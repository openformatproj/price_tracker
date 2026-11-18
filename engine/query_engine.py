#!/usr/bin/env python3
"""
Natural language query engine and build optimization calculator.
Supports deterministic intent resolution and optional Google Gemini conversational fallback.
Decoupled from specific hardware domains (derives categories dynamically from BOM).
"""

import json
import logging
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

import requests

try:
    from .tracker import (
        load_bom,
        load_price_history,
        mark_item_purchased,
        mark_item_returned,
        get_build_status,
        get_bom_categories,
        parse_price,
    )
    from .i18n import (
        t,
        resolve_lang,
        get_category_label,
        DEFAULT_ICONS,
    )
except ImportError:
    from tracker import (
        load_bom,
        load_price_history,
        mark_item_purchased,
        mark_item_returned,
        get_build_status,
        get_bom_categories,
        parse_price,
    )
    from i18n import (
        t,
        resolve_lang,
        get_category_label,
        DEFAULT_ICONS,
    )

logger = logging.getLogger(__name__)


def load_engine_data(
    bom_path: str = "bom.json",
    history_path: str = "price_history.json",
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Load BOM components and price history records."""
    bom = load_bom(bom_path)
    history = load_price_history(history_path)
    return bom, history


def calculate_cheapest_build(
    bom: List[Dict[str, Any]],
    history: Dict[str, Any],
    constraints: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Calculate the cheapest complete assembly build combining whichever interchangeable
    options currently offer the lowest price across all distinct categories in the BOM.
    If a category contains an item marked as purchased, it locks that option (Exception A).
    If constraints is provided, it restricts matching categories to candidate options matching the constraint (Exception B).
    All active candidate options across unfulfilled categories MUST have a determinable current price
    (last_checked_price is not None and > 0). If any active candidate lacks a current price, an error
    is returned listing the items for which the current price cannot be determined.
    """
    categories = get_bom_categories(bom)
    by_category: Dict[str, List[Dict[str, Any]]] = {cat: [] for cat in categories}

    for item in bom:
        cat = item.get("category", "")
        if cat in by_category:
            by_category[cat].append(item)

    selected_build: List[Dict[str, Any]] = []
    missing_price_items: List[Dict[str, Any]] = []
    total_effective = 0.0
    total_target = 0.0

    for cat in categories:
        options = by_category.get(cat, [])
        if not options:
            continue

        # Exception A: Check if any item in this category is already purchased
        purchased_item = None
        for it in options:
            rec = history.get(it["id"], {})
            if rec.get("purchased"):
                purchased_item = it
                break

        if purchased_item is not None:
            rec = history.get(purchased_item["id"], {})
            purchase_price = float(rec.get("purchase_price") or purchased_item.get("target_price", 0.0))
            target_price = float(purchased_item.get("target_price", 0.0))
            selected_build.append({
                "item": purchased_item,
                "effective_price": purchase_price,
                "price_type": "purchased",
                "store": "Acquistato",
                "url": "",
                "target_price": target_price,
                "is_purchased": True,
                "last_checked_date": rec.get("last_checked_date"),
            })
            total_effective += purchase_price
            total_target += target_price
            continue

        # Exception B: Filter options by constraint for this category if present
        constraint = constraints.get(cat) if constraints else None
        candidate_options = options
        if constraint is not None:
            constrained_options = []
            for it in options:
                # 1. Exact item id match
                if isinstance(constraint, str) and it.get("id") == constraint:
                    constrained_options.append(it)
                # 2. Option index match
                elif isinstance(constraint, int) and it.get("option_index") == constraint:
                    constrained_options.append(it)
                # 3. Keyword / substring match in name, id, or description
                elif isinstance(constraint, str):
                    c_low = constraint.lower().strip()
                    it_name = it.get("name", "").lower()
                    it_id = it.get("id", "").lower()
                    it_desc = it.get("description", "").lower()
                    if c_low in it_name or c_low in it_id or c_low in it_desc:
                        constrained_options.append(it)
            if constrained_options:
                candidate_options = constrained_options

        # Check current price for all active candidate options in this category
        category_candidates_evaluated: List[Dict[str, Any]] = []
        for it in candidate_options:
            rec = history.get(it["id"], {})
            last_price = rec.get("last_checked_price")
            if last_price is None or float(last_price) <= 0:
                missing_price_items.append({
                    "item": it,
                    "category": cat,
                })
            else:
                target_price = float(it.get("target_price", 0.0))
                category_candidates_evaluated.append({
                    "item": it,
                    "effective_price": float(last_price),
                    "price_type": "checked",
                    "store": rec.get("last_checked_source", "Store"),
                    "url": rec.get("last_checked_url", ""),
                    "target_price": target_price,
                    "is_purchased": False,
                    "last_checked_date": rec.get("last_checked_date"),
                })

        if category_candidates_evaluated:
            category_candidates_evaluated.sort(key=lambda x: x["effective_price"])
            best_opt = category_candidates_evaluated[0]
            selected_build.append(best_opt)
            total_effective += best_opt["effective_price"]
            total_target += best_opt["target_price"]

    if missing_price_items:
        return {
            "error": "missing_current_prices",
            "missing_items": missing_price_items,
            "categories": categories,
            "constraints": constraints,
        }

    return {
        "items": selected_build,
        "total_price": total_effective,
        "total_target": total_target,
        "diff_vs_target": total_effective - total_target,
        "categories": categories,
        "constraints": constraints,
    }


def format_build_reply(
    build_data: Dict[str, Any],
    lang: Optional[str] = None,
    constraint_label: Optional[str] = None,
) -> str:
    """Format cheapest build result into rich Telegram HTML."""
    actual_lang = resolve_lang(lang)

    if build_data.get("error") == "missing_current_prices":
        missing_items = build_data.get("missing_items", [])
        opt_abbr = t("opt_abbr", lang=actual_lang)
        lines = [t("build_error_missing_prices_header", lang=actual_lang)]
        for entry in missing_items:
            it = entry["item"]
            cat = entry.get("category", it.get("category", ""))
            opt_idx = it.get("option_index", 0)
            label = it.get("category_label") or get_category_label(cat, lang=actual_lang)
            lines.append(f"• <b>{it['name']}</b> (<i>{label} - {opt_abbr} {opt_idx}</i>)")
        lines.append("\n" + t("build_error_missing_prices_footer", lang=actual_lang))
        return "\n".join(lines)

    items = build_data.get("items", [])
    total_price = build_data.get("total_price", 0.0)
    total_target = build_data.get("total_target", 0.0)
    diff = build_data.get("diff_vs_target", 0.0)

    label_to_use = constraint_label or build_data.get("constraint_label")
    if label_to_use:
        title = t("build_reply_title_constrained", lang=actual_lang, constraint=label_to_use).rstrip("\n")
    else:
        title = t("build_reply_title", lang=actual_lang).rstrip("\n")

    lines = [title]

    for entry in items:
        item = entry["item"]
        cat = item.get("category", "")
        opt_idx = item.get("option_index", 0)
        label = item.get("category_label") or get_category_label(cat, lang=actual_lang)
        price = entry["effective_price"]
        store = entry["store"]
        url = entry["url"]
        target = entry["target_price"]
        opt_abbr = t("opt_abbr", lang=actual_lang)

        if entry.get("price_type") == "purchased":
            badge = t("badge_purchased", lang=actual_lang)
            lines.append(
                f"{label}: <b>€{price:.2f}</b> (<b>{badge}</b>) ✅\n"
                f"   ↳ <i>{item['name']}</i> ({opt_abbr} {opt_idx})"
            )
        else:
            status_tag = ""
            if price <= target:
                status_tag = f" 🎯 <i>({t('badge_below_target', lang=actual_lang)})</i>"
            elif entry["price_type"] == "target_fallback":
                status_tag = f" ⚠️ <i>({t('badge_target_estimate', lang=actual_lang)})</i>"

            prep = t("store_preposition", lang=actual_lang)
            link_tag = f'<a href="{url}">{store}</a>' if url else store
            lines.append(
                f"{label}: <b>€{price:.2f}</b> {prep} {link_tag}{status_tag}\n"
                f"   ↳ <i>{item['name']}</i> ({opt_abbr} {opt_idx})"
            )

    lines.append("\n" + "━" * 32)
    current_lbl = t("current_total_label", lang=actual_lang)
    target_lbl = t("target_total_label", lang=actual_lang)
    diff_suffix = t("diff_vs_target_suffix", lang=actual_lang)
    lines.append(f"💰 <b>{current_lbl}</b> <b>€{total_price:.2f}</b>")
    diff_sign = "+" if diff > 0 else "-"
    lines.append(
        f"🎯 <b>{target_lbl}</b> €{total_target:.2f} "
        f"({diff_sign}€{abs(diff):.2f} {diff_suffix})"
    )

    return "\n".join(lines)


def format_build_status_reply(status_data: Dict[str, Any], lang: Optional[str] = None) -> str:
    """Format build progress and budget status into Telegram HTML."""
    actual_lang = resolve_lang(lang)
    lines = [
        t("status_title", lang=actual_lang, completed=status_data['completed_count'], total=status_data['total_categories'])
    ]
    if status_data.get("purchased_items"):
        lines.append(t("purchased_header_html", lang=actual_lang))
        for p in status_data["purchased_items"]:
            dt_str = f" <i>({p['purchase_date']})</i>" if p.get("purchase_date") else ""
            lines.append(f"• <b>{p['item']['name']}</b>: <b>€{p['purchase_price']:.2f}</b>{dt_str}")
        lines.append(t("spent_so_far_html", lang=actual_lang, spent=status_data['total_spent']))

    if status_data.get("pending_categories"):
        lines.append(t("pending_header_html", lang=actual_lang))
        prep = t("store_preposition", lang=actual_lang)
        for p in status_data["pending_categories"]:
            url = p.get("url")
            store = p.get("store", "Store")
            link_str = f'<a href="{url}">{store}</a>' if url else store
            lines.append(f"• <b>{p['item']['name']}</b>: <b>€{p['price']:.2f}</b> {prep} {link_str}")
        lines.append(t("remaining_estimated_html", lang=actual_lang, pending=status_data['total_pending']))

    lines.append("━" * 32)
    lines.append(t("total_estimated_html", lang=actual_lang, total=status_data['total_estimated']))
    diff = status_data["diff_vs_target"]
    diff_str = f"+€{diff:.2f}" if diff > 0 else f"-€{abs(diff):.2f}"
    lines.append(t("target_budget_html", lang=actual_lang, target=status_data['total_target'], diff_str=diff_str))
    return "\n".join(lines)


def search_items(
    query: str,
    bom: List[Dict[str, Any]],
    history: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Fuzzy/keyword match items by name, ID, category or description."""
    q = query.lower().strip()
    words = [w for w in re.split(r"\W+", q) if len(w) > 2]
    matches = []

    for item in bom:
        score = 0
        name = item.get("name", "").lower()
        item_id = item.get("id", "").lower()
        category = item.get("category", "").lower()
        desc = item.get("description", "").lower()

        if q in name or q in item_id:
            score += 50

        for w in words:
            if w in name:
                score += 15
            if w in item_id:
                score += 12
            if w in category:
                score += 10
            if w in desc:
                score += 4

        if score > 0:
            matches.append({
                "item": item,
                "history": history.get(item["id"], {}),
                "score": score,
            })

    matches.sort(key=lambda x: x["score"], reverse=True)
    return matches


def format_item_reply(matches: List[Dict[str, Any]], lang: Optional[str] = None) -> str:
    """Format matching items into Telegram HTML."""
    actual_lang = resolve_lang(lang)
    if not matches:
        return t("no_matches_found", lang=actual_lang)

    top_matches = matches[:3]
    blocks = []

    for match in top_matches:
        item = match["item"]
        rec = match["history"]
        target = float(item.get("target_price", 0.0))
        last_price = rec.get("last_checked_price")
        last_store = rec.get("last_checked_source", "N/A")
        last_url = rec.get("last_checked_url", "")
        lowest = rec.get("lowest_price")

        lines = [
            t(
                "item_reply_header",
                lang=actual_lang,
                name=item["name"],
                category=item.get("category", ""),
                option_index=item.get("option_index", 0),
                target=target,
            )
        ]

        if rec.get("purchased"):
            p_price = float(rec.get("purchase_price", 0.0))
            lines.append(t("item_reply_purchased", lang=actual_lang, price=p_price))
        elif last_price is not None:
            link = f'<a href="{last_url}">{last_store}</a>' if last_url else last_store
            diff = float(last_price) - target
            diff_str = f"(-€{abs(diff):.2f})" if diff <= 0 else f"(+€{diff:.2f})"
            lines.append(
                t(
                    "item_reply_last_price",
                    lang=actual_lang,
                    price=float(last_price),
                    link=link,
                    diff_str=diff_str,
                )
            )
        else:
            lines.append(t("item_reply_not_detected", lang=actual_lang))

        if lowest is not None:
            lines.append(t("item_reply_lowest", lang=actual_lang, price=float(lowest)))

        if item.get("description"):
            lines.append(f"ℹ️ <i>{item['description']}</i>")

        blocks.append("\n".join(lines))

    return "\n\n" + ("\n" + "─" * 28 + "\n\n").join(blocks)


def get_active_deals(
    bom: List[Dict[str, Any]],
    history: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Return all components that are currently below target or at all-time lows."""
    deals = []
    for item in bom:
        rec = history.get(item["id"], {})
        last_price = rec.get("last_checked_price")
        target_price = float(item.get("target_price", 0.0))
        lowest_price = rec.get("lowest_price")

        if last_price is not None:
            is_below_target = float(last_price) <= target_price
            is_new_lowest = lowest_price is not None and float(last_price) <= float(lowest_price)

            if is_below_target or is_new_lowest:
                deals.append({
                    "item": item,
                    "price": float(last_price),
                    "target": target_price,
                    "store": rec.get("last_checked_source", "Store"),
                    "url": rec.get("last_checked_url", ""),
                    "is_below_target": is_below_target,
                    "is_new_lowest": is_new_lowest,
                })

    deals.sort(key=lambda x: x["price"] - x["target"])
    return deals


def format_deals_reply(deals: List[Dict[str, Any]], lang: Optional[str] = None) -> str:
    """Format active bargains into Telegram HTML."""
    actual_lang = resolve_lang(lang)
    if not deals:
        return t("no_deals", lang=actual_lang)

    lines = [
        t("deals_title", lang=actual_lang, count=len(deals))
    ]

    for d in deals:
        item = d["item"]
        price = d["price"]
        target = d["target"]
        store = d["store"]
        url = d["url"]
        diff = price - target

        badge = (
            t("badge_below_target", lang=actual_lang)
            if d["is_below_target"]
            else t("badge_new_lowest", lang=actual_lang)
        )
        link_str = f'<a href="{url}">{store}</a>' if url else store
        diff_str = f"-€{abs(diff):.2f}" if diff <= 0 else f"+€{diff:.2f}"

        lines.append(
            t(
                "deal_item_line",
                lang=actual_lang,
                name=item["name"],
                badge=badge,
                price=price,
                link=link_str,
                target=target,
                diff_str=diff_str,
            )
        )

    return "\n".join(lines)


def format_help_reply(lang: Optional[str] = None) -> str:
    """Return user guide with sample natural language questions."""
    actual_lang = resolve_lang(lang)
    return t("help_reply", lang=actual_lang)


def classify_and_answer_local(
    query: str,
    bom: List[Dict[str, Any]],
    history: Dict[str, Any],
    history_path: str = "price_history.json",
    lang: Optional[str] = None,
) -> str:
    """
    Deterministic rule and intent-based natural language answerer.
    Works fast, with 0 external dependencies and 0 costs.
    """
    actual_lang = resolve_lang(lang)
    q = query.strip().lower()

    if q in ("/start", "/help", "aiuto", "help", "ciao", "cosa puoi fare?", "what can you do?"):
        return format_help_reply(lang=actual_lang)

    # 1. Purchase / Buy Intent
    buy_match = re.search(r"^/buy\s+([a-zA-Z0-9_-]+)(?:\s+([0-9.,]+))?", q)
    if not buy_match:
        nl_buy = re.search(
            r"(?:ho\s+(?:comprato|acquistato|preso)|acquistat[oa]|comprat[oa]|segna\s+(?:come\s+)?(?:acquistat[oa]|comprat[oa])|i\s+(?:bought|purchased)|mark\s+(?:as\s+)?purchased)\s+(?:l[aeio]\s+|the\s+|il\s+)?(.+?)(?:\s+(?:a|per|for|at|costo|prezzo|cost|price)\s+([€\d.,]+))?$",
            q,
        )
        if nl_buy:
            item_query = nl_buy.group(1).strip()
            price_str = nl_buy.group(2)
        else:
            item_query = None
            price_str = None
    else:
        item_query = buy_match.group(1).strip()
        price_str = buy_match.group(2)

    if item_query:
        matched_item = None
        for it in bom:
            if it["id"].lower() == item_query.lower():
                matched_item = it
                break
        if not matched_item:
            matches = search_items(item_query, bom, history)
            if matches and matches[0]["score"] >= 6:
                matched_item = matches[0]["item"]

        if matched_item:
            parsed_price = parse_price(price_str) if price_str else None
            ok, msg, _ = mark_item_purchased(
                matched_item["id"], parsed_price, history_path=history_path, bom=bom, lang=actual_lang
            )
            if ok:
                h_fresh = history.get(matched_item["id"], {})
                paid = h_fresh.get("purchase_price", parsed_price or 0.0)
                cat = matched_item.get("category", "")
                return t(
                    "purchase_bot_reply",
                    lang=actual_lang,
                    name=matched_item["name"],
                    price=paid,
                    category=cat.upper(),
                )
            else:
                return f"❌ {msg}"

    # 2. Return / Refund Intent
    ret_match = re.search(r"^/return\s+([a-zA-Z0-9_-]+)", q)
    if not ret_match:
        nl_ret = re.search(
            r"(?:ho\s+(?:reso|restituito)|fatto\s+il\s+reso|restituisco|restituit[oa]|annulla\s+acquisto|i\s+returned|returned|refunded)\s+(?:d[ieall']+|the\s+|il\s+|la\s+)?(.+)",
            q,
        )
        item_query_ret = nl_ret.group(1).strip() if nl_ret else None
    else:
        item_query_ret = ret_match.group(1).strip()

    if item_query_ret:
        matched_item = None
        for it in bom:
            if it["id"].lower() == item_query_ret.lower():
                matched_item = it
                break
        if not matched_item:
            matches = search_items(item_query_ret, bom, history)
            if matches and matches[0]["score"] >= 6:
                matched_item = matches[0]["item"]

        if matched_item:
            ok, msg, _ = mark_item_returned(
                matched_item["id"], history_path=history_path, bom=bom, lang=actual_lang
            )
            if ok:
                cat = matched_item.get("category", "")
                return t(
                    "return_bot_reply",
                    lang=actual_lang,
                    name=matched_item["name"],
                    category=cat.upper(),
                )
            else:
                return f"❌ {msg}"

    # 3. Build status / Purchases intent
    status_patterns = [
        r"cosa\s+ho\s+comprato",
        r"stato\s+acquist[ie]",
        r"budget\s+rimanente",
        r"quanto\s+ho\s+speso",
        r"quanto\s+manca",
        r"stato\s+build",
        r"componenti\s+mancanti",
        r"avanzamento\s+build",
        r"riepilogo\s+spes[ae]",
        r"what\s+(?:have\s+i|did\s+i)\s+(?:bought|buy|purchased|purchase)",
        r"what.*(?:bought|purchased)\s+so\s+far",
        r"build\s+status",
        r"spending\s+summary",
        r"^/status",
    ]
    for pat in status_patterns:
        if re.search(pat, q):
            st = get_build_status(bom=bom, history=history, history_path=history_path)
            return format_build_status_reply(st, lang=actual_lang)

    # 4. Cheapest configuration intent
    cheapest_patterns = [
        r"configurazione.*conveniente",
        r"configurazione.*economica",
        r"build.*conveniente",
        r"build.*economica",
        r"miglior.*prezzo.*totale",
        r"prezzo.*configurazione",
        r"costo.*totale",
        r"quanto.*costa.*(la|l|il).*(build|configurazione|server|computer)",
        r"(?:cost[- ]effective|cheapest|best|optimal).*(?:build|configuration)",
        r"cheapest.*build",
        r"best.*build",
        r"optimal.*build",
        r"cheapest.*configuration",
        r"/build",
        r"/economica",
    ]
    for pattern in cheapest_patterns:
        if re.search(pattern, q):
            constraint_text = None
            if q.startswith("/build "):
                constraint_text = q[7:].strip()
            else:
                m_c = re.search(
                    r"(?:con|with|includendo|having|solo\s+con|only\s+with|usando|using)\s+([^?;\n]+)",
                    q,
                )
                if m_c:
                    constraint_text = m_c.group(1).rstrip(".? ").strip()

            if constraint_text:
                parts = re.split(r"\s+(?:e|and)\s+|,\s*", constraint_text)
                constraints: Dict[str, Any] = {}
                labels: List[str] = []
                unmatched_parts: List[str] = []

                for part in parts:
                    part_str = part.strip()
                    if not part_str:
                        continue
                    m_items = search_items(part_str, bom, history)
                    part_tokens = [w for w in re.split(r"\W+", part_str.lower()) if len(w) > 1]
                    numeric_tokens = [w for w in part_tokens if any(c.isdigit() for c in w)]

                    valid_match = False
                    if m_items and m_items[0]["score"] >= 8:
                        top_it = m_items[0]["item"]
                        combined_text = (
                            top_it.get("name", "") + " " + top_it.get("id", "") + " " + top_it.get("description", "")
                        ).lower()
                        if all(nt in combined_text for nt in numeric_tokens):
                            valid_match = True

                    if valid_match:
                        top_it = m_items[0]["item"]
                        cat = top_it.get("category", "")
                        constraints[cat] = top_it["id"]
                        labels.append(top_it.get("name", part_str))
                    else:
                        unmatched_parts.append(part_str)

                if unmatched_parts and not constraints:
                    return t("constraint_not_found", lang=actual_lang, constraint=", ".join(unmatched_parts))

                if constraints:
                    label_str = ", ".join(labels)
                    build_data = calculate_cheapest_build(bom, history, constraints=constraints)
                    return format_build_reply(build_data, lang=actual_lang, constraint_label=label_str)

            build_data = calculate_cheapest_build(bom, history)
            return format_build_reply(build_data, lang=actual_lang)

    # 5. Active deals intent
    deals_patterns = [
        r"offert[ae]",
        r"scont[oi]",
        r"sotto.*target",
        r"affar[ei]",
        r"ribass[oi]",
        r"deals?",
        r"discounts?",
        r"below\s+target",
        r"/deals",
        r"/offerte",
    ]
    for pattern in deals_patterns:
        if re.search(pattern, q):
            deals = get_active_deals(bom, history)
            return format_deals_reply(deals, lang=actual_lang)

    # 6. Target budget intent
    target_budget_patterns = [
        r"budget.*target",
        r"totale.*target",
        r"costo.*target",
        r"spesa.*target",
        r"target\s+budget",
        r"total\s+target",
    ]
    for pattern in target_budget_patterns:
        if re.search(pattern, q):
            total_target = 0.0
            categories = get_bom_categories(bom)
            for cat in categories:
                cat_items = [it for it in bom if it.get("category") == cat]
                purchased_it = next((it for it in cat_items if history.get(it["id"], {}).get("purchased")), None)
                if purchased_it:
                    rec = history.get(purchased_it["id"], {})
                    total_target += float(rec.get("purchase_price") or purchased_it.get("target_price", 0.0))
                elif cat_items:
                    total_target += min(float(it.get("target_price", 0.0)) for it in cat_items)
            return t("target_budget_reply", lang=actual_lang, total=total_target)

    # 7. Search specific item or category
    matches = search_items(query, bom, history)
    if matches and matches[0]["score"] >= 8:
        return format_item_reply(matches, lang=actual_lang)

    return t("fallback_not_understood", lang=actual_lang)


def answer_with_gemini(
    query: str,
    bom: List[Dict[str, Any]],
    history: Dict[str, Any],
    api_key: str,
    lang: Optional[str] = None,
) -> Optional[str]:
    """Invoke Google Gemini 2.5 Flash API with BOM and history context."""
    if not api_key:
        return None

    actual_lang = resolve_lang(lang)
    model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    context_data = {
        "bom_components": [
            {
                "id": it["id"],
                "category": it.get("category", ""),
                "option_index": it.get("option_index", 0),
                "name": it.get("name", it["id"]),
                "target_price": it.get("target_price", 0.0),
                "last_checked_price": history.get(it["id"], {}).get("last_checked_price"),
                "store": history.get(it["id"], {}).get("last_checked_source"),
                "url": history.get(it["id"], {}).get("last_checked_url"),
                "lowest_price": history.get(it["id"], {}).get("lowest_price"),
                "purchased": history.get(it["id"], {}).get("purchased"),
                "purchase_price": history.get(it["id"], {}).get("purchase_price"),
            }
            for it in bom
        ],
        "cheapest_calculated_build": calculate_cheapest_build(bom, history),
    }

    if actual_lang == "en":
        system_instruction = (
            "You are an AI assistant specialized in price tracking and BOM / PC build assembly optimization.\n"
            "Answer user questions in English using EXCLUSIVELY the provided context data.\n"
            "If the user asks about the generic cheapest configuration or total cost without specific constraints, "
            "use the data from 'cheapest_calculated_build'.\n"
            "If 'cheapest_calculated_build' reports an error ('missing_current_prices'), or if any candidate component "
            "(neither purchased nor excluded by constraints) is missing a current price ('last_checked_price' is null or missing), "
            "you MUST state that it is not possible to determine the cheapest configuration at this moment, explicitly listing the components whose current price is unknown.\n"
            "If the user specifies constraints, preferences, or component choices (e.g. 'with 16GB GPU' or 'with ASUS motherboard'), "
            "pick the component satisfying the constraint for that category and choose the cheapest available options with known current prices for the other categories, "
            "calculating the updated total and specifying each selected component.\n"
            "Use HTML formatting compatible with Telegram: <b>bold</b>, <i>italic</i>, <code>code</code>, <a href=\"URL\">link</a>.\n"
            "Be clear, concise, and direct."
        )
    else:
        system_instruction = (
            "Sei un assistente AI specializzato nel monitoraggio dei prezzi di distinte base / assemblaggi.\n"
            "Rispondi alle domande dell'utente in italiano usando ESCLUSIVAMENTE i dati forniti nel contesto.\n"
            "Se l'utente chiede della configurazione più conveniente generica (senza vincoli), "
            "usa i dati di 'cheapest_calculated_build'.\n"
            "Se 'cheapest_calculated_build' segnala l'errore 'missing_current_prices', o se uno o più componenti candidati "
            "(non acquistati e non esclusi da vincoli) non hanno un prezzo corrente ('last_checked_price' nullo o mancante), "
            "DEVI segnalare all'utente che è impossibile determinare con certezza la configurazione più conveniente in questo momento, elencando esplicitamente i componenti di cui non si conosce il prezzo corrente.\n"
            "Se l'utente specifica vincoli, preferenze o scelte di componenti (ad es. 'con GPU da 16 GB' o 'con scheda madre ASUS'), "
            "seleziona il componente corrispondente al vincolo per quella categoria e scegli le opzioni con prezzo corrente noto più economiche per tutte le altre, "
            "calcolando il totale aggiornato e specificando ciascun componente scelto.\n"
            "Usa formattazione HTML compatibile con Telegram: <b>grassetto</b>, <i>corsivo</i>, <code>codice</code>, <a href=\"URL\">link</a>.\n"
            "Sii chiaro, conciso e diretto."
        )

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": f"Dati attuali componenti e storico prezzi:\n```json\n{json.dumps(context_data, ensure_ascii=False)}\n```\n\nDomanda dell'utente: {query}"
                    }
                ]
            }
        ],
        "systemInstruction": {
            "parts": [{"text": system_instruction}]
        },
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 1000,
        },
    }

    try:
        resp = requests.post(url, json=payload, timeout=12)
        if resp.status_code == 200:
            res_json = resp.json()
            candidates = res_json.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()
        else:
            logger.warning("Gemini API error: HTTP %s - %s", resp.status_code, resp.text)
    except Exception as e:
        logger.warning("Failed to call Gemini API: %s", e)

    return None


