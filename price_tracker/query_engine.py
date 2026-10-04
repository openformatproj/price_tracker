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

logger = logging.getLogger("price_tracker.query_engine")

DEFAULT_ICONS = {
    "gpu": "🎮",
    "cpu": "🧠",
    "cooler": "❄️",
    "mobo": "🔌",
    "motherboard": "🔌",
    "ram": "⚡",
    "memory": "⚡",
    "psu": "🔋",
    "power": "🔋",
    "case": "📦",
    "storage": "💾",
    "ssd": "💾",
    "hdd": "💽",
    "fan": "🌀",
    "monitor": "🖥️",
}


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
) -> Dict[str, Any]:
    """
    Calculate the cheapest complete assembly build combining whichever interchangeable
    options currently offer the lowest price across all distinct categories in the BOM.
    If a category contains an item marked as purchased, it locks that option.
    """
    categories = get_bom_categories(bom)
    by_category: Dict[str, List[Dict[str, Any]]] = {cat: [] for cat in categories}

    for item in bom:
        cat = item.get("category", "")
        if cat in by_category:
            rec = history.get(item["id"], {})
            last_price = rec.get("last_checked_price")
            lowest_price = rec.get("lowest_price")
            target_price = float(item.get("target_price", 0.0))
            is_purchased = bool(rec.get("purchased"))

            if is_purchased and rec.get("purchase_price") is not None:
                effective_price = float(rec["purchase_price"])
                price_type = "purchased"
                store = "Acquistato"
                url = ""
            elif last_price is not None:
                effective_price = float(last_price)
                price_type = "checked"
                store = rec.get("last_checked_source", "Store")
                url = rec.get("last_checked_url", "")
            elif lowest_price is not None:
                effective_price = float(lowest_price)
                price_type = "historical_low"
                store = rec.get("lowest_price_source", "Store")
                url = rec.get("lowest_price_url", "")
            else:
                effective_price = target_price
                price_type = "target_fallback"
                store = "Target"
                url = item["sources"][0]["url"] if item.get("sources") else ""

            by_category[cat].append({
                "item": item,
                "effective_price": effective_price,
                "price_type": price_type,
                "store": store,
                "url": url,
                "target_price": target_price,
                "is_purchased": is_purchased,
                "last_checked_date": rec.get("last_checked_date"),
            })

    selected_build: List[Dict[str, Any]] = []
    total_effective = 0.0
    total_target = 0.0

    for cat in categories:
        options = by_category.get(cat, [])
        if not options:
            continue
        purchased_opt = next((o for o in options if o.get("is_purchased")), None)
        if purchased_opt:
            best_option = purchased_opt
        else:
            options.sort(key=lambda x: x["effective_price"])
            best_option = options[0]

        selected_build.append(best_option)
        total_effective += best_option["effective_price"]
        total_target += best_option["target_price"]

    return {
        "items": selected_build,
        "total_price": total_effective,
        "total_target": total_target,
        "diff_vs_target": total_effective - total_target,
        "categories": categories,
    }


def format_build_reply(build_data: Dict[str, Any]) -> str:
    """Format cheapest build result into rich Telegram HTML."""
    items = build_data.get("items", [])
    total_price = build_data.get("total_price", 0.0)
    total_target = build_data.get("total_target", 0.0)
    diff = build_data.get("diff_vs_target", 0.0)

    lines = [
        "🖥️ <b>Configurazione Più Conveniente Attuale</b>",
        "<i>Combinazione ottimale delle opzioni intercambiabili:</i>\n",
    ]

    for entry in items:
        item = entry["item"]
        cat = item.get("category", "")
        opt_idx = item.get("option_index", 0)
        icon = item.get("icon") or DEFAULT_ICONS.get(cat.lower(), "📦")
        label = item.get("category_label") or f"{icon} <b>{cat.capitalize()}</b>"
        price = entry["effective_price"]
        store = entry["store"]
        url = entry["url"]
        target = entry["target_price"]

        if entry.get("price_type") == "purchased":
            lines.append(
                f"{label}: <b>€{price:.2f}</b> (<b>Acquistato!</b>) ✅\n"
                f"   ↳ <i>{item['name']}</i> (Opz. {opt_idx})"
            )
        else:
            status_tag = ""
            if price <= target:
                status_tag = " 🎯 <i>(Sotto target!)</i>"
            elif entry["price_type"] == "target_fallback":
                status_tag = " ⚠️ <i>(Stima target)</i>"

            link_tag = f'<a href="{url}">{store}</a>' if url else store
            lines.append(
                f"{label}: <b>€{price:.2f}</b> su {link_tag}{status_tag}\n"
                f"   ↳ <i>{item['name']}</i> (Opz. {opt_idx})"
            )

    lines.append("\n" + "━" * 32)
    lines.append(f"💰 <b>Totale Attuale:</b> <b>€{total_price:.2f}</b>")
    diff_sign = "+" if diff > 0 else "-"
    lines.append(
        f"🎯 <b>Totale Target:</b> €{total_target:.2f} "
        f"({diff_sign}€{abs(diff):.2f} rispetto all'obiettivo)"
    )

    return "\n".join(lines)


