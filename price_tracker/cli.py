#!/usr/bin/env python3
"""
CLI entry point for Price Tracker.
"""

import argparse
import logging
import sys

try:
    from .tracker import (
        run_tracker,
        mark_item_purchased,
        mark_item_returned,
        get_build_status,
        send_telegram_notification,
        load_telegram_config,
        DEFAULT_BOM_PATH,
        DEFAULT_CONFIG_PATH,
        DEFAULT_HISTORY_PATH,
        DEFAULT_COOKIES_PATH,
    )
    from .query_engine import answer_query
    from .webhook_server import run_webhook_server
    from .i18n import t, resolve_lang
except ImportError:
    from tracker import (
        run_tracker,
        mark_item_purchased,
        mark_item_returned,
        get_build_status,
        send_telegram_notification,
        load_telegram_config,
        DEFAULT_BOM_PATH,
        DEFAULT_CONFIG_PATH,
        DEFAULT_HISTORY_PATH,
        DEFAULT_COOKIES_PATH,
    )
    from query_engine import answer_query
    from webhook_server import run_webhook_server
    from i18n import t, resolve_lang


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="price-tracker",
        description="Modular Price Tracking & Assembly Optimization Engine",
    )
    parser.add_argument(
        "--lang",
        type=str,
        choices=["it", "en"],
        default=None,
        help="Language for messages and outputs ('it' or 'en', default: resolved from config/env/it)",
    )
    parser.add_argument(
        "--bom",
        type=str,
        default=DEFAULT_BOM_PATH,
        help=f"Path to BOM JSON file (default: {DEFAULT_BOM_PATH})",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=DEFAULT_CONFIG_PATH,
        help=f"Path to Telegram credentials file (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--history",
        type=str,
        default=DEFAULT_HISTORY_PATH,
        help=f"Path to price history JSON file (default: {DEFAULT_HISTORY_PATH})",
    )
    parser.add_argument(
        "--cookies",
        type=str,
        default=DEFAULT_COOKIES_PATH,
        help=f"Path to store cookies JSON file (default: {DEFAULT_COOKIES_PATH})",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose debug logging",
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # 1. check (default when no subcommand specified)
    check_parser = subparsers.add_parser("check", help="Run scraping and price monitoring")
    check_parser.add_argument("--dry-run", action="store_true", help="Scrape without saving or alerting")
    check_parser.add_argument("--force-notify", action="store_true", help="Notify even without price drop")
    check_parser.add_argument("--item", type=str, default=None, help="Check only a specific item ID")

    # 2. ask
    ask_parser = subparsers.add_parser("ask", help="Ask a question in natural language")
    ask_parser.add_argument("query", nargs="+", help="Question text")

    # 3. buy
    buy_parser = subparsers.add_parser("buy", help="Mark a component as purchased")
    buy_parser.add_argument("item_id", help="Item ID as defined in BOM")
    buy_parser.add_argument("price", nargs="?", type=float, default=None, help="Paid price in EUR")

    # 4. return
    return_parser = subparsers.add_parser("return", help="Register a returned item")
    return_parser.add_argument("item_id", help="Item ID as defined in BOM")

    # 5. status
    subparsers.add_parser("status", help="Show build progress and budget status")

    # 6. serve
    serve_parser = subparsers.add_parser("serve", help="Run local webhook HTTP server")
    serve_parser.add_argument("--port", type=int, default=8080, help="HTTP listening port (default: 8080)")

    # 7. test-telegram
    subparsers.add_parser("test-telegram", help="Send test notification to Telegram")

    # Fallback flags for backward-compatibility with direct `python tracker.py --dry-run` etc.
    parser.add_argument("--dry-run", action="store_true", help="Scrape prices without notifying or saving")
    parser.add_argument("--force-notify", action="store_true", help="Force Telegram notifications")
    parser.add_argument("--item", type=str, default=None, help="Track only a specific item ID")
    parser.add_argument("--test-telegram", action="store_true", help="Send a test message to Telegram")
    parser.add_argument("--buy", nargs="+", metavar=("ITEM_ID", "PRICE"), help="Mark an item as purchased")
    parser.add_argument("--return", dest="return_item", metavar="ITEM_ID", help="Mark an item as returned")
    parser.add_argument("--status", action="store_true", help="Display build progress and budget status")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    actual_lang = resolve_lang(lang=args.lang, config_path=args.config)

    # Route command or legacy flags
    if args.command == "ask":
        query_text = " ".join(args.query)
        print(t("cli_question_label", lang=actual_lang, query=query_text))
        reply = answer_query(
            query_text,
            bom_path=args.bom,
            history_path=args.history,
            lang=actual_lang,
            config_path=args.config,
        )
        print(reply)
        sys.exit(0)

    if args.command == "buy" or args.buy:
        item_id = args.item_id if args.command == "buy" else args.buy[0]
        price = args.price if args.command == "buy" else (float(args.buy[1]) if len(args.buy) > 1 else None)
        ok, msg, _ = mark_item_purchased(
            item_id, price, bom_path=args.bom, history_path=args.history, lang=actual_lang
        )
        print(f"{'✅' if ok else '❌'} {msg}")
        sys.exit(0 if ok else 1)

    if args.command == "return" or args.return_item:
        item_id = args.item_id if args.command == "return" else args.return_item
        ok, msg, _ = mark_item_returned(
            item_id, bom_path=args.bom, history_path=args.history, lang=actual_lang
        )
        print(f"{'🔄' if ok else '❌'} {msg}")
        sys.exit(0 if ok else 1)

    if args.command == "status" or args.status:
        st = get_build_status(bom_path=args.bom, history_path=args.history)
        print("=" * 65)
        print(t("status_cli_title", lang=actual_lang, completed=st['completed_count'], total=st['total_categories']))
        print("=" * 65)
        if st["purchased_items"]:
            print("\n" + t("purchased_header", lang=actual_lang))
            for p in st["purchased_items"]:
                dt_str = f" ({p['purchase_date']})" if p.get("purchase_date") else ""
                print(f"  • {p['item']['name']}: €{p['purchase_price']:.2f}{dt_str}")
            print("  " + t("spent_so_far", lang=actual_lang, spent=st['total_spent']))

        if st["pending_categories"]:
            print("\n" + t("pending_header", lang=actual_lang))
            for p in st["pending_categories"]:
                print(f"  • {p['item']['category'].upper()}: {p['item']['name']} -> €{p['price']:.2f} [{p['store']}]")
            print("  " + t("remaining_estimated", lang=actual_lang, pending=st['total_pending']))

        print("\n" + "─" * 65)
        print(t("total_estimated", lang=actual_lang, total=st['total_estimated']))
        diff = st['diff_vs_target']
        diff_str = f"+€{diff:.2f}" if diff > 0 else f"-€{abs(diff):.2f}"
        print(t("target_budget", lang=actual_lang, target=st['total_target'], diff_str=diff_str))
        print("=" * 65)
        sys.exit(0)

    if args.command == "serve":
        run_webhook_server(
            port=args.port,
            config_path=args.config,
            bom_path=args.bom,
            history_path=args.history,
            lang=actual_lang,
        )
        sys.exit(0)

    if args.command == "test-telegram" or args.test_telegram:
        token, chat_id, _ = load_telegram_config(args.config)
        print(t("cli_test_telegram_testing", lang=actual_lang, config=args.config))
        test_msg = t("telegram_test_msg", lang=actual_lang)
        success = send_telegram_notification(token, chat_id, test_msg)
        if success:
            print(t("cli_test_telegram_success", lang=actual_lang))
            sys.exit(0)
        else:
            print(t("cli_test_telegram_failure", lang=actual_lang))
            sys.exit(1)

    # Default: Run tracker check
    dry_run = getattr(args, "dry_run", False)
    force_notify = getattr(args, "force_notify", False)
    target_item_id = getattr(args, "item", None)

    run_tracker(
        config_path=args.config,
        history_path=args.history,
        cookies_path=args.cookies,
        bom_path=args.bom,
        dry_run=dry_run,
        force_notify=force_notify,
        target_item_id=target_item_id,
        lang=actual_lang,
    )


if __name__ == "__main__":
    main()