def answer_query(
    query: str,
    bom_path: str = "bom.json",
    history_path: str = "price_history.json",
    gemini_api_key: Optional[str] = None,
    lang: Optional[str] = None,
    config_path: Optional[str] = None,
) -> str:
    """
    Main query resolution entry point.
    Tries deterministic local engine for state mutations & common intents,
    falls back to Gemini AI for complex natural conversational requests.
    """
    actual_lang = resolve_lang(lang=lang, config_path=config_path)
    bom, history = load_engine_data(bom_path, history_path)
    if not bom:
        return t("bom_empty_or_not_found", lang=actual_lang, path=bom_path)

    local_reply = classify_and_answer_local(
        query, bom, history, history_path=history_path, lang=actual_lang
    )
    fallback_prefix_it = t("fallback_not_understood", lang="it")[:20]
    fallback_prefix_en = t("fallback_not_understood", lang="en")[:20]
    is_fallback = local_reply.startswith(fallback_prefix_it) or local_reply.startswith(fallback_prefix_en)

    if not is_fallback:
        return local_reply

    api_key = gemini_api_key or os.environ.get("GEMINI_API_KEY")
    if api_key:
        llm_reply = answer_with_gemini(query, bom, history, api_key, lang=actual_lang)
        if llm_reply:
            return llm_reply

    return local_reply
