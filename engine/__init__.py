"""
Price Tracker: Modular & Domain-Agnostic Price Tracking & Assembly Optimization Engine.
"""

from .tracker import (
    load_bom,
    load_price_history,
    save_price_history,
    parse_price,
    extract_prices_from_html,
    fetch_source_prices,
    load_cookies_config,
    load_telegram_config,
    send_telegram_notification,
    evaluate_item,
    format_telegram_message,
    format_aggregated_telegram_message,
    mark_item_purchased,
    mark_item_returned,
    get_build_status,
    get_bom_categories,
    run_tracker,
)

from .query_engine import (
    calculate_cheapest_build,
    search_items,
    get_active_deals,
    classify_and_answer_local,
    format_build_reply,
    format_build_status_reply,
    format_deals_reply,
    format_item_reply,
    format_help_reply,
    answer_query,
)

__version__ = "1.0.0"
__all__ = [
    "load_bom",
    "load_price_history",
    "save_price_history",
    "parse_price",
    "extract_prices_from_html",
    "fetch_source_prices",
    "load_cookies_config",
    "load_telegram_config",
    "send_telegram_notification",
    "evaluate_item",
    "format_telegram_message",
    "format_aggregated_telegram_message",
    "mark_item_purchased",
    "mark_item_returned",
    "get_build_status",
    "get_bom_categories",
    "run_tracker",
    "calculate_cheapest_build",
    "search_items",
    "get_active_deals",
    "classify_and_answer_local",
    "format_build_reply",
    "format_build_status_reply",
    "format_deals_reply",
    "format_item_reply",
    "format_help_reply",
    "answer_query",
]
