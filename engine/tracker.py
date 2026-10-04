#!/usr/bin/env python3
"""
Price Tracker Engine: Scraping, historical tracking, alerts, and purchase lifecycle.
"""

from datetime import datetime
import json
import logging
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

import requests

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    from .i18n import t, resolve_lang, get_category_label
except ImportError:
    from i18n import t, resolve_lang, get_category_label

logger = logging.getLogger(__name__)

DEFAULT_BOM_PATH = "bom.json"
DEFAULT_CONFIG_PATH = "telegram_config.json"
DEFAULT_HISTORY_PATH = "price_history.json"
DEFAULT_COOKIES_PATH = "cookies.json"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def load_bom(bom_path: str = DEFAULT_BOM_PATH) -> List[Dict[str, Any]]:
    """
    Load components from BOM JSON file.
    Supports either a list of items or an object with an 'items' key.
    """
    if not os.path.exists(bom_path):
        logger.error("BOM file not found at: %s", bom_path)
        return []

    try:
        with open(bom_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "items" in data:
                return data["items"]
            else:
                logger.error("Invalid BOM format in %s: expected list or object with 'items'", bom_path)
                return []
    except Exception as e:
        logger.error("Failed to load BOM from %s: %s", bom_path, e)
        return []


def get_bom_categories(bom: List[Dict[str, Any]]) -> List[str]:
    """
    Extract unique categories from BOM preserving order of appearance.
    Completely decoupled from any specific hardware domain.
    """
    seen = set()
    categories = []
    for item in bom:
        cat = item.get("category")
        if cat and cat not in seen:
            seen.add(cat)
            categories.append(cat)
    return categories


def parse_price(text: Optional[str]) -> Optional[float]:
    """
    Parse a price string in various European and standard formats into a float.
    Handles '€ 1.250,50', '839,00 €', '95.99 €', 'da 599,00 €', etc.
    """
    if not text:
        return None

    cleaned = text.replace("\xa0", " ").strip()
    match = re.search(r"(\d[\d\s.,]*\d|\d)", cleaned)
    if not match:
        return None

    num_str = match.group(1).replace(" ", "")

    if "," in num_str and "." in num_str:
        if num_str.rfind(",") > num_str.rfind("."):
            num_str = num_str.replace(".", "").replace(",", ".")
        else:
            num_str = num_str.replace(",", "")
    elif "," in num_str:
        parts = num_str.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            num_str = parts[0] + "." + parts[1]
        else:
            num_str = num_str.replace(",", "")
    elif "." in num_str:
        parts = num_str.split(".")
        if len(parts) > 2:
            num_str = "".join(parts[:-1]) + "." + parts[-1]
        elif len(parts) == 2 and len(parts[1]) == 3:
            num_str = parts[0] + parts[1]

    try:
        val = float(num_str)
        return val if val > 0 else None
    except ValueError:
        return None


def extract_prices_from_html(html: str, selector: str) -> List[float]:
    """
    Extract all valid prices matching a CSS selector from an HTML string.
    """
    if BeautifulSoup is None:
        logger.error("BeautifulSoup4 is not installed. Please install it with 'pip install beautifulsoup4'.")
        return []

    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    elements = soup.select(selector)
    prices: List[float] = []

    for el in elements:
        text = el.get_text(separator=" ", strip=True)
        price = parse_price(text)
        if price is not None and price > 0:
            prices.append(price)

    return prices


def fetch_source_prices(
    source: Dict[str, Any],
    session: requests.Session,
    cookies_by_domain: Optional[Dict[str, Any]] = None,
    timeout: int = 15,
) -> Tuple[Optional[float], Optional[str]]:
    """
    Fetch a page from a store source and extract the lowest valid price found.
    Returns (lowest_price, error_message).
    """
    url = source.get("url", "")
    selector = source.get("css_selector") or source.get("selector", "")
    store = source.get("store", "Unknown")

    if not url or not selector:
        return None, "Missing url or css_selector"

    headers = {**DEFAULT_HEADERS, **source.get("headers", {})}

    req_cookies = {}
    if cookies_by_domain:
        for domain, c_val in cookies_by_domain.items():
            if domain in url:
                if isinstance(c_val, dict):
                    req_cookies.update(c_val)
                elif isinstance(c_val, str):
                    for pair in c_val.split(";"):
                        if "=" in pair:
                            k, v = pair.strip().split("=", 1)
                            req_cookies[k] = v

    source_cookies = source.get("cookies", {})
    if isinstance(source_cookies, dict):
        req_cookies.update(source_cookies)

    try:
        resp = session.get(url, headers=headers, cookies=req_cookies or None, timeout=timeout)
        if resp.status_code == 403:
            return None, f"HTTP 403 Forbidden ({store} bot-protection active)"
        if resp.status_code == 404:
            return None, f"HTTP 404 Not Found"
        resp.raise_for_status()

        prices = extract_prices_from_html(resp.text, selector)
        if not prices:
            return None, f"No prices matched selector '{selector}'"

        return min(prices), None
    except requests.exceptions.Timeout:
        return None, f"Request timeout after {timeout}s"
    except requests.exceptions.RequestException as e:
        return None, f"Network error: {str(e)}"
    except Exception as e:
        return None, f"Parsing error: {str(e)}"


def load_cookies_config(cookies_path: str = DEFAULT_COOKIES_PATH) -> Dict[str, Any]:
    """
    Load cookie configuration from JSON file or environment variables.
    """
    cookies_config: Dict[str, Any] = {}

    if os.path.exists(cookies_path):
        try:
            with open(cookies_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    cookies_config = data
        except Exception as e:
            logger.warning("Could not read cookies from %s: %s", cookies_path, e)

    datadome_env = os.environ.get("TROVAPREZZI_DATADOME")
    if datadome_env:
        tp_cookies = cookies_config.setdefault("trovaprezzi.it", {})
        if isinstance(tp_cookies, dict):
            tp_cookies["datadome"] = datadome_env

    cookies_json_env = os.environ.get("COOKIES_JSON")
    if cookies_json_env:
        try:
            extra = json.loads(cookies_json_env)
            if isinstance(extra, dict):
                cookies_config.update(extra)
        except Exception as e:
            logger.warning("Failed to parse COOKIES_JSON env var: %s", e)

    return cookies_config


def load_telegram_config(config_path: str = DEFAULT_CONFIG_PATH) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
    """
    Load Telegram credentials and optional cookies from config or environment.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    cookies: Dict[str, Any] = {}

    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                token = token or data.get("bot_token")
                chat_id = chat_id or data.get("chat_id")
                cookies = data.get("cookies", {})
        except Exception as e:
            logger.warning("Could not read config from %s: %s", config_path, e)

    return token, chat_id, cookies


def load_price_history(history_path: str = DEFAULT_HISTORY_PATH) -> Dict[str, Any]:
    """
    Load historical price tracking data from JSON file.
    """
    if not os.path.exists(history_path):
        return {}
    try:
        with open(history_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Could not read history from %s: %s. Starting fresh.", history_path, e)
        return {}


def save_price_history(history: Dict[str, Any], history_path: str = DEFAULT_HISTORY_PATH) -> None:
    """
    Atomically save price history to a JSON file.
    """
    temp_path = f"{history_path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    os.replace(temp_path, history_path)


def mark_item_purchased(
    item_id: str,
    price: Optional[float] = None,
    bom_path: str = DEFAULT_BOM_PATH,
    history_path: str = DEFAULT_HISTORY_PATH,
    bom: Optional[List[Dict[str, Any]]] = None,
    lang: Optional[str] = None,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Mark an item in BOM as purchased in price history.
    If price is omitted, uses the last checked price or lowest price or target price.
    """
    if bom is None:
        bom = load_bom(bom_path)
    matched_item = None
    for it in bom:
        if it["id"].lower() == item_id.lower():
            matched_item = it
            break

    if not matched_item:
        return False, t("item_not_found_in_bom", lang=lang, item_id=item_id), None

    history = load_price_history(history_path)
    rec = history.setdefault(matched_item["id"], {})

    if price is None or price <= 0:
        if rec.get("last_checked_price"):
            final_price = float(rec["last_checked_price"])
        elif rec.get("lowest_price"):
            final_price = float(rec["lowest_price"])
        else:
            final_price = float(matched_item.get("target_price", 0.0))
    else:
        final_price = float(price)

    rec["purchased"] = True
    rec["purchase_price"] = final_price
    rec["purchase_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    save_price_history(history, history_path)
    return True, t("purchase_success_record", lang=lang, name=matched_item["name"], price=final_price), matched_item


def mark_item_returned(
    item_id: str,
    bom_path: str = DEFAULT_BOM_PATH,
    history_path: str = DEFAULT_HISTORY_PATH,
    bom: Optional[List[Dict[str, Any]]] = None,
    lang: Optional[str] = None,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Mark an item as returned/refunded, removing its purchased state.
    """
    if bom is None:
        bom = load_bom(bom_path)
    matched_item = None
    for it in bom:
        if it["id"].lower() == item_id.lower():
            matched_item = it
            break

    if not matched_item:
        return False, t("item_not_found_in_bom", lang=lang, item_id=item_id), None

    history = load_price_history(history_path)
    if matched_item["id"] in history:
        history[matched_item["id"]]["purchased"] = False
        history[matched_item["id"]].pop("purchase_price", None)
        history[matched_item["id"]].pop("purchase_date", None)
        save_price_history(history, history_path)

    return True, t("return_success_record", lang=lang, name=matched_item["name"]), matched_item


def get_build_status(
    bom_path: str = DEFAULT_BOM_PATH,
    history_path: str = DEFAULT_HISTORY_PATH,
    bom: Optional[List[Dict[str, Any]]] = None,
    history: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Calculate progress of the build: which items are purchased vs pending,
    total spent, remaining cost at current best prices, and comparison to target budget.
    Dynamically works on any BOM without hardcoding categories.
    """
    if bom is None:
        bom = load_bom(bom_path)
    if history is None:
        history = load_price_history(history_path)
    all_categories = get_bom_categories(bom)

    by_category: Dict[str, List[Dict[str, Any]]] = {cat: [] for cat in all_categories}

    for it in bom:
        cat = it.get("category")
        if cat in by_category:
            by_category[cat].append(it)

    purchased_items = []
    pending_categories = []
    total_spent = 0.0
    total_pending = 0.0
    total_target = 0.0

    for cat in all_categories:
        items = by_category[cat]
        purchased_in_cat = None
        for it in items:
            rec = history.get(it["id"], {})
            if rec.get("purchased"):
                purchased_in_cat = {
                    "item": it,
                    "purchase_price": float(rec.get("purchase_price", 0.0)),
                    "purchase_date": rec.get("purchase_date"),
                }
                break

        if purchased_in_cat:
            purchased_items.append(purchased_in_cat)
            total_spent += purchased_in_cat["purchase_price"]
            total_target += float(purchased_in_cat["item"].get("target_price", 0.0))
        else:
            best_opt = None
            best_eff_price = float("inf")
            for it in items:
                rec = history.get(it["id"], {})
                last_p = rec.get("last_checked_price")
                lowest_p = rec.get("lowest_price")
                target_p = float(it.get("target_price", 0.0))

                if last_p is not None:
                    eff_p = float(last_p)
                    store = rec.get("last_checked_source", "Store")
                    url = rec.get("last_checked_url", "")
                elif lowest_p is not None:
                    eff_p = float(lowest_p)
                    store = rec.get("lowest_price_source", "Store")
                    url = rec.get("lowest_price_url", "")
                else:
                    eff_p = target_p
                    store = "Target"
                    url = it["sources"][0]["url"] if it.get("sources") else ""

                if eff_p < best_eff_price:
                    best_eff_price = eff_p
                    best_opt = {
                        "item": it,
                        "price": eff_p,
                        "store": store,
                        "url": url,
                        "target_price": target_p,
                    }

            if best_opt:
                pending_categories.append(best_opt)
                total_pending += best_opt["price"]
                total_target += best_opt["target_price"]

    return {
        "purchased_items": purchased_items,
        "pending_categories": pending_categories,
        "total_spent": total_spent,
        "total_pending": total_pending,
        "total_estimated": total_spent + total_pending,
        "total_target": total_target,
        "diff_vs_target": (total_spent + total_pending) - total_target,
        "completed_count": len(purchased_items),
        "total_categories": len(all_categories),
    }


def evaluate_item(
    item: Dict[str, Any],
    best_price: float,
    best_source: Dict[str, str],
    history: Dict[str, Any],
    force_notify: bool = False,
) -> Dict[str, Any]:
    """
    Evaluate detected price against target_price and historical lowest price.
    """
    item_id = item["id"]
    target_price = float(item["target_price"])
    record = history.get(item_id, {})

    lowest_price = record.get("lowest_price")
    last_notified_price = record.get("last_notified_price")

    now_iso = datetime.now().isoformat()
    best_store = best_source.get("store", "Unknown")
    best_url = best_source.get("url", "")

    record["target_price"] = target_price
    record["category"] = item.get("category", "")
    record["option_index"] = item.get("option_index", 0)
    record["last_checked_price"] = best_price
    record["last_checked_date"] = now_iso
    record["last_checked_source"] = best_store
    record["last_checked_url"] = best_url

    is_below_target = best_price <= target_price
    is_new_lowest = lowest_price is None or best_price < lowest_price
    previous_lowest = lowest_price

    if is_new_lowest:
        record["lowest_price"] = best_price
        record["lowest_price_date"] = now_iso
        record["lowest_price_source"] = best_store
        record["lowest_price_url"] = best_url

    history[item_id] = record

    should_notify = False
    reason = "NONE"

    if force_notify:
        should_notify = True
        reason = "FORCE"
    elif is_below_target:
        if last_notified_price is None:
            should_notify = True
            reason = "INITIAL_BELOW_TARGET"
        elif best_price < last_notified_price:
            should_notify = True
            reason = "PRICE_DROP"
        else:
            reason = "UNCHANGED_BELOW_TARGET"
    elif is_new_lowest:
        if previous_lowest is not None:
            should_notify = True
            reason = "NEW_LOWEST"
        else:
            reason = "INITIAL_DETECTED"
    else:
        reason = "ABOVE_TARGET"

    return {
        "item_id": item_id,
        "item_name": item["name"],
        "category": item.get("category", ""),
        "option_index": item.get("option_index", 0),
        "target_price": target_price,
        "best_price": best_price,
        "best_store": best_store,
        "best_url": best_url,
        "is_below_target": is_below_target,
        "is_new_lowest": is_new_lowest,
        "previous_lowest": previous_lowest,
        "is_price_drop": (last_notified_price is not None and best_price < last_notified_price),
        "reason": reason,
        "action": "NOTIFY" if should_notify else "SKIP",
    }


def format_telegram_message(eval_result: Dict[str, Any], lang: Optional[str] = None) -> str:
    """
    Format a single alert item into HTML markup for Telegram.
    """
    actual_lang = resolve_lang(lang)
    item_name = eval_result["item_name"]
    best_price = eval_result["best_price"]
    target_price = eval_result["target_price"]
    best_store = eval_result["best_store"]
    best_url = eval_result["best_url"]
    reason = eval_result["reason"]
    category = eval_result.get("category", "")
    option_index = eval_result.get("option_index", 0)

    category_info = (
        t("category_option_str", lang=actual_lang, category=category, option_index=option_index)
        if category else ""
    )
    diff = best_price - target_price
    diff_sign = "+" if diff > 0 else "-"
    diff_str = f"{diff_sign}€{abs(diff):.2f}"

    lines = [
        t(
            "single_alert_header",
            lang=actual_lang,
            item_name=item_name,
            category_info=category_info,
            best_price=best_price,
            target_price=target_price,
            diff_str=diff_str,
            best_store=best_store,
        )
    ]

    if reason in ("INITIAL_BELOW_TARGET", "PRICE_DROP"):
        lines.append(t("single_alert_below_target", lang=actual_lang))
    elif reason == "NEW_LOWEST":
        prev = eval_result.get("previous_lowest")
        prev_str = f"€{prev:.2f}" if prev is not None else "N/A"
        lines.append(t("single_alert_new_lowest", lang=actual_lang, prev_str=prev_str))

    if best_url:
        lines.append(t("single_alert_open_link", lang=actual_lang, url=best_url, store=best_store))

    return "\n".join(lines)


def format_aggregated_telegram_message(alerts: List[Dict[str, Any]], lang: Optional[str] = None) -> str:
    """
    Format multiple alert items into a single consolidated Telegram HTML digest.
    """
    if not alerts:
        return ""

    actual_lang = resolve_lang(lang)
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    count = len(alerts)
    deal_word = t("deal_word_single" if count == 1 else "deal_word_plural", lang=actual_lang)

    header = t("digest_header", lang=actual_lang, date=now_str, count=count, deal_word=deal_word)

    items_text = []
    for idx, alert in enumerate(alerts, 1):
        item_name = alert["item_name"]
        best_price = alert["best_price"]
        target_price = alert["target_price"]
        best_store = alert["best_store"]
        best_url = alert["best_url"]
        reason = alert["reason"]
        category = alert.get("category", "")
        opt_idx = alert.get("option_index", 0)

        category_str = (
            t("category_digest_str", lang=actual_lang, category=category, opt_idx=opt_idx)
            if category else ""
        )
        diff = best_price - target_price
        diff_str = f"-€{abs(diff):.2f}" if diff <= 0 else f"+€{diff:.2f}"

        status_line = ""
        if reason in ("INITIAL_BELOW_TARGET", "PRICE_DROP"):
            status_line = t("digest_status_below_target", lang=actual_lang)
        elif reason == "NEW_LOWEST":
            prev = alert.get("previous_lowest")
            prev_str = f"€{prev:.2f}" if prev is not None else "N/A"
            status_line = t("digest_status_new_lowest", lang=actual_lang, prev=prev_str)

        link_str = t("open_offer_link", lang=actual_lang, url=best_url) if best_url else ""

        block = t(
            "digest_item_block",
            lang=actual_lang,
            idx=idx,
            item_name=item_name,
            category_str=category_str,
            best_price=best_price,
            best_store=best_store,
            target_price=target_price,
            diff_str=diff_str,
            status_line=status_line,
            link_str=link_str,
        )
        items_text.append(block)

    return header + "\n".join(items_text)


def send_telegram_notification(
    token: Optional[str],
    chat_id: Optional[str],
    message: str,
    timeout: int = 15,
) -> bool:
    """
    Send an HTML-formatted message via the Telegram Bot API.
    Splits automatically if message exceeds 4000 characters.
    """
    if not token or not chat_id:
        logger.warning("Telegram credentials not configured. Please set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.")
        return False

    if "YOUR_BOT_TOKEN" in token or "YOUR_CHAT_ID" in chat_id:
        logger.warning("Telegram credentials contain placeholders.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    def _send_chunk(text_chunk: str) -> bool:
        payload = {
            "chat_id": chat_id,
            "text": text_chunk,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }
        try:
            resp = requests.post(url, json=payload, timeout=timeout)
            if resp.status_code == 200:
                logger.info("Telegram notification sent successfully.")
                return True
            else:
                logger.error("Failed to send Telegram notification: HTTP %s - %s", resp.status_code, resp.text)
                return False
        except requests.exceptions.RequestException as e:
            logger.error("Network error sending Telegram notification: %s", e)
            return False

    max_len = 4000
    if len(message) <= max_len:
        return _send_chunk(message)

    chunks = []
    lines = message.split("\n\n")
    current_chunk = ""
    for line in lines:
        if len(current_chunk) + len(line) + 2 > max_len:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = line
        else:
            current_chunk = f"{current_chunk}\n\n{line}" if current_chunk else line
    if current_chunk:
        chunks.append(current_chunk)

    all_success = True
    for chunk in chunks:
        if not _send_chunk(chunk):
            all_success = False

    return all_success


def run_tracker(
    config_path: str = DEFAULT_CONFIG_PATH,
    history_path: str = DEFAULT_HISTORY_PATH,
    cookies_path: str = DEFAULT_COOKIES_PATH,
    bom_path: str = DEFAULT_BOM_PATH,
    dry_run: bool = False,
    force_notify: bool = False,
    target_item_id: Optional[str] = None,
    lang: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Main monitoring pipeline.
    """
    actual_lang = resolve_lang(lang=lang, config_path=config_path)
    token, chat_id, legacy_cookies = load_telegram_config(config_path)
    file_cookies = load_cookies_config(cookies_path)
    cookies = {**legacy_cookies, **file_cookies}
    history = load_price_history(history_path)

    bom_items = load_bom(bom_path)
    items_to_check = bom_items
    if target_item_id:
        items_to_check = [item for item in bom_items if item["id"] == target_item_id]
        if not items_to_check:
            logger.error("Item ID '%s' not found in BOM", target_item_id)
            return []

    session = requests.Session()
    results = []
    triggered_alerts: List[Dict[str, Any]] = []

    fulfilled_categories: Dict[str, Dict[str, Any]] = {}
    for it in bom_items:
        h_entry = history.get(it["id"], {})
        if h_entry.get("purchased"):
            c = it.get("category")
            if c:
                fulfilled_categories[c] = {
                    "item_id": it["id"],
                    "name": it.get("name", it["id"]),
                    "purchase_price": float(h_entry.get("purchase_price", 0.0)),
                    "purchase_date": h_entry.get("purchase_date"),
                }

    print("=" * 70)
    print(t("starting_check", lang=actual_lang, timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    if dry_run:
        print(t("dry_run_banner", lang=actual_lang))
    if fulfilled_categories:
        print(t("completed_slots_header", lang=actual_lang, count=len(fulfilled_categories), categories=', '.join(fulfilled_categories.keys())))
    print("=" * 70)

    for item in items_to_check:
        item_id = item["id"]
        name = item["name"]
        cat = item.get("category")
        target_price = item["target_price"]
        h_entry = history.get(item_id, {})

        if h_entry.get("purchased"):
            p_price = float(h_entry.get("purchase_price", 0.0))
            print(f"\n📦 [{item_id}] {name} (" + t("item_purchased_banner", lang=actual_lang, price=p_price) + ")")
            continue

        if cat and cat in fulfilled_categories and fulfilled_categories[cat]["item_id"] != item_id:
            fulfilled_by = fulfilled_categories[cat]
            print(
                f"\n📦 [{item_id}] {name} ("
                + t("slot_fulfilled_banner", lang=actual_lang, category=cat, name=fulfilled_by['name'], price=fulfilled_by['purchase_price'])
                + ")"
            )
            continue

        target_lbl = t("target_label", lang=actual_lang)
        print(f"\n📦 [{item_id}] {name} ({target_lbl}: €{target_price:.2f})")

        detected_prices: List[Tuple[float, Dict[str, str]]] = []

        for source in item.get("sources", []):
            store = source.get("store", "Unknown")
            price, err = fetch_source_prices(source, session, cookies_by_domain=cookies)
            if price is not None:
                detected_prices.append((price, source))
                print(f"  • {store:12}: €{price:.2f}")
            else:
                print(f"  • {store:12}: ❌ Error ({err})")

        if not detected_prices:
            print("  " + t("no_prices_detected", lang=actual_lang))
            continue

        detected_prices.sort(key=lambda x: x[0])
        best_price, best_source = detected_prices[0]
        best_store = best_source.get("store", "Unknown")

        eval_res = evaluate_item(
            item=item,
            best_price=best_price,
            best_source=best_source,
            history=history,
            force_notify=force_notify,
        )

        results.append(eval_res)

        action_str = eval_res["action"]
        tags = []
        if eval_res["is_below_target"]:
            tags.append(t("tag_below_target", lang=actual_lang))
        if eval_res["is_new_lowest"]:
            prev_low = eval_res.get("previous_lowest")
            prev_str = f"€{prev_low:.2f}" if prev_low is not None else "N/A"
            tags.append(t("tag_new_lowest", lang=actual_lang, prev=prev_str))
        if eval_res["is_price_drop"]:
            tags.append(t("tag_price_drop", lang=actual_lang))

        tag_display = " ".join(f"[{tag}]" for tag in tags)
        print(f"  ✅ Best: €{best_price:.2f} ({best_store}) {tag_display}")

        if action_str == "NOTIFY":
            triggered_alerts.append(eval_res)
            print("  " + t("alert_queued", lang=actual_lang, reason=eval_res['reason']))
        else:
            print("  " + t("no_alert_needed", lang=actual_lang, reason=eval_res['reason']))

    if triggered_alerts:
        print("\n" + t("alerts_collected", lang=actual_lang, count=len(triggered_alerts)))
        if dry_run:
            print(t("dry_run_preview", lang=actual_lang))
            print("-" * 50)
            print(format_aggregated_telegram_message(triggered_alerts, lang=actual_lang))
            print("-" * 50)
        else:
            agg_msg = format_aggregated_telegram_message(triggered_alerts, lang=actual_lang)
            success = send_telegram_notification(token, chat_id, agg_msg)
            if success:
                logger.info("Aggregated Telegram alert successfully sent.")
                for al in triggered_alerts:
                    iid = al["item_id"]
                    if iid in history:
                        history[iid]["last_notified_price"] = al["best_price"]
            else:
                logger.error("Failed to send aggregated Telegram notification.")
    else:
        print("\n" + t("no_alerts_triggered", lang=actual_lang))

    if not dry_run:
        save_price_history(history, history_path)
        logger.info(t("history_saved", lang=actual_lang, path=history_path))

    print("\n" + "=" * 70)
    print(t("check_finished", lang=actual_lang))
    print("=" * 70)

    return results