def format_build_status_reply(status_data: Dict[str, Any]) -> str:
    """Format build progress and budget status into Telegram HTML."""
    lines = [
        f"📊 <b>Stato Avanzamento Build ({status_data['completed_count']}/{status_data['total_categories']} acquistati)</b>\n"
    ]
    if status_data.get("purchased_items"):
        lines.append("✅ <b>Componenti Acquistati:</b>")
        for p in status_data["purchased_items"]:
            dt_str = f" <i>({p['purchase_date']})</i>" if p.get("purchase_date") else ""
            lines.append(f"• <b>{p['item']['name']}</b>: <b>€{p['purchase_price']:.2f}</b>{dt_str}")
        lines.append(f"  ↳ 💰 <i>Speso finora:</i> <b>€{status_data['total_spent']:.2f}</b>\n")

    if status_data.get("pending_categories"):
        lines.append("⏳ <b>Da Acquistare (Miglior offerta attuale):</b>")
        for p in status_data["pending_categories"]:
            url = p.get("url")
            store = p.get("store", "Store")
            link_str = f'<a href="{url}">{store}</a>' if url else store
            lines.append(f"• <b>{p['item']['name']}</b>: <b>€{p['price']:.2f}</b> su {link_str}")
        lines.append(f"  ↳ ⏳ <i>Rimanente stimato:</i> <b>€{status_data['total_pending']:.2f}</b>\n")

    lines.append("━" * 32)
    lines.append(f"💰 <b>Costo Totale Finale Stimato:</b> <b>€{status_data['total_estimated']:.2f}</b>")
    diff = status_data["diff_vs_target"]
    diff_str = f"+€{diff:.2f}" if diff > 0 else f"-€{abs(diff):.2f}"
    lines.append(f"🎯 <b>Budget Target:</b> €{status_data['total_target']:.2f} ({diff_str})")
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


def format_item_reply(matches: List[Dict[str, Any]]) -> str:
    """Format matching items into Telegram HTML."""
    if not matches:
        return "❌ Nessun componente corrispondente trovato nella distinta base."

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
            f"📦 <b>{item['name']}</b>",
            f"🏷️ <i>Categoria: {item['category']} (Opzione {item.get('option_index', 0)})</i>",
            f"🎯 <b>Target:</b> €{target:.2f}",
        ]

        if rec.get("purchased"):
            p_price = float(rec.get("purchase_price", 0.0))
            lines.append(f"✅ <b>Stato: ACQUISTATO a €{p_price:.2f}</b>")
        elif last_price is not None:
            link = f'<a href="{last_url}">{last_store}</a>' if last_url else last_store
            diff = float(last_price) - target
            diff_str = f"(-€{abs(diff):.2f})" if diff <= 0 else f"(+€{diff:.2f})"
            lines.append(f"💰 <b>Ultimo Prezzo:</b> <b>€{float(last_price):.2f}</b> su {link} {diff_str}")
        else:
            lines.append("💰 <b>Ultimo Prezzo:</b> <i>Non ancora rilevato</i>")

        if lowest is not None:
            lines.append(f"📉 <b>Minimo Storico:</b> €{float(lowest):.2f}")

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


