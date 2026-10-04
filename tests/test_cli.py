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


if __name__ == "__main__":
    unittest.main()
