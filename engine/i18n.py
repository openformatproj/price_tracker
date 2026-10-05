#!/usr/bin/env python3
"""
Centralized internationalization (i18n) and localized message repository.
Supports Italian ('it') and English ('en') with configurable project-level overrides.
"""

import json
import os
from typing import Any, Dict, Optional

DEFAULT_LANG = "en"

CATEGORY_ICONS: Dict[str, str] = {
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

DEFAULT_ICONS = CATEGORY_ICONS

CATEGORY_NAMES: Dict[str, Dict[str, str]] = {
    "it": {
        "gpu": "Scheda Video",
        "cpu": "Processore",
        "cooler": "Dissipatore",
        "mobo": "Scheda Madre",
        "motherboard": "Scheda Madre",
        "ram": "RAM",
        "memory": "Memoria RAM",
        "psu": "Alimentatore",
        "power": "Alimentatore",
        "case": "Case",
        "storage": "Archiviazione",
        "ssd": "SSD",
        "hdd": "Disco Rigido",
        "fan": "Ventole",
        "monitor": "Monitor",
    },
    "en": {
        "gpu": "GPU",
        "cpu": "CPU",
        "cooler": "Cooler",
        "mobo": "Motherboard",
        "motherboard": "Motherboard",
        "ram": "RAM",
        "memory": "Memory",
        "psu": "Power Supply",
        "power": "Power Supply",
        "case": "Case",
        "storage": "Storage",
        "ssd": "SSD",
        "hdd": "Hard Drive",
        "fan": "Fans",
        "monitor": "Monitor",
    },
}

MESSAGES: Dict[str, Dict[str, str]] = {
    "it": {
        # General / Status
        "starting_check": "🔍 Avvio monitoraggio prezzi - {timestamp}",
        "dry_run_banner": "⚠️  MODALITÀ DRY RUN: Nessuna notifica verrà inviata, lo storico non verrà salvato.",
        "completed_slots_header": "📦 Slot già completati ({count} categorie): {categories}",
        "item_purchased_banner": "✅ ACQUISTATO a €{price:.2f} - Monitoraggio sospeso",
        "slot_fulfilled_banner": "Slot '{category}' già coperto da {name} a €{price:.2f} - Monitoraggio sospeso",
        "target_label": "Target",
        "no_prices_detected": "⚠️ Nessun prezzo rilevato tra le sorgenti per questo articolo.",
        "tag_below_target": "🎯 SOTTO TARGET",
        "tag_new_lowest": "📉 NUOVO MINIMO (prec: {prev})",
        "tag_price_drop": "🔻 ULTERIORE CALO",
        "alert_queued": "🔔 Alert aggiunto alla coda ({reason})",
        "no_alert_needed": "ℹ️ Nessun alert necessario ({reason})",
        "alerts_collected": "📬 Raccolti {count} alert.",
        "dry_run_preview": "  ⚠️ DRY RUN: Anteprima notifica aggregata:",
        "no_alerts_triggered": "ℹ️ Nessun alert attivato durante questa esecuzione.",
        "check_finished": "🏁 Verifica prezzi terminata.",
        "history_saved": "Storico prezzi salvato in {path}",
        "bom_not_found": "File distinta base non trovato: {path}",

        # Telegram Notifications
        "digest_header": (
            "🚨 <b>Price Tracker Alert Digest</b>\n"
            "📅 <i>{date}</i>\n\n"
            "Trovate <b>{count} {deal_word}</b> sotto target o a un nuovo minimo storico:\n"
        ),
        "deal_word_single": "offerta",
        "deal_word_plural": "offerte",
        "digest_status_below_target": "   🎯 <i>Sotto la soglia target desiderata!</i>\n",
        "digest_status_new_lowest": "   📉 <i>Nuovo minimo storico! (Prec: {prev})</i>\n",
        "open_offer_link": '   🔗 <a href="{url}">Apri offerta</a>\n',
        "single_alert_header": (
            "🚨 <b>Price Alert!</b>\n\n"
            "📦 <b>{item_name}</b>{category_info}\n\n"
            "💰 <b>Prezzo Rilevato:</b> €{best_price:.2f}\n"
            "🎯 <b>Prezzo Target:</b> €{target_price:.2f} ({diff_str})\n"
            "🏬 <b>Store:</b> {best_store}"
        ),
        "single_alert_below_target": "🎯 <i>Il prezzo è sceso sotto la tua soglia target!</i>",
        "single_alert_new_lowest": "📉 <i>Nuovo minimo storico assoluto! (Precedente: {prev_str})</i>",
        "single_alert_open_link": '\n🔗 <a href="{url}">Apri offerta su {store}</a>',
        "telegram_test_msg": (
            "🤖 <b>Price Tracker Test</b>\n\n"
            "Tutto configurato correttamente! Il bot è pronto a inviarti notifiche sui prezzi dei componenti."
        ),
        "unauthorized_access": "⛔ <b>Accesso non autorizzato.</b> Questo bot è configurato come privato.",

        # Purchases & Returns
        "item_not_found_in_bom": "Componente '{item_id}' non trovato nella distinta base.",
        "purchase_success_record": "Componente '{name}' registrato come acquistato a €{price:.2f}.",
        "return_success_record": "Reso registrato: '{name}' è stato reimpostato per il monitoraggio attivo.",
        "purchase_bot_reply": (
            "✅ <b>Componente segnato come acquistato!</b>\n\n"
            "📦 <b>{name}</b>\n"
            "💰 <b>Prezzo d'acquisto registrato:</b> €{price:.2f}\n"
            "⏸️ <i>Il monitoraggio dei prezzi per la categoria <b>{category}</b> è stato sospeso.</i>"
        ),
        "return_bot_reply": (
            "🔄 <b>Reso registrato con successo!</b>\n\n"
            "📦 <b>{name}</b>\n"
            "▶️ <i>Il monitoraggio dei prezzi per la categoria <b>{category}</b> è stato riattivato.</i>"
        ),

        # Build Status & Budget
        "status_title": "📊 <b>Stato Avanzamento Build ({completed}/{total} acquistati)</b>\n",
        "status_cli_title": "📊 Avanzamento Build: {completed}/{total} Slot Completati",
        "purchased_header": "✅ Componenti Acquistati:",
        "purchased_header_html": "✅ <b>Componenti Acquistati:</b>",
        "spent_so_far": "💰 Totale Speso Finora: €{spent:.2f}",
        "spent_so_far_html": "  ↳ 💰 <i>Speso finora:</i> <b>€{spent:.2f}</b>\n",
        "pending_header": "⏳ Componenti Mancanti (Migliore Offerta Attuale):",
        "pending_header_html": "⏳ <b>Da Acquistare (Miglior offerta attuale):</b>",
        "remaining_estimated": "⏳ Rimanente Stimato: €{pending:.2f}",
        "remaining_estimated_html": "  ↳ ⏳ <i>Rimanente stimato:</i> <b>€{pending:.2f}</b>\n",
        "total_estimated": "💰 Totale Finale Stimato: €{total:.2f}",
        "total_estimated_html": "💰 <b>Costo Totale Finale Stimato:</b> <b>€{total:.2f}</b>",
        "target_budget": "🎯 Budget Obiettivo:       €{target:.2f} ({diff_str})",
        "target_budget_html": "🎯 <b>Budget Target:</b> €{target:.2f} ({diff_str})",

        # Build Reply
        "build_reply_title": (
            "🖥️ <b>Configurazione Più Conveniente Attuale</b>\n"
            "<i>Combinazione ottimale delle opzioni intercambiabili:</i>\n"
        ),
        "opt_abbr": "Opz.",
        "badge_purchased": "Acquistato!",
        "badge_below_target": "Sotto target!",
        "badge_target_estimate": "Stima target",
        "current_total_label": "Totale Attuale:",
        "target_total_label": "Totale Target:",
        "diff_vs_target_suffix": "rispetto all'obiettivo",

        # Deals & Search
        "deals_title": "🎯 <b>Offerte & Minimi Rilevati ({count} trovate):</b>\n",
        "no_deals": (
            "ℹ️ <b>Nessuna offerta speciale attiva al momento.</b>\n\n"
            "Tutti i componenti rilevati si trovano attualmente sopra le soglie target impostate."
        ),
        "no_matches_found": "❌ Nessun componente corrispondente trovato nella distinta base.",
        "target_budget_reply": (
            "🎯 <b>Budget Target Complessivo:</b> <b>€{total:.2f}</b>\n\n"
            "Assumendo di raggiungere i prezzi target impostati per l'opzione più economica di ogni categoria."
        ),
        "help_reply": (
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
        ),
        "fallback_not_understood": (
            "🤔 Non ho compreso con certezza la tua richiesta.\n\n"
            "Prova a chiedermi ad esempio:\n"
            "• <i>\"Ho comprato la CPU a 316.76€\"</i>\n"
            "• <i>\"Cosa ho comprato finora?\"</i>\n"
            "• <i>\"Qual è la configurazione più conveniente?\"</i>\n"
            "• <i>\"Quanto costa il processore?\"</i>\n"
            "• <i>\"Ci sono offerte sotto target?\"</i>\n"
            "Oppure digita /help per la guida completa."
        ),

        # Extra Formatters & CLI
        "digest_item_block": (
            "<b>{idx}. {item_name}</b>{category_str}\n"
            "   💰 <b>Prezzo:</b> €{best_price:.2f} su <b>{best_store}</b>\n"
            "   🎯 <b>Target:</b> €{target_price:.2f} ({diff_str})\n"
            "{status_line}"
            "{link_str}"
        ),
        "category_option_str": " ({category} - opzione {option_index})",
        "category_digest_str": " (<i>{category} - opzione {opt_idx}</i>)",
        "store_preposition": "su",
        "store_purchased": "Acquistato",
        "badge_new_lowest": "Minimo Storico",
        "deal_item_line": "• <b>{name}</b> ({badge})\n  💰 <b>€{price:.2f}</b> su {link} | Target: €{target:.2f} ({diff_str})",
        "item_reply_header": "📦 <b>{name}</b>\n🏷️ <i>Categoria: {category} (Opzione {option_index})</i>\n🎯 <b>Target:</b> €{target:.2f}",
        "item_reply_purchased": "✅ <b>Stato: ACQUISTATO a €{price:.2f}</b>",
        "item_reply_last_price": "💰 <b>Ultimo Prezzo:</b> <b>€{price:.2f}</b> su {link} {diff_str}",
        "item_reply_not_detected": "💰 <b>Ultimo Prezzo:</b> <i>Non ancora rilevato</i>",
        "item_reply_lowest": "📉 <b>Minimo Storico:</b> €{price:.2f}",
        "cli_question_label": "🔍 Domanda: {query}\n",
        "cli_test_telegram_testing": "Verifica credenziali Telegram da {config}...",
        "cli_test_telegram_success": "✅ Notifica di test inviata con successo! Controlla la tua app Telegram.",
        "cli_test_telegram_failure": "❌ Invio notifica di test fallito. Verifica bot_token e chat_id nel file di configurazione.",
        "bom_empty_or_not_found": "⚠️ Errore: distinta base ({path}) non trovata o vuota.",
    },
    "en": {
        # General / Status
        "starting_check": "🔍 Starting Price Check - {timestamp}",
        "dry_run_banner": "⚠️  DRY RUN MODE: No notifications will be sent, history will not be saved.",
        "completed_slots_header": "📦 Completed slots ({count} categories): {categories}",
        "item_purchased_banner": "✅ PURCHASED at €{price:.2f} - Monitoring paused",
        "slot_fulfilled_banner": "Slot '{category}' already covered by {name} at €{price:.2f} - Monitoring paused",
        "target_label": "Target",
        "no_prices_detected": "⚠️ No prices detected across all sources for this item.",
        "tag_below_target": "🎯 BELOW TARGET",
        "tag_new_lowest": "📉 NEW LOWEST (prev: {prev})",
        "tag_price_drop": "🔻 PRICE DROP",
        "alert_queued": "🔔 Alert queued ({reason})",
        "no_alert_needed": "ℹ️ No alert needed ({reason})",
        "alerts_collected": "📬 Collected {count} alert(s).",
        "dry_run_preview": "  ⚠️ DRY RUN: Aggregated notification preview:",
        "no_alerts_triggered": "ℹ️ No alerts triggered during this run.",
        "check_finished": "🏁 Price check finished.",
        "history_saved": "Price history saved to {path}",
        "bom_not_found": "BOM file not found at: {path}",

        # Telegram Notifications
        "digest_header": (
            "🚨 <b>Price Tracker Alert Digest</b>\n"
            "📅 <i>{date}</i>\n\n"
            "Found <b>{count} {deal_word}</b> below target or at a new historical low:\n"
        ),
        "deal_word_single": "deal",
        "deal_word_plural": "deals",
        "digest_status_below_target": "   🎯 <i>Below desired target threshold!</i>\n",
        "digest_status_new_lowest": "   📉 <i>New historical low! (Prev: {prev})</i>\n",
        "open_offer_link": '   🔗 <a href="{url}">Open deal</a>\n',
        "single_alert_header": (
            "🚨 <b>Price Alert!</b>\n\n"
            "📦 <b>{item_name}</b>{category_info}\n\n"
            "💰 <b>Detected Price:</b> €{best_price:.2f}\n"
            "🎯 <b>Target Price:</b> €{target_price:.2f} ({diff_str})\n"
            "🏬 <b>Store:</b> {best_store}"
        ),
        "single_alert_below_target": "🎯 <i>Price dropped below your target threshold!</i>",
        "single_alert_new_lowest": "📉 <i>New all-time historical low! (Previous: {prev_str})</i>",
        "single_alert_open_link": '\n🔗 <a href="{url}">Open deal on {store}</a>',
        "telegram_test_msg": (
            "🤖 <b>Price Tracker Test</b>\n\n"
            "Everything is configured correctly! The bot is ready to send price notifications."
        ),
        "unauthorized_access": "⛔ <b>Unauthorized access.</b> This bot is configured as private.",

        # Purchases & Returns
        "item_not_found_in_bom": "Item '{item_id}' not found in BOM.",
        "purchase_success_record": "Item '{name}' recorded as purchased at €{price:.2f}.",
        "return_success_record": "Return registered: '{name}' reset to active monitoring.",
        "purchase_bot_reply": (
            "✅ <b>Item marked as purchased!</b>\n\n"
            "📦 <b>{name}</b>\n"
            "💰 <b>Recorded purchase price:</b> €{price:.2f}\n"
            "⏸️ <i>Price tracking for category <b>{category}</b> has been paused.</i>"
        ),
        "return_bot_reply": (
            "🔄 <b>Return registered successfully!</b>\n\n"
            "📦 <b>{name}</b>\n"
            "▶️ <i>Price tracking for category <b>{category}</b> has been resumed.</i>"
        ),

        # Build Status & Budget
        "status_title": "📊 <b>Build Progress ({completed}/{total} purchased)</b>\n",
        "status_cli_title": "📊 Build Progress: {completed}/{total} Slots Completed",
        "purchased_header": "✅ Purchased Components:",
        "purchased_header_html": "✅ <b>Purchased Components:</b>",
        "spent_so_far": "💰 Total Spent So Far: €{spent:.2f}",
        "spent_so_far_html": "  ↳ 💰 <i>Spent so far:</i> <b>€{spent:.2f}</b>\n",
        "pending_header": "⏳ Missing Components (Current Best Offer):",
        "pending_header_html": "⏳ <b>To Purchase (Current best offer):</b>",
        "remaining_estimated": "⏳ Estimated Remaining: €{pending:.2f}",
        "remaining_estimated_html": "  ↳ ⏳ <i>Estimated remaining:</i> <b>€{pending:.2f}</b>\n",
        "total_estimated": "💰 Total Estimated Final Cost: €{total:.2f}",
        "total_estimated_html": "💰 <b>Total Estimated Final Cost:</b> <b>€{total:.2f}</b>",
        "target_budget": "🎯 Target Budget:       €{target:.2f} ({diff_str})",
        "target_budget_html": "🎯 <b>Target Budget:</b> €{target:.2f} ({diff_str})",

        # Build Reply
        "build_reply_title": (
            "🖥️ <b>Current Most Cost-Effective Configuration</b>\n"
            "<i>Optimal combination of interchangeable options:</i>\n"
        ),
        "opt_abbr": "Opt.",
        "badge_purchased": "Purchased!",
        "badge_below_target": "Below target!",
        "badge_target_estimate": "Target estimate",
        "current_total_label": "Current Total:",
        "target_total_label": "Target Budget:",
        "diff_vs_target_suffix": "vs target",

        # Deals & Search
        "deals_title": "🎯 <b>Active Deals & Lows ({count} found):</b>\n",
        "no_deals": (
            "ℹ️ <b>No special deals active at the moment.</b>\n\n"
            "All tracked components are currently above set target thresholds."
        ),
        "no_matches_found": "❌ No matching component found in BOM.",
        "target_budget_reply": (
            "🎯 <b>Total Target Budget:</b> <b>€{total:.2f}</b>\n\n"
            "Assuming target prices are met for the cheapest option in each category."
        ),
        "help_reply": (
            "🤖 <b>Price Tracker Bot</b>\n\n"
            "You can ask me questions in <b>natural language</b> about prices, components, purchases, and builds!\n\n"
            "💡 <b>Sample questions and commands:</b>\n"
            "• <i>\"I bought the CPU for €316.76\"</i>\n"
            "• <i>\"Purchased ASUS TUF motherboard at 143.89\"</i>\n"
            "• <i>\"Returned the component\"</i>\n"
            "• <i>\"What have I bought so far?\"</i> / <i>\"Build status\"</i>\n"
            "• <i>\"What is the cheapest configuration?\"</i>\n"
            "• <i>\"How much is the processor?\"</i>\n"
            "• <i>\"Any deals below target right now?\"</i>\n\n"
            "⚡ <b>Quick commands:</b>\n"
            "• /buy &lt;item_id&gt; [price] - Mark an item as purchased\n"
            "• /return &lt;item_id&gt; - Register a return and resume tracking\n"
            "• /status - Show build progress and budget\n"
            "• /build - Show cheapest configuration\n"
            "• /deals - Show active deals below target\n"
            "• /help - Show this message"
        ),
        "fallback_not_understood": (
            "🤔 I didn't clearly understand your request.\n\n"
            "Try asking for example:\n"
            "• <i>\"I bought the CPU at 316.76€\"</i>\n"
            "• <i>\"What have I bought so far?\"</i>\n"
            "• <i>\"What is the cheapest configuration?\"</i>\n"
            "• <i>\"How much is the processor?\"</i>\n"
            "• <i>\"Are there any deals below target?\"</i>\n"
            "Or type /help for the complete guide."
        ),

        # Extra Formatters & CLI
        "digest_item_block": (
            "<b>{idx}. {item_name}</b>{category_str}\n"
            "   💰 <b>Price:</b> €{best_price:.2f} on <b>{best_store}</b>\n"
            "   🎯 <b>Target:</b> €{target_price:.2f} ({diff_str})\n"
            "{status_line}"
            "{link_str}"
        ),
        "category_option_str": " ({category} - option {option_index})",
        "category_digest_str": " (<i>{category} - option {opt_idx}</i>)",
        "store_preposition": "on",
        "store_purchased": "Purchased",
        "badge_new_lowest": "Historical Low",
        "deal_item_line": "• <b>{name}</b> ({badge})\n  💰 <b>€{price:.2f}</b> on {link} | Target: €{target:.2f} ({diff_str})",
        "item_reply_header": "📦 <b>{name}</b>\n🏷️ <i>Category: {category} (Option {option_index})</i>\n🎯 <b>Target:</b> €{target:.2f}",
        "item_reply_purchased": "✅ <b>Status: PURCHASED at €{price:.2f}</b>",
        "item_reply_last_price": "💰 <b>Last Price:</b> <b>€{price:.2f}</b> on {link} {diff_str}",
        "item_reply_not_detected": "💰 <b>Last Price:</b> <i>Not detected yet</i>",
        "item_reply_lowest": "📉 <b>All-time Low:</b> €{price:.2f}",
        "cli_question_label": "🔍 Question: {query}\n",
        "cli_test_telegram_testing": "Testing Telegram credentials from {config}...",
        "cli_test_telegram_success": "✅ Test notification successfully sent! Check your Telegram app.",
        "cli_test_telegram_failure": "❌ Test notification failed. Please verify bot_token and chat_id in telegram_config.json.",
        "bom_empty_or_not_found": "⚠️ Error: BOM file ({path}) not found or empty.",
    },
}


def resolve_lang(
    lang: Optional[str] = None,
    config_path: Optional[str] = None,
) -> str:
    """
    Determine active language code in priority order:
    1. Explicit parameter (if valid)
    2. PRICE_TRACKER_LANG environment variable
    3. 'lang' property inside config_path JSON file
    4. DEFAULT_LANG ('it')
    """
    if lang and lang.lower() in MESSAGES:
        return lang.lower()

    env_lang = os.environ.get("PRICE_TRACKER_LANG")
    if env_lang and env_lang.lower() in MESSAGES:
        return env_lang.lower()

    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                file_lang = data.get("lang")
                if file_lang and str(file_lang).lower() in MESSAGES:
                    return str(file_lang).lower()
        except Exception:
            pass
    elif os.path.exists("tracker_config.json"):
        try:
            with open("tracker_config.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                file_lang = data.get("lang")
                if file_lang and str(file_lang).lower() in MESSAGES:
                    return str(file_lang).lower()
        except Exception:
            pass

    return DEFAULT_LANG


def t(key: str, lang: Optional[str] = None, **kwargs: Any) -> str:
    """
    Retrieve translated message template and format with kwargs.
    Falls back to English or key name if missing.
    """
    actual_lang = resolve_lang(lang)
    lang_dict = MESSAGES.get(actual_lang, MESSAGES[DEFAULT_LANG])

    template = lang_dict.get(key)
    if template is None:
        template = MESSAGES.get("en", {}).get(key, key)

    if kwargs:
        try:
            return template.format(**kwargs)
        except Exception:
            return template
    return template


def get_category_label(
    category: str,
    lang: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    config_path: Optional[str] = None,
) -> str:
    """
    Return formatted category label with icon and localized name.
    e.g. '🔌 <b>Scheda Madre</b>' (it) or '🔌 <b>Motherboard</b>' (en).
    Optionally looks up custom overrides in config, config_path, or tracker_config.json.
    """
    c_lower = category.lower().strip()
    if config and "category_labels" in config:
        custom = config["category_labels"].get(c_lower)
        if custom:
            return custom
    elif config_path and os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                custom = data.get("category_labels", {}).get(c_lower)
                if custom:
                    return custom
        except Exception:
            pass
    elif os.path.exists("tracker_config.json"):
        try:
            with open("tracker_config.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                custom = data.get("category_labels", {}).get(c_lower)
                if custom:
                    return custom
        except Exception:
            pass


    actual_lang = resolve_lang(lang)
    icon = CATEGORY_ICONS.get(c_lower, "📦")

    names = CATEGORY_NAMES.get(actual_lang, CATEGORY_NAMES[DEFAULT_LANG])
    localized_name = names.get(c_lower, category.capitalize())

    return f"{icon} <b>{localized_name}</b>"