def format_deals_reply(deals: List[Dict[str, Any]]) -> str:
    """Format active bargains into Telegram HTML."""
    if not deals:
        return (
            "ℹ️ <b>Nessuna offerta speciale attiva al momento.</b>\n\n"
            "Tutti i componenti rilevati si trovano attualmente sopra le soglie target impostate."
        )

    lines = [
        f"🎯 <b>Offerte & Minimi Rilevati ({len(deals)} trovate):</b>\n"
    ]

    for d in deals:
        item = d["item"]
        price = d["price"]
        target = d["target"]
        store = d["store"]
        url = d["url"]
        diff = price - target

        badge = "🎯 Sotto Target" if d["is_below_target"] else "📉 Minimo Storico"
        link_str = f'<a href="{url}">{store}</a>' if url else store
        diff_str = f"-€{abs(diff):.2f}" if diff <= 0 else f"+€{diff:.2f}"

        lines.append(
            f"• <b>{item['name']}</b> ({badge})\n"
            f"  💰 <b>€{price:.2f}</b> su {link_str} | Target: €{target:.2f} ({diff_str})"
        )

    return "\n".join(lines)


def format_help_reply() -> str:
    """Return user guide with sample natural language questions."""
    return (
        "🤖 <b>Price Tracker Bot</b>\n\n"
        "Puoi farmi domande in <b>linguaggio naturale</b> su prezzi, componenti, stato acquisti e build!\n\n"
        "💡 <b>Esempi di domande e comandi:</b>\n"
        "• <i>\"Ho comprato la CPU a 316.76€\"</i>\n"
        "• <i>\"Acquistata scheda madre ASUS TUF a 143.89\"</i>\n"
        "• <i>\"Ho fatto il reso del componente\"</i>\n"
        "• <i>\"Cosa ho comprato finora?\"</i> / <i>\"Stato build\"</i>\n"
        "• <i>\"Qual è la configurazione più conveniente?\"</i>\n"
        "• <i>\"Quanto costa il processore?\"</i>\n"
        "• <i>\"Ci sono offerte sotto target al momento?\"</i>\n\n"
        "⚡ <b>Comandi rapidi:</b>\n"
        "• /buy &lt;item_id&gt; [prezzo] - Segna un componente come acquistato\n"
        "• /return &lt;item_id&gt; - Registra un reso e riattiva il monitoraggio\n"
        "• /status - Mostra avanzamento build e budget speso/rimanente\n"
        "• /build - Mostra la configurazione più economica\n"
        "• /deals - Mostra le offerte sotto target\n"
        "• /help - Mostra questo messaggio"
    )


