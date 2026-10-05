#!/usr/bin/env python3
"""
Unit tests for centralized i18n module and multi-language support.
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from engine.i18n import (
    DEFAULT_LANG,
    MESSAGES,
    CATEGORY_NAMES,
    CATEGORY_ICONS,
    resolve_lang,
    t,
    get_category_label,
)
from engine.tracker import (
    format_telegram_message,
    format_aggregated_telegram_message,
    mark_item_purchased,
    mark_item_returned,
)
from engine.query_engine import (
    format_build_reply,
    format_build_status_reply,
    format_deals_reply,
    format_help_reply,
    classify_and_answer_local,
)
from engine.cli import main


class TestI18nCore(unittest.TestCase):
    def test_message_keys_symmetry(self):
        """Ensure all keys in Italian dictionary exist in English dictionary and vice versa."""
        it_keys = set(MESSAGES["it"].keys())
        en_keys = set(MESSAGES["en"].keys())
        self.assertEqual(
            it_keys,
            en_keys,
            f"Missing in EN: {it_keys - en_keys} | Missing in IT: {en_keys - it_keys}",
        )

    def test_category_names_symmetry(self):
        """Ensure categories translated in Italian match categories translated in English."""
        it_cats = set(CATEGORY_NAMES["it"].keys())
        en_cats = set(CATEGORY_NAMES["en"].keys())
        self.assertEqual(it_cats, en_cats)

    def test_t_function_formatting(self):
        """Ensure t() formats parameters correctly."""
        msg_it = t("target_label", lang="it")
        msg_en = t("target_label", lang="en")
        self.assertEqual(msg_it, "Target")
        self.assertEqual(msg_en, "Target")

        msg_params = t("alerts_collected", lang="it", count=3)
        self.assertIn("3", msg_params)

        msg_params_en = t("alerts_collected", lang="en", count=3)
        self.assertIn("3", msg_params_en)
        self.assertIn("Collected", msg_params_en)

    def test_t_function_fallback(self):
        """Ensure missing keys fall back gracefully."""
        self.assertEqual(t("non_existent_key_xyz"), "non_existent_key_xyz")

    def test_get_category_label(self):
        label_it = get_category_label("gpu", lang="it")
        self.assertIn("🎮", label_it)
        self.assertIn("Scheda Video", label_it)

        label_en = get_category_label("gpu", lang="en")
        self.assertIn("🎮", label_en)
        self.assertIn("GPU", label_en)

    def test_get_category_label_custom(self):
        # Custom config dictionary
        cfg = {"category_labels": {"gpu": "🚀 <b>Graphics Card</b>"}}
        self.assertEqual(get_category_label("gpu", config=cfg), "🚀 <b>Graphics Card</b>")

        # Custom config file
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"category_labels": {"cpu": "🧠 <b>Central Processing Unit</b>"}}, f)
            cfg_path = f.name
        try:
            self.assertEqual(get_category_label("cpu", config_path=cfg_path), "🧠 <b>Central Processing Unit</b>")
        finally:
            if os.path.exists(cfg_path):
                os.remove(cfg_path)


    def test_resolve_lang_priority(self):
        # 1. Default
        self.assertEqual(resolve_lang(), DEFAULT_LANG)

        # 2. Config file
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"lang": "en"}, f)
            cfg_path = f.name
        try:
            self.assertEqual(resolve_lang(config_path=cfg_path), "en")

            # 3. Environment variable overrides config file
            with patch.dict(os.environ, {"PRICE_TRACKER_LANG": "it"}):
                self.assertEqual(resolve_lang(config_path=cfg_path), "it")

            # 4. Explicit parameter overrides environment and config file
            with patch.dict(os.environ, {"PRICE_TRACKER_LANG": "it"}):
                self.assertEqual(resolve_lang(lang="en", config_path=cfg_path), "en")
        finally:
            if os.path.exists(cfg_path):
                os.remove(cfg_path)


class TestI18nFormatting(unittest.TestCase):
    def test_format_telegram_message_english(self):
        eval_res = {
            "item_name": "AMD Ryzen 9 7900",
            "category": "cpu",
            "option_index": 0,
            "best_price": 310.0,
            "target_price": 320.0,
            "best_store": "Alternate",
            "best_url": "https://example.com/cpu",
            "reason": "INITIAL_BELOW_TARGET",
            "previous_lowest": None,
        }
        msg = format_telegram_message(eval_res, lang="en")
        self.assertIn("Detected Price:", msg)
        self.assertIn("Target Price:", msg)
        self.assertIn("Price dropped below your target threshold!", msg)
        self.assertIn("Open deal on Alternate", msg)

    def test_format_aggregated_telegram_message_english(self):
        alerts = [
            {
                "item_name": "AMD Ryzen 9 7900",
                "category": "cpu",
                "option_index": 0,
                "best_price": 310.0,
                "target_price": 320.0,
                "best_store": "Alternate",
                "best_url": "https://example.com/cpu",
                "reason": "INITIAL_BELOW_TARGET",
                "previous_lowest": None,
            }
        ]
        msg = format_aggregated_telegram_message(alerts, lang="en")
        self.assertIn("Found <b>1 deal</b>", msg)
        self.assertIn("Price:", msg)
        self.assertIn("Open deal", msg)

    def test_query_engine_english_replies(self):
        # Build reply
        build_data = {
            "items": [
                {
                    "item": {"name": "AMD Ryzen 9 7900", "category": "cpu", "option_index": 0},
                    "effective_price": 310.0,
                    "target_price": 320.0,
                    "store": "Alternate",
                    "url": "https://example.com/cpu",
                    "price_type": "checked",
                }
            ],
            "total_price": 310.0,
            "total_target": 320.0,
            "diff_vs_target": -10.0,
            "categories": ["cpu"],
        }
        reply = format_build_reply(build_data, lang="en")
        self.assertIn("Current Most Cost-Effective Configuration", reply)
        self.assertIn("Current Total:", reply)
        self.assertIn("Target Budget:", reply)
        self.assertIn("vs target", reply)

        # Status reply
        status_data = {
            "completed_count": 1,
            "total_categories": 7,
            "purchased_items": [{"item": {"name": "CPU"}, "purchase_price": 310.0, "purchase_date": None}],
            "pending_categories": [],
            "total_spent": 310.0,
            "total_pending": 0.0,
            "total_estimated": 310.0,
            "total_target": 350.0,
            "diff_vs_target": -40.0,
        }
        st_reply = format_build_status_reply(status_data, lang="en")
        self.assertIn("Build Progress", st_reply)
        self.assertIn("Purchased Components:", st_reply)
        self.assertIn("Total Estimated Final Cost:", st_reply)

        # Help reply
        help_reply = format_help_reply(lang="en")
        self.assertIn("You can ask me questions in <b>natural language</b>", help_reply)

    def test_english_natural_language_queries(self):
        bom = [
            {
                "id": "cpu_ryzen",
                "category": "cpu",
                "name": "AMD Ryzen 9 7900",
                "target_price": 310.0,
            }
        ]
        history = {
            "cpu_ryzen": {
                "last_checked_price": 300.0,
                "lowest_price": 300.0,
            }
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(history, f)
            h_path = f.name

        try:
            # 1. Buy in English
            reply_buy = classify_and_answer_local(
                "i bought the cpu_ryzen at 299.99",
                bom,
                history,
                history_path=h_path,
                lang="en",
            )
            self.assertIn("Item marked as purchased!", reply_buy)
            self.assertIn("€299.99", reply_buy)

            # 2. Return in English
            reply_ret = classify_and_answer_local(
                "i returned cpu_ryzen",
                bom,
                history,
                history_path=h_path,
                lang="en",
            )
            self.assertIn("Return registered successfully!", reply_ret)

            # 3. Status in English
            reply_st = classify_and_answer_local(
                "build status",
                bom,
                history,
                history_path=h_path,
                lang="en",
            )
            self.assertIn("Build Progress", reply_st)

            # 4. Cheapest build in English
            reply_b = classify_and_answer_local(
                "what is the cheapest build?",
                bom,
                history,
                history_path=h_path,
                lang="en",
            )
            self.assertIn("Current Most Cost-Effective Configuration", reply_b)
        finally:
            if os.path.exists(h_path):
                os.remove(h_path)


class TestCLILanguage(unittest.TestCase):
    @patch("engine.cli.run_tracker")
    def test_cli_lang_flag_passed(self, mock_run):
        with patch.object(sys, "argv", ["price-tracker", "--lang", "en"]):
            main()
            mock_run.assert_called_once()
            _, kwargs = mock_run.call_args
            self.assertEqual(kwargs["lang"], "en")


if __name__ == "__main__":
    unittest.main()
