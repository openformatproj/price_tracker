#!/usr/bin/env python3
"""
Unit tests for cli.py
"""

import sys
import unittest
from unittest.mock import patch, MagicMock

from engine.cli import main


class TestCLI(unittest.TestCase):
    @patch("engine.cli.run_tracker")
    def test_cli_default_check(self, mock_run):
        with patch.object(sys, "argv", ["price-tracker"]):
            main()
            mock_run.assert_called_once()
            _, kwargs = mock_run.call_args
            self.assertFalse(kwargs["dry_run"])

    @patch("engine.cli.run_tracker")
    def test_cli_check_subcommand_dry_run(self, mock_run):
        with patch.object(sys, "argv", ["price-tracker", "check", "--dry-run"]):
            main()
            mock_run.assert_called_once()
            _, kwargs = mock_run.call_args
            self.assertTrue(kwargs["dry_run"])

    @patch("engine.cli.run_tracker")
    def test_cli_check_with_ai_flag(self, mock_run):
        with patch.object(sys, "argv", ["price-tracker", "check", "--ai"]):
            main()
            mock_run.assert_called_once()
            _, kwargs = mock_run.call_args
            self.assertTrue(kwargs["enable_ai"])

    @patch("engine.ai_scraper.extract_price_with_ai")
    @patch("engine.tracker.load_bom")
    @patch("requests.Session")
    def test_cli_test_ai_subcommand(self, mock_session_cls, mock_load_bom, mock_extract_ai):
        mock_load_bom.return_value = [
            {
                "id": "cpu_ryzen_7900",
                "name": "AMD Ryzen 9 7900",
                "sources": [
                    {"store": "Alternate", "url": "https://example.com/cpu"}
                ]
            }
        ]
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html><div>AMD Ryzen 9 7900 - €315</div></html>"
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        mock_extract_ai.return_value = (315.0, None, {
            "matched": True,
            "matched_product_title": "AMD Ryzen 9 7900",
            "best_price": 315.0,
            "in_stock": True,
            "is_exact_variant": True,
            "suggested_css_selector": "div.price",
            "notes": "Matched CPU"
        })

        with patch.object(sys, "argv", ["price-tracker", "test-ai", "cpu_ryzen_7900"]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 0)
            mock_extract_ai.assert_called_once()

    @patch("engine.cli.run_tracker")
    def test_cli_legacy_flag_dry_run(self, mock_run):
        with patch.object(sys, "argv", ["price-tracker", "--dry-run"]):
            main()
            mock_run.assert_called_once()
            _, kwargs = mock_run.call_args
            self.assertTrue(kwargs["dry_run"])

    @patch("engine.cli.answer_query")
    def test_cli_ask_command(self, mock_ask):
        mock_ask.return_value = "Risposta simulata"
        with patch.object(sys, "argv", ["price-tracker", "ask", "quanto", "costa", "il", "ryzen?"]):
            with self.assertRaises(SystemExit) as cm:
                main()
            mock_ask.assert_called_once()
            args, kwargs = mock_ask.call_args
            self.assertEqual(args[0], "quanto costa il ryzen?")
            self.assertEqual(cm.exception.code, 0)

    @patch("engine.cli.mark_item_purchased")
    def test_cli_buy_command(self, mock_buy):
        mock_buy.return_value = (True, "Item marked as purchased", {})
        with patch.object(sys, "argv", ["price-tracker", "buy", "cpu_ryzen_7900", "315.0"]):
            with self.assertRaises(SystemExit) as cm:
                main()
            mock_buy.assert_called_once()
            args, kwargs = mock_buy.call_args
            self.assertEqual(args[0], "cpu_ryzen_7900")
            self.assertEqual(args[1], 315.0)
            self.assertEqual(cm.exception.code, 0)

    @patch("engine.cli.mark_item_returned")
    def test_cli_return_command(self, mock_ret):
        mock_ret.return_value = (True, "Item returned", {})
        with patch.object(sys, "argv", ["price-tracker", "return", "cpu_ryzen_7900"]):
            with self.assertRaises(SystemExit) as cm:
                main()
            mock_ret.assert_called_once()
            args, kwargs = mock_ret.call_args
            self.assertEqual(args[0], "cpu_ryzen_7900")
            self.assertEqual(cm.exception.code, 0)

    @patch("engine.cli.get_build_status")
    def test_cli_status_command(self, mock_status):
        mock_status.return_value = {
            "completed_count": 1,
            "total_categories": 7,
            "purchased_items": [{"item": {"name": "CPU"}, "purchase_price": 315.0}],
            "pending_categories": [],
            "total_spent": 315.0,
            "total_pending": 0.0,
            "total_estimated": 315.0,
            "total_target": 350.0,
            "diff_vs_target": -35.0,
        }
        with patch.object(sys, "argv", ["price-tracker", "status"]):
            with self.assertRaises(SystemExit) as cm:
                main()
            mock_status.assert_called_once()
            self.assertEqual(cm.exception.code, 0)

    @patch("engine.cookie_helper.refresh_browser_cookies")
    def test_cli_refresh_cookies_subcommand(self, mock_refresh):
        mock_refresh.return_value = (True, "mocked_cookie_token", None)
        with patch.object(sys, "argv", ["price-tracker", "refresh-cookies", "--headless"]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 0)
            mock_refresh.assert_called_once_with(
                url="https://www.trovaprezzi.it",
                target_domain="trovaprezzi.it",
                target_cookie="datadome",
                cookies_path="cookies.json",
                timeout=60,
                headless=True,
            )


if __name__ == "__main__":
    unittest.main()
