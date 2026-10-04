#!/usr/bin/env python3
"""
Unit tests for price_tracker.tracker
"""

import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

try:
    from price_tracker.tracker import (
        parse_price,
        extract_prices_from_html,
        evaluate_item,
        format_telegram_message,
        format_aggregated_telegram_message,
        load_telegram_config,
        load_price_history,
        save_price_history,
        send_telegram_notification,
        load_bom,
        mark_item_purchased,
        mark_item_returned,
        get_build_status,
        get_bom_categories,
        run_tracker,
    )
except ImportError:
    from tracker import (
        parse_price,
        extract_prices_from_html,
        evaluate_item,
        format_telegram_message,
        format_aggregated_telegram_message,
        load_telegram_config,
        load_price_history,
        save_price_history,
        send_telegram_notification,
        load_bom,
        mark_item_purchased,
        mark_item_returned,
        get_build_status,
        get_bom_categories,
        run_tracker,
    )


class TestParsePrice(unittest.TestCase):
    def test_standard_italian_format(self):
        self.assertEqual(parse_price("€ 1.250,50"), 1250.50)
        self.assertEqual(parse_price("839,00 €"), 839.00)
        self.assertEqual(parse_price("35,90 €"), 35.90)

    def test_simple_integers_and_decimals(self):
        self.assertEqual(parse_price("1250"), 1250.0)
        self.assertEqual(parse_price("839.50"), 839.50)
        self.assertEqual(parse_price("35.9"), 35.9)

    def test_thousands_separators(self):
        self.assertEqual(parse_price("1,250.50"), 1250.50)
        self.assertEqual(parse_price("1.250"), 1250.0)

    def test_dirty_text(self):
        self.assertEqual(parse_price("Spedizione inclusa: 145,99 € IVA incl."), 145.99)
        self.assertEqual(parse_price("A partire da: 99,00 €"), 99.00)
        self.assertEqual(parse_price("da 599,00 €"), 599.00)

    def test_invalid_prices(self):
        self.assertIsNone(parse_price(None))
        self.assertIsNone(parse_price(""))
        self.assertIsNone(parse_price("Non disponibile"))
        self.assertIsNone(parse_price("€ 0,00"))


class TestHtmlPriceExtraction(unittest.TestCase):
    def test_trovaprezzi_selector(self):
        html = '''
        <div class="item">
            <span class="item_price">839,00 €</span>
        </div>
        <div class="item">
            <span class="item_price">850,50 €</span>
        </div>
        '''
        prices = extract_prices_from_html(html, ".item_price")
        self.assertEqual(prices, [839.0, 850.5])

    def test_alternate_selector(self):
        html = '''
        <div class="product">
            <span class="price">€ 319,00</span>
        </div>
        '''
        prices = extract_prices_from_html(html, "span.price")
        self.assertEqual(prices, [319.0])

    def test_no_matches(self):
        html = '<div class="content"><p>Out of stock</p></div>'
        prices = extract_prices_from_html(html, ".item_price")
        self.assertEqual(prices, [])