def classify_and_answer_local(
    query: str,
    bom: List[Dict[str, Any]],
    history: Dict[str, Any],
    history_path: str = "price_history.json",
) -> str:
    """
    Deterministic rule and intent-based natural language answerer.
    Works fast, with 0 external dependencies and 0 costs.
    """
    q = query.strip().lower()

    if q in ("/start", "/help", "aiuto", "help", "ciao", "cosa puoi fare?"):
        return format_help_reply()

    # 1. Purchase / Buy Intent
    buy_match = re.search(r"^/buy\s+([a-zA-Z0-9_-]+)(?:\s+([0-9.,]+))?", q)
    if not buy_match:
        nl_buy = re.search(
            r"(?:ho\s+(?:comprato|acquistato|preso)|acquistat[oa]|comprat[oa]|segna\s+(?:come\s+)?(?:acquistat[oa]|comprat[oa]))\s+(?:l[aeio]\s+|il\s+)?(.+?)(?:\s+(?:a|per|costo|prezzo)\s+([€\d.,]+))?$",
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
            ok, msg, _ = mark_item_purchased(matched_item["id"], parsed_price, history_path=history_path, bom=bom)
            if ok:
                h_fresh = history.get(matched_item["id"], {})
                paid = h_fresh.get("purchase_price", parsed_price or 0.0)
                cat = matched_item.get("category", "")
                return (
                    f"✅ <b>Componente segnato come acquistato!</b>\n\n"
                    f"📦 <b>{matched_item['name']}</b>\n"
                    f"💰 <b>Prezzo d'acquisto registrato:</b> €{paid:.2f}\n"
                    f"⏸️ <i>Il monitoraggio dei prezzi per la categoria <b>{cat.upper()}</b> è stato sospeso.</i>"
                )
            else:
                return f"❌ {msg}"

    # 2. Return / Refund Intent
    ret_match = re.search(r"^/return\s+([a-zA-Z0-9_-]+)", q)
    if not ret_match:
        nl_ret = re.search(
            r"(?:ho\s+(?:reso|restituito)|fatto\s+il\s+reso|restituisco|restituit[oa]|annulla\s+acquisto)\s+(?:d[ieall']+|il\s+|la\s+)?(.+)",
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
            ok, msg, _ = mark_item_returned(matched_item["id"], history_path=history_path, bom=bom)
            if ok:
                cat = matched_item.get("category", "")
                return (
                    f"🔄 <b>Reso registrato con successo!</b>\n\n"
                    f"📦 <b>{matched_item['name']}</b>\n"
                    f"▶️ <i>Il monitoraggio dei prezzi per la categoria <b>{cat.upper()}</b> è stato riattivato.</i>"
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
        r"^/status",
    ]
    for pat in status_patterns:
        if re.search(pat, q):
            st = get_build_status(bom=bom, history=history, history_path=history_path)
            return format_build_status_reply(st)

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
        r"cheapest.*build",
        r"/build",
        r"/economica",
    ]
    for pattern in cheapest_patterns:
        if re.search(pattern, q):
            build_data = calculate_cheapest_build(bom, history)
            return format_build_reply(build_data)

    # 5. Active deals intent
    deals_patterns = [
        r"offert[ae]",
        r"scont[oi]",
        r"sotto.*target",
        r"affar[ei]",
        r"ribass[oi]",
        r"deals",
        r"/deals",
        r"/offerte",
    ]
    for pattern in deals_patterns:
        if re.search(pattern, q):
            deals = get_active_deals(bom, history)
            return format_deals_reply(deals)

    # 6. Target budget intent
    target_budget_patterns = [
        r"budget.*target",
        r"totale.*target",
        r"costo.*target",
        r"spesa.*target",
    ]
    for pattern in target_budget_patterns:
        if re.search(pattern, q):
            build_data = calculate_cheapest_build(bom, history)
            return (
                f"🎯 <b>Budget Target Complessivo:</b> <b>€{build_data['total_target']:.2f}</b>\n\n"
                f"Assumendo di raggiungere i prezzi target impostati per l'opzione più economica di ogni categoria."
            )

    # 7. Search specific item or category
    matches = search_items(query, bom, history)
    if matches and matches[0]["score"] >= 8:
        return format_item_reply(matches)

    return (
        "🤔 Non ho compreso con certezza la tua richiesta.\n\n"
        "Prova a chiedermi ad esempio:\n"
        "• <i>\"Ho comprato la CPU a 316.76€\"</i>\n"
        "• <i>\"Cosa ho comprato finora?\"</i>\n"
        "• <i>\"Qual è la configurazione più conveniente?\"</i>\n"
        "• <i>\"Quanto costa il processore?\"</i>\n"
        "• <i>\"Ci sono offerte sotto target?\"</i>\n"
        "Oppure digita /help per la guida completa."
    )


def answer_with_gemini(
    query: str,
    bom: List[Dict[str, Any]],
    history: Dict[str, Any],
    api_key: str,
) -> Optional[str]:
    """Invoke Google Gemini 2.5 Flash API with BOM and history context."""
    if not api_key:
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

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

    system_instruction = (
        "Sei un assistente AI specializzato nel monitoraggio dei prezzi di distinte base / assemblaggi.\n"
        "Rispondi alle domande dell'utente in italiano usando ESCLUSIVAMENTE i dati forniti nel contesto.\n"
        "Se l'utente chiede della configurazione più conveniente o del costo totale, usa i dati di 'cheapest_calculated_build'. "
        "Indica quale opzione è stata scelta per ciascuna categoria, il prezzo, lo store e il totale finale.\n"
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
) -> str:
    """
    Main query resolution entry point.
    Tries deterministic local engine for state mutations & common intents,
    falls back to Gemini AI for complex natural conversational requests.
    """
    bom, history = load_engine_data(bom_path, history_path)
    if not bom:
        return "⚠️ Errore: distinta base (bom.json) non trovata o vuota."

    local_reply = classify_and_answer_local(query, bom, history, history_path=history_path)
    if not local_reply.startswith("🤔 Non ho compreso"):
        return local_reply

    api_key = gemini_api_key or os.environ.get("GEMINI_API_KEY")
    if api_key:
        llm_reply = answer_with_gemini(query, bom, history, api_key)
        if llm_reply:
            return llm_reply

    return local_reply
