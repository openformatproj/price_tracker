#!/usr/bin/env python3
"""
Local Browser Cookie Refresh Helper.
Launches a real browser via Chrome DevTools Protocol (CDP) to bypass/solve
anti-bot challenges (e.g. DataDome) and automatically extract session cookies.
"""

import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Known browser executables in order of preference
CHROME_CANDIDATES = [
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium-browser",
    "/usr/bin/chromium",
]


def find_browser_executable() -> Optional[str]:
    """Find available Chrome or Chromium binary on the system PATH."""
    for candidate in CHROME_CANDIDATES:
        path = shutil.which(candidate)
        if path:
            return path
    return None


def save_cookie_to_file(
    domain: str,
    cookie_name: str,
    cookie_value: str,
    cookies_path: str = "cookies.json",
    extra_cookies: Optional[Dict[str, str]] = None,
) -> bool:
    """Save or update cookies in cookies.json."""
    data: Dict[str, Any] = {}
    if os.path.exists(cookies_path):
        try:
            with open(cookies_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.warning("Could not read %s: %s. Overwriting.", cookies_path, e)
            data = {}

    if domain not in data or not isinstance(data[domain], dict):
        data[domain] = {}

    data[domain][cookie_name] = cookie_value
    if extra_cookies:
        data[domain].update(extra_cookies)

    try:
        with open(cookies_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error("Failed to write to %s: %s", cookies_path, e)
        return False


def refresh_browser_cookies(
    url: str = "https://www.trovaprezzi.it",
    target_domain: str = "trovaprezzi.it",
    target_cookie: str = "datadome",
    cookies_path: str = "cookies.json",
    timeout: int = 60,
    headless: bool = False,
    port: int = 9222,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Launch Chrome, navigate to target URL, and poll for target_cookie via CDP.
    Returns: (success, cookie_value, error_message)
    """
    browser_bin = find_browser_executable()
    if not browser_bin:
        return False, None, "No Chrome or Chromium browser executable found on system."

    try:
        import websockets.sync.client
    except ImportError:
        return False, None, "The 'websockets' library is required. Install with: pip install websockets"

    temp_profile = tempfile.mkdtemp(prefix="pt_chrome_")

    cmd = [
        browser_bin,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={temp_profile}",
        "--disable-blink-features=AutomationControlled",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if headless:
        cmd.append("--headless=new")
    cmd.append(url)

    logger.info("Launching %s to refresh cookie '%s' from %s", browser_bin, target_cookie, url)
    print(f"🌐 Launching browser: {browser_bin}")
    print(f"🔗 Target: {url}")
    if not headless:
        print("💡 A browser window has opened. If a CAPTCHA or puzzle challenge appears, solve it in the window.")
    print("⏳ Waiting for cookie extraction...")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    start_time = time.time()
    extracted_val = None
    err_msg = None

    try:
        # Wait for Chrome's DevTools HTTP endpoint to become responsive
        ws_url = None
        for _ in range(20):
            if time.time() - start_time > timeout:
                break
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=2) as resp:
                    tabs = json.loads(resp.read().decode())
                    for tab in tabs:
                        if tab.get("type") == "page" and "webSocketDebuggerUrl" in tab:
                            ws_url = tab["webSocketDebuggerUrl"]
                            break
                    if ws_url:
                        break
            except Exception:
                time.sleep(0.5)

        if not ws_url:
            err_msg = "Could not connect to Chrome DevTools port (is another instance using port 9222?)"
            return False, None, err_msg

        # Connect to CDP WebSocket and poll Network.getCookies
        with websockets.sync.client.connect(ws_url) as ws:
            req_id = 1
            while time.time() - start_time < timeout:
                if proc.poll() is not None:
                    err_msg = "Browser closed before cookie was detected."
                    break

                ws.send(json.dumps({
                    "id": req_id,
                    "method": "Network.getCookies",
                    "params": {"urls": [url]},
                }))
                req_id += 1

                try:
                    raw_resp = ws.recv(timeout=3)
                    resp = json.loads(raw_resp)
                    cookies_list = resp.get("result", {}).get("cookies", [])
                    domain_cookies = {}
                    for c in cookies_list:
                        c_name = c.get("name")
                        c_val = c.get("value")
                        if c_name and c_val:
                            domain_cookies[c_name] = c_val
                        if c_name == target_cookie and c_val:
                            extracted_val = c_val

                    # Check page title to avoid early exit while Cloudflare/Turnstile challenge is active
                    is_challenge = False
                    try:
                        ws.send(json.dumps({
                            "id": req_id,
                            "method": "Runtime.evaluate",
                            "params": {"expression": "document.title"},
                        }))
                        req_id += 1
                        raw_t = ws.recv(timeout=2)
                        t_val = json.loads(raw_t).get("result", {}).get("result", {}).get("value", "")
                        if t_val and any(kw in t_val.lower() for kw in ["ci siamo quasi", "just a moment", "challenge"]):
                            is_challenge = True
                    except Exception:
                        pass

                    if not is_challenge and (extracted_val or "cf_clearance" in domain_cookies):
                        if not extracted_val and "cf_clearance" in domain_cookies:
                            extracted_val = domain_cookies["cf_clearance"]
                        break
                except Exception:
                    pass

                time.sleep(1.5)

        if not extracted_val and not err_msg:
            err_msg = f"Timed out after {timeout}s waiting for '{target_cookie}' cookie."

    finally:
        # Cleanly terminate browser process
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        shutil.rmtree(temp_profile, ignore_errors=True)

    if extracted_val:
        saved = save_cookie_to_file(
            target_domain,
            target_cookie if target_cookie in domain_cookies else "cf_clearance",
            extracted_val,
            cookies_path,
            extra_cookies=domain_cookies,
        )
        if saved:
            print(f"✅ Successfully captured cookies: {', '.join(domain_cookies.keys())}!")
            print(f"💾 Saved to {cookies_path}")
            return True, extracted_val, None
        return True, extracted_val, f"Captured cookie but failed to write to {cookies_path}"

    return False, None, err_msg