class TestEvaluationLogic(unittest.TestCase):
    def setUp(self):
        self.item = {
            "id": "test_gpu",
            "name": "Test GPU RTX 4070 Ti Super",
            "target_price": 840.0,
        }
        self.source = {
            "store": "Trovaprezzi",
            "url": "https://example.com/gpu",
        }

    def test_initial_detection_above_target(self):
        history = {}
        res = evaluate_item(self.item, best_price=899.0, best_source=self.source, history=history)
        self.assertEqual(res["action"], "SKIP")
        self.assertEqual(res["reason"], "INITIAL_DETECTED")
        self.assertFalse(res["is_below_target"])
        self.assertTrue(res["is_new_lowest"])

    def test_initial_detection_below_target(self):
        history = {}
        res = evaluate_item(self.item, best_price=820.0, best_source=self.source, history=history)
        self.assertEqual(res["action"], "NOTIFY")
        self.assertEqual(res["reason"], "INITIAL_BELOW_TARGET")
        self.assertTrue(res["is_below_target"])

    def test_new_lowest_price(self):
        history = {
            "test_gpu": {
                "lowest_price": 890.0,
                "lowest_price_date": "2026-01-01T00:00:00",
                "last_notified_price": None,
            }
        }
        res = evaluate_item(self.item, best_price=870.0, best_source=self.source, history=history)
        self.assertEqual(res["action"], "NOTIFY")
        self.assertEqual(res["reason"], "NEW_LOWEST")
        self.assertEqual(res["previous_lowest"], 890.0)

    def test_price_drop_while_below_target(self):
        history = {
            "test_gpu": {
                "lowest_price": 820.0,
                "last_notified_price": 820.0,
            }
        }
        res = evaluate_item(self.item, best_price=800.0, best_source=self.source, history=history)
        self.assertEqual(res["action"], "NOTIFY")
        self.assertEqual(res["reason"], "PRICE_DROP")
        self.assertTrue(res["is_price_drop"])

    def test_unchanged_below_target_anti_spam(self):
        history = {
            "test_gpu": {
                "lowest_price": 820.0,
                "last_notified_price": 820.0,
            }
        }
        res = evaluate_item(self.item, best_price=820.0, best_source=self.source, history=history)
        self.assertEqual(res["action"], "SKIP")
        self.assertEqual(res["reason"], "UNCHANGED_BELOW_TARGET")

    def test_force_notify_flag(self):
        history = {
            "test_gpu": {
                "lowest_price": 820.0,
                "last_notified_price": 820.0,
            }
        }
        res = evaluate_item(self.item, best_price=820.0, best_source=self.source, history=history, force_notify=True)
        self.assertEqual(res["action"], "NOTIFY")
        self.assertEqual(res["reason"], "FORCE")


class TestTelegramFormatting(unittest.TestCase):
    def test_message_formatting(self):
        eval_res = {
            "item_name": "Test CPU",
            "category": "cpu",
            "option_index": 0,
            "best_price": 315.0,
            "target_price": 320.0,
            "best_store": "Alternate",
            "best_url": "https://example.com/cpu",
            "reason": "INITIAL_BELOW_TARGET",
            "previous_lowest": None,
        }
        msg = format_telegram_message(eval_res)
        self.assertIn("Test CPU", msg)
        self.assertIn("€315.00", msg)
        self.assertIn("Alternate", msg)
        self.assertIn("https://example.com/cpu", msg)


