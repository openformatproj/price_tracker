#!/usr/bin/env python3
"""
Unit tests for cookie_helper.py
"""

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from engine.cookie_helper import (
    find_browser_executable,
    refresh_browser_cookies,
    save_cookie_to_file,
)


class TestCookieHelper(unittest.TestCase):
    def test_save_cookie_to_file_creates_and_updates(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write(json.dumps({"existing.com": {"foo": "bar"}}))
            temp_path = f.name

        try:
            # 1. Update existing file with new domain
            ok = save_cookie_to_file("trovaprezzi.it", "datadome", "token_123", cookies_path=temp_path)
            self.assertTrue(ok)

            with open(temp_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["existing.com"]["foo"], "bar")
            self.assertEqual(data["trovaprezzi.it"]["datadome"], "token_123")

            # 2. Update existing cookie key in domain
            ok2 = save_cookie_to_file("trovaprezzi.it", "datadome", "token_456", cookies_path=temp_path)
            self.assertTrue(ok2)

            with open(temp_path, "r", encoding="utf-8") as f:
                data2 = json.load(f)
            self.assertEqual(data2["trovaprezzi.it"]["datadome"], "token_456")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    @patch("shutil.which")
    def test_find_browser_executable(self, mock_which):
        mock_which.side_effect = lambda x: "/usr/bin/google-chrome" if "google-chrome" in x else None
        bin_path = find_browser_executable()
        self.assertEqual(bin_path, "/usr/bin/google-chrome")

    @patch("engine.cookie_helper.find_browser_executable")
    def test_refresh_browser_cookies_no_browser(self, mock_find):
        mock_find.return_value = None
        ok, val, err = refresh_browser_cookies()
        self.assertFalse(ok)
        self.assertIsNone(val)
        self.assertIn("No Chrome or Chromium", err)

    @patch("engine.cookie_helper.save_cookie_to_file")
    @patch("engine.cookie_helper.find_browser_executable")
    @patch("subprocess.Popen")
    @patch("urllib.request.urlopen")
    def test_refresh_browser_cookies_success(
        self, mock_urlopen, mock_popen, mock_find, mock_save
    ):
        mock_find.return_value = "/usr/bin/google-chrome"
        mock_save.return_value = True

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        # Mock DevTools HTTP /json response
        mock_http_resp = MagicMock()
        mock_http_resp.read.return_value = json.dumps([
            {"type": "page", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/1"}
        ]).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_http_resp

        # Mock WebSocket connection and response
        mock_ws = MagicMock()
        mock_ws.recv.return_value = json.dumps({
            "id": 1,
            "result": {
                "cookies": [
                    {"name": "other_cookie", "value": "123"},
                    {"name": "datadome", "value": "secret_datadome_token_abc"},
                ]
            }
        })

        mock_ws_mod = MagicMock()
        mock_ws_mod.connect.return_value.__enter__.return_value = mock_ws
        mock_sync_mod = MagicMock()
        mock_sync_mod.client = mock_ws_mod
        mock_parent = MagicMock()
        mock_parent.sync = mock_sync_mod

        with patch.dict("sys.modules", {"websockets": mock_parent, "websockets.sync": mock_sync_mod, "websockets.sync.client": mock_ws_mod}):
            ok, val, err = refresh_browser_cookies(
                url="https://www.trovaprezzi.it",
                target_domain="trovaprezzi.it",
                target_cookie="datadome",
                timeout=5,
            )

            self.assertTrue(ok)
            self.assertEqual(val, "secret_datadome_token_abc")
            self.assertIsNone(err)
            mock_save.assert_called_once_with(
            "trovaprezzi.it",
            "datadome",
            "secret_datadome_token_abc",
            "cookies.json",
            extra_cookies={"other_cookie": "123", "datadome": "secret_datadome_token_abc"},
        )


if __name__ == "__main__":
    unittest.main()
