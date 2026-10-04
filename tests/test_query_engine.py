#!/usr/bin/env python3
"""
Unit tests for query_engine.py
"""

import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from engine.query_engine import (
    calculate_cheapest_build,
    search_items,
    get_active_deals,
    classify_and_answer_local,
    format_build_reply,
    format_item_reply,
    answer_query,
)


class TestQueryEngine(unittest.TestCase):
    def setUp(self):
        self.mock_bom = [
            {
                "id": "gpu_4070_ti_super",
                "category": "gpu",
                "option_index": 0,
                "name": "GPU: NVIDIA GeForce RTX 4070 Ti Super 16GB",
                "target_price": 870.0,
                "sources": [{"store": "Trovaprezzi", "url": "https://example.com/gpu"}],
            },
            {
                "id": "cpu_ryzen_7900",
                "category": "cpu",
                "option_index": 0,
                "name": "CPU: AMD Ryzen 9 7900 (12C/24T)",
                "target_price": 310.0,
                "sources": [{"store": "Trovaprezzi", "url": "https://example.com/cpu"}],
            },
            {
                "id": "cooler_phantom_spirit",
                "category": "cooler",
                "option_index": 0,
                "name": "CPU Cooler: Thermalright Phantom Spirit 120 SE",
                "target_price": 48.0,
                "sources": [{"store": "Amazon", "url": "https://example.com/c0"}],
            },
            {
                "id": "cooler_peerless_assassin",
                "category": "cooler",
                "option_index": 1,
                "name": "CPU Cooler: Thermalright Peerless Assassin 120 SE",
                "target_price": 45.0,
                "sources": [{"store": "Trovaprezzi", "url": "https://example.com/c1"}],
            },
            {
                "id": "mobo_tomahawk",
                "category": "mobo",
                "option_index": 0,
                "name": "Motherboard: MSI MAG B650 Tomahawk WiFi",
                "target_price": 215.0,
                "sources": [{"store": "Alternate", "url": "https://example.com/m0"}],
            },
            {
                "id": "mobo_tuf",
                "category": "mobo",
                "option_index": 1,
                "name": "Motherboard: ASUS TUF GAMING B650-PLUS WIFI",
                "target_price": 205.0,
                "sources": [{"store": "Trovaprezzi", "url": "https://example.com/m1"}],
            },
            {
                "id": "ram_corsair",
                "category": "ram",
                "option_index": 0,
                "name": "RAM: Corsair Vengeance 64GB DDR5-6000",
                "target_price": 210.0,
                "sources": [{"store": "Alternate", "url": "https://example.com/r0"}],
            },
            {
                "id": "psu_bequiet",
                "category": "psu",
                "option_index": 0,
                "name": "Power Supply: be quiet! Pure Power 12 M 850W",
                "target_price": 108.0,
                "sources": [{"store": "Alternate", "url": "https://example.com/p0"}],
            },
            {
                "id": "case_lancool",
                "category": "case",
                "option_index": 0,
                "name": "PC Case: Lian Li Lancool 216",
                "target_price": 89.0,
                "sources": [{"store": "Alternate", "url": "https://example.com/k0"}],
            },
        ]

        self.mock_history = {
            "gpu_4070_ti_super": {
                "last_checked_price": 860.0,
                "last_checked_source": "Trovaprezzi",
                "last_checked_url": "https://example.com/gpu",
                "lowest_price": 860.0,
            },
            "cpu_ryzen_7900": {
                "last_checked_price": 315.0,
                "last_checked_source": "Alternate",
                "last_checked_url": "https://example.com/cpu",
                "lowest_price": 315.0,
            },
            # Phantom Spirit is 50.0, Peerless Assassin is 36.60 -> Peerless should be chosen!
            "cooler_phantom_spirit": {
                "last_checked_price": 50.0,
                "last_checked_source": "Amazon",
                "last_checked_url": "https://example.com/c0",
                "lowest_price": 50.0,
            },
            "cooler_peerless_assassin": {
                "last_checked_price": 36.60,
                "last_checked_source": "Trovaprezzi",
                "last_checked_url": "https://example.com/c1",
                "lowest_price": 36.60,
            },
            # Tomahawk is 220.0, ASUS TUF is 143.89 -> ASUS TUF should be chosen!
            "mobo_tomahawk": {
                "last_checked_price": 220.0,
                "last_checked_source": "Alternate",
                "last_checked_url": "https://example.com/m0",
            },
            "mobo_tuf": {
                "last_checked_price": 143.89,
                "last_checked_source": "Trovaprezzi",
                "last_checked_url": "https://example.com/m1",
            },
            "ram_corsair": {
                "last_checked_price": 200.0,
                "last_checked_source": "Alternate",
                "last_checked_url": "https://example.com/r0",
            },
            "psu_bequiet": {
                "last_checked_price": 105.0,
                "last_checked_source": "Alternate",
                "last_checked_url": "https://example.com/p0",
            },
            "case_lancool": {
                "last_checked_price": 85.0,
                "last_checked_source": "Alternate",
                "last_checked_url": "https://example.com/k0",
            },
        }

    def test_cheapest_build_selection(self):
        build = calculate_cheapest_build(self.mock_bom, self.mock_history)
        selected_ids = [item["item"]["id"] for item in build["items"]]

        # Verify correct alternatives selected
        self.assertIn("cooler_peerless_assassin", selected_ids)
        self.assertNotIn("cooler_phantom_spirit", selected_ids)
        self.assertIn("mobo_tuf", selected_ids)
        self.assertNotIn("mobo_tomahawk", selected_ids)

        # Expected total: 860 + 315 + 36.60 + 143.89 + 200 + 105 + 85 = 1745.49
        expected_total = 860.0 + 315.0 + 36.60 + 143.89 + 200.0 + 105.0 + 85.0
        self.assertAlmostEqual(build["total_price"], expected_total, places=2)

    def test_format_build_reply(self):
        build = calculate_cheapest_build(self.mock_bom, self.mock_history)
        reply = format_build_reply(build)
        self.assertIn("Current Most Cost-Effective Configuration", reply)
        self.assertIn("Peerless Assassin", reply)
        self.assertIn("ASUS TUF", reply)
        self.assertIn("Current Total:", reply)

        # Italian override test
        reply_it = format_build_reply(build, lang="it")
        self.assertIn("Configurazione Più Conveniente Attuale", reply_it)
        self.assertIn("Totale Attuale:", reply_it)

    def test_search_items_by_keywords(self):
        results = search_items("dissipatore peerless", self.mock_bom, self.mock_history)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["item"]["id"], "cooler_peerless_assassin")

        results_cpu = search_items("processore ryzen", self.mock_bom, self.mock_history)
        self.assertGreater(len(results_cpu), 0)
        self.assertEqual(results_cpu[0]["item"]["id"], "cpu_ryzen_7900")

    def test_classify_and_answer_local_intents(self):
        # Build query (English default)
        reply_build_en = classify_and_answer_local(
            "what is the cheapest build?",
            self.mock_bom,
            self.mock_history,
        )
        self.assertIn("Current Most Cost-Effective Configuration", reply_build_en)

        # Build query (Italian override)
        reply_build_it = classify_and_answer_local(
            "qual è la configurazione più conveniente?",
            self.mock_bom,
            self.mock_history,
            lang="it",
        )
        self.assertIn("Configurazione Più Conveniente", reply_build_it)

        # Deals query (English default)
        reply_deals_en = classify_and_answer_local(
            "any deals below target?",
            self.mock_bom,
            self.mock_history,
        )
        self.assertIn("Active Deals", reply_deals_en)

        # Deals query (Italian override)
        reply_deals_it = classify_and_answer_local(
            "ci sono offerte sotto target?",
            self.mock_bom,
            self.mock_history,
            lang="it",
        )
        self.assertIn("Offerte & Minimi", reply_deals_it)

        # Single item query
        reply_item = classify_and_answer_local(
            "quanto costa il ryzen 7900?",
            self.mock_bom,
            self.mock_history,
        )
        self.assertIn("Ryzen 9 7900", reply_item)

        # Help query
        reply_help = classify_and_answer_local(
            "/help",
            self.mock_bom,
            self.mock_history,
        )
        self.assertIn("Price Tracker Bot", reply_help)

    @patch("requests.post")
    def test_gemini_fallback_on_failure(self, mock_post):
        mock_post.side_effect = Exception("API connection timeout")

        with patch("engine.query_engine.load_engine_data") as mock_load:
            mock_load.return_value = (self.mock_bom, self.mock_history)
            # English default
            reply_en = answer_query(
                "what is the most cost-effective build?",
                gemini_api_key="fake_key_123",
            )
            self.assertIn("Current Most Cost-Effective Configuration", reply_en)

            # Italian override
            reply_it = answer_query(
                "qual è la configurazione più economica?",
                gemini_api_key="fake_key_123",
                lang="it",
            )
            self.assertIn("Configurazione Più Conveniente", reply_it)

    def test_buy_and_return_queries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hist_file = os.path.join(tmpdir, "price_history.json")
            with open(hist_file, "w", encoding="utf-8") as f:
                json.dump(self.mock_history, f)

            # 1. Natural language buy (English default)
            reply_buy_en = classify_and_answer_local(
                "i bought the cpu ryzen 7900 for 316.76€",
                self.mock_bom,
                self.mock_history,
                history_path=hist_file,
            )
            self.assertIn("Item marked as purchased", reply_buy_en)
            self.assertIn("€316.76", reply_buy_en)

            # Check history was updated
            with open(hist_file, "r", encoding="utf-8") as f:
                h = json.load(f)
            self.assertTrue(h["cpu_ryzen_7900"]["purchased"])
            self.assertEqual(h["cpu_ryzen_7900"]["purchase_price"], 316.76)

            # 2. Return query (English default)
            reply_ret_en = classify_and_answer_local(
                "returned the ryzen 7900",
                self.mock_bom,
                self.mock_history,
                history_path=hist_file,
            )
            self.assertIn("Return registered successfully", reply_ret_en)
            with open(hist_file, "r", encoding="utf-8") as f:
                h = json.load(f)
            self.assertFalse(h["cpu_ryzen_7900"]["purchased"])

            # 3. Buy and return in Italian (lang="it")
            reply_buy_it = classify_and_answer_local(
                "ho comprato la cpu ryzen 7900 a 316.76€",
                self.mock_bom,
                self.mock_history,
                history_path=hist_file,
                lang="it",
            )
            self.assertIn("Componente segnato come acquistato", reply_buy_it)

            reply_ret_it = classify_and_answer_local(
                "fatto il reso del ryzen 7900",
                self.mock_bom,
                self.mock_history,
                history_path=hist_file,
                lang="it",
            )
            self.assertIn("Reso registrato con successo", reply_ret_it)

    def test_status_query(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bom_file = os.path.join(tmpdir, "bom.json")
            hist_file = os.path.join(tmpdir, "price_history.json")
            with open(bom_file, "w", encoding="utf-8") as f:
                json.dump(self.mock_bom, f)
            with open(hist_file, "w", encoding="utf-8") as f:
                json.dump(self.mock_history, f)

            # English default
            reply_st_en = classify_and_answer_local(
                "what did i buy so far?",
                self.mock_bom,
                self.mock_history,
                history_path=hist_file,
            )
            self.assertIn("Build Progress", reply_st_en)

            # Italian override
            reply_st_it = classify_and_answer_local(
                "cosa ho comprato finora?",
                self.mock_bom,
                self.mock_history,
                history_path=hist_file,
                lang="it",
            )
            self.assertIn("Stato Avanzamento Build", reply_st_it)


if __name__ == "__main__":
    unittest.main()