class TestAggregatedTelegramFormatting(unittest.TestCase):
    def test_empty_alerts(self):
        self.assertEqual(format_aggregated_telegram_message([]), "")

    def test_single_alert_aggregated(self):
        alerts = [
            {
                "item_name": "Test CPU",
                "category": "cpu",
                "option_index": 0,
                "best_price": 315.0,
                "target_price": 320.0,
                "best_store": "Alternate",
                "best_url": "https://example.com/cpu",
                "reason": "INITIAL_BELOW_TARGET",
                "previous_lowest": None,
            }
        ]
        msg = format_aggregated_telegram_message(alerts)
        self.assertIn("Trovate <b>1 offerta</b>", msg)
        self.assertIn("1. Test CPU", msg)
        self.assertIn("€315.00", msg)

    def test_multiple_alerts_aggregated(self):
        alerts = [
            {
                "item_name": "CPU Cooler",
                "category": "cooler",
                "option_index": 1,
                "best_price": 36.60,
                "target_price": 45.0,
                "best_store": "Trovaprezzi",
                "best_url": "https://example.com/c1",
                "reason": "INITIAL_BELOW_TARGET",
            },
            {
                "item_name": "Motherboard",
                "category": "mobo",
                "option_index": 2,
                "best_price": 143.89,
                "target_price": 205.0,
                "best_store": "Trovaprezzi",
                "best_url": "https://example.com/m2",
                "reason": "NEW_LOWEST",
                "previous_lowest": 180.0,
            },
        ]
        msg = format_aggregated_telegram_message(alerts)
        self.assertIn("Trovate <b>2 offerte</b>", msg)
        self.assertIn("1. CPU Cooler", msg)
        self.assertIn("2. Motherboard", msg)

    @patch("price_tracker.tracker.requests.post")
    def test_send_large_message_split(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        large_msg = "\n\n".join([f"Block {i} " + "A" * 500 for i in range(10)])
        self.assertGreater(len(large_msg), 5000)

        success = send_telegram_notification("fake_token", "fake_chat_id", large_msg)
        self.assertTrue(success)
        self.assertGreater(mock_post.call_count, 1)


class TestPurchaseTracking(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.bom_path = os.path.join(self.temp_dir.name, "bom.json")
        self.history_path = os.path.join(self.temp_dir.name, "price_history.json")

        self.mock_bom = [
            {
                "id": "cpu_ryzen_7900",
                "category": "cpu",
                "option_index": 0,
                "name": "CPU: AMD Ryzen 9 7900",
                "target_price": 305.0,
                "sources": [],
            },
            {
                "id": "mobo_aorus",
                "category": "mobo",
                "option_index": 0,
                "name": "Motherboard: Gigabyte AORUS",
                "target_price": 135.0,
                "sources": [],
            },
            {
                "id": "mobo_tuf",
                "category": "mobo",
                "option_index": 1,
                "name": "Motherboard: ASUS TUF",
                "target_price": 135.0,
                "sources": [],
            },
        ]
        with open(self.bom_path, "w", encoding="utf-8") as f:
            json.dump(self.mock_bom, f)

        self.initial_history = {
            "cpu_ryzen_7900": {"last_checked_price": 316.76, "last_checked_source": "Trovaprezzi"},
            "mobo_aorus": {"last_checked_price": 143.90, "last_checked_source": "Alternate"},
            "mobo_tuf": {"last_checked_price": 143.89, "last_checked_source": "Trovaprezzi"},
        }
        with open(self.history_path, "w", encoding="utf-8") as f:
            json.dump(self.initial_history, f)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_dynamic_categories(self):
        cats = get_bom_categories(self.mock_bom)
        self.assertEqual(cats, ["cpu", "mobo"])

    def test_mark_item_purchased_explicit_price(self):
        ok, msg, item = mark_item_purchased(
            "cpu_ryzen_7900", price=310.0, bom_path=self.bom_path, history_path=self.history_path
        )
        self.assertTrue(ok)
        self.assertIn("registrato come acquistato", msg)
        self.assertIn("€310.00", msg)

        h = load_price_history(self.history_path)
        self.assertTrue(h["cpu_ryzen_7900"]["purchased"])
        self.assertEqual(h["cpu_ryzen_7900"]["purchase_price"], 310.0)
        self.assertIn("purchase_date", h["cpu_ryzen_7900"])

    def test_mark_item_purchased_fallback_price(self):
        ok, msg, item = mark_item_purchased(
            "cpu_ryzen_7900", price=None, bom_path=self.bom_path, history_path=self.history_path
        )
        self.assertTrue(ok)
        h = load_price_history(self.history_path)
        self.assertEqual(h["cpu_ryzen_7900"]["purchase_price"], 316.76)

    def test_mark_item_returned(self):
        mark_item_purchased("cpu_ryzen_7900", price=316.76, bom_path=self.bom_path, history_path=self.history_path)
        ok, msg, item = mark_item_returned("cpu_ryzen_7900", bom_path=self.bom_path, history_path=self.history_path)
        self.assertTrue(ok)
        self.assertIn("Reso registrato", msg)

        h = load_price_history(self.history_path)
        self.assertFalse(h["cpu_ryzen_7900"]["purchased"])
        self.assertNotIn("purchase_price", h["cpu_ryzen_7900"])

    def test_get_build_status(self):
        mark_item_purchased("mobo_tuf", price=143.89, bom_path=self.bom_path, history_path=self.history_path)
        st = get_build_status(bom_path=self.bom_path, history_path=self.history_path)
        self.assertEqual(st["completed_count"], 1)
        self.assertEqual(st["total_spent"], 143.89)
        self.assertEqual(st["purchased_items"][0]["item"]["id"], "mobo_tuf")

    def test_run_tracker_skips_purchased_and_fulfilled_categories(self):
        mark_item_purchased("mobo_tuf", price=143.89, bom_path=self.bom_path, history_path=self.history_path)
        with patch("price_tracker.tracker.fetch_source_prices") as mock_fetch:
            res = run_tracker(
                bom_path=self.bom_path,
                history_path=self.history_path,
                config_path="telegram_config.example.json",
                dry_run=True,
            )
            self.assertEqual(mock_fetch.call_count, 0)


if __name__ == "__main__":
    unittest.main()
