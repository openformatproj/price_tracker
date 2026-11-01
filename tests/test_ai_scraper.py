#!/usr/bin/env python3
"""
Unit tests for AI-powered semantic scraping and self-healing extraction.
"""

import json
import os
import unittest
from unittest.mock import MagicMock, patch

import requests

from engine.ai_scraper import (
    DEFAULT_AI_SCRAPER_MODEL,
    extract_price_with_ai,
    prune_html_for_ai,
)
from engine.tracker import fetch_source_prices


class TestAiScraperPruning(unittest.TestCase):
    """Tests for HTML pruning before feeding into Gemini."""

    def test_prune_empty_html(self):
        self.assertEqual(prune_html_for_ai(""), "")
        self.assertEqual(prune_html_for_ai(None), "")

    def test_prune_strips_scripts_styles_and_boilerplate(self):
        raw_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>.banner { color: red; }</style>
            <script>console.log("analytics tracking code");</script>
        </head>
        <body>
            <header><nav><a href="/home">Home</a></nav></header>
            <main>
                <div class="product-card">
                    <h1>AMD Ryzen 9 7900 Box AM5</h1>
                    <span class="price">€ 315,00</span>
                    <p class="stock">Disponibile subito</p>
                </div>
            </main>
            <footer><p>&copy; 2026 Test Shop</p></footer>
        </body>
        </html>
        """
        pruned = prune_html_for_ai(raw_html)
        self.assertNotIn("analytics tracking code", pruned)
        self.assertNotIn(".banner { color: red; }", pruned)
        self.assertNotIn("&copy; 2026 Test Shop", pruned)
        self.assertIn("AMD Ryzen 9 7900 Box AM5", pruned)
        self.assertIn("€ 315,00", pruned)

    def test_prune_max_chars_truncation(self):
        long_html = "<div><p>" + ("Product offer text " * 1000) + "</p></div>"
        pruned = prune_html_for_ai(long_html, max_chars=200)
        self.assertLessEqual(len(pruned), 200)


class TestAiPriceExtraction(unittest.TestCase):
    """Tests for Gemini extraction with mocked responses."""

    def setUp(self):
        self.item = {
            "id": "cpu_ryzen_7900",
            "name": "AMD Ryzen 9 7900",
            "category": "cpu",
            "description": "12 cores, 24 threads, Socket AM5, 65W TDP",
            "target_price": 305.0,
        }
        self.source = {
            "store": "Alternate",
            "url": "https://example.com/item",
            "css_selector": "span.price",
        }
        self.sample_html = """
        <html>
            <body>
                <div class="product-detail">
                    <h1>AMD Ryzen 9 7900 (12C/24T, AM5)</h1>
                    <div class="price-box">€ 312,50</div>
                    <div class="availability">In stock</div>
                </div>
            </body>
        </html>
        """

    def test_missing_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            price, err, meta = extract_price_with_ai(self.item, self.source, self.sample_html, api_key=None)
            self.assertIsNone(price)
            self.assertIn("GEMINI_API_KEY not configured", err)
            self.assertIsNone(meta)

    def test_empty_html_content(self):
        price, err, meta = extract_price_with_ai(self.item, self.source, "", api_key="dummy_key")
        self.assertIsNone(price)
        self.assertIn("empty or blocked", err)

    @patch("requests.post")
    def test_successful_gemini_extraction(self, mock_post):
        ai_response_payload = {
            "matched": True,
            "matched_product_title": "AMD Ryzen 9 7900 (12C/24T, AM5)",
            "best_price": 312.50,
            "currency": "EUR",
            "seller_or_store": "Alternate",
            "condition": "new",
            "in_stock": True,
            "is_exact_variant": True,
            "suggested_css_selector": "div.price-box",
            "notes": "Matched exact CPU model in brand new condition.",
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": json.dumps(ai_response_payload)}]
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        price, err, meta = extract_price_with_ai(
            self.item, self.source, self.sample_html, api_key="dummy_key"
        )

        self.assertEqual(price, 312.50)
        self.assertIsNone(err)
        self.assertIsNotNone(meta)
        self.assertEqual(meta["suggested_css_selector"], "div.price-box")
        self.assertTrue(meta["matched"])

        # Verify Gemini endpoint and model
        call_args, call_kwargs = mock_post.call_args
        self.assertIn(DEFAULT_AI_SCRAPER_MODEL, call_args[0])
        self.assertIn("key=dummy_key", call_args[0])

    @patch("requests.post")
    def test_accessory_or_mismatch_rejected(self, mock_post):
        ai_response_payload = {
            "matched": False,
            "matched_product_title": "Thermal Paste for AMD AM5",
            "best_price": 8.50,
            "currency": "EUR",
            "seller_or_store": "Alternate",
            "condition": "new",
            "in_stock": True,
            "is_exact_variant": False,
            "suggested_css_selector": "",
            "notes": "Rejected thermal paste accessory, CPU was out of stock.",
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": json.dumps(ai_response_payload)}]
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        price, err, meta = extract_price_with_ai(
            self.item, self.source, self.sample_html, api_key="dummy_key"
        )

        self.assertIsNone(price)
        self.assertIn("Rejected thermal paste accessory", err)
        self.assertFalse(meta["matched"])

    @patch("requests.post")
    def test_gemini_api_http_error(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "API key not valid. Please pass a valid API key."
        mock_post.return_value = mock_resp

        price, err, meta = extract_price_with_ai(
            self.item, self.source, self.sample_html, api_key="invalid_key"
        )
        self.assertIsNone(price)
        self.assertIn("Gemini API HTTP 400", err)

    @patch("requests.post")
    def test_gemini_network_timeout(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")

        price, err, meta = extract_price_with_ai(
            self.item, self.source, self.sample_html, api_key="dummy_key"
        )
        self.assertIsNone(price)
        self.assertIn("Network error calling Gemini API", err)


class TestTrackerAiIntegration(unittest.TestCase):
    """Tests for fetch_source_prices AI fallback and self-healing integration."""

    def setUp(self):
        self.session = MagicMock()
        self.item = {
            "id": "cpu_ryzen_7900",
            "name": "AMD Ryzen 9 7900",
            "category": "cpu",
            "target_price": 305.0,
        }

    def test_css_selector_success_does_not_invoke_ai(self):
        # When selector matches, AI must NOT be invoked (saving tokens/latency)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '<div class="price">€ 318,00</div>'
        self.session.get.return_value = mock_resp

        source = {
            "store": "Alternate",
            "url": "https://example.com/cpu",
            "css_selector": "div.price",
        }

        with patch("engine.tracker.extract_price_with_ai") as mock_ai:
            price, err = fetch_source_prices(
                source,
                self.session,
                item=self.item,
                enable_ai=True,
                api_key="key",
            )
            self.assertEqual(price, 318.0)
            self.assertIsNone(err)
            mock_ai.assert_not_called()

    def test_css_selector_failure_falls_back_to_ai(self):
        # When selector fails, AI should be called if enable_ai=True
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        # HTML changed class from .price to .new-price-badge
        mock_resp.text = '<div class="new-price-badge">€ 311,90</div>'
        self.session.get.return_value = mock_resp

        source = {
            "store": "Alternate",
            "url": "https://example.com/cpu",
            "css_selector": "div.old-broken-selector",
        }

        with patch("engine.tracker.extract_price_with_ai") as mock_ai:
            mock_ai.return_value = (311.90, None, {"suggested_css_selector": "div.new-price-badge"})

            price, err = fetch_source_prices(
                source,
                self.session,
                item=self.item,
                enable_ai=True,
                api_key="key",
            )
            self.assertEqual(price, 311.90)
            self.assertIsNone(err)
            mock_ai.assert_called_once()

    def test_ai_only_mode(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '<div class="custom-card">AMD Ryzen 9 7900 - € 309,00</div>'
        self.session.get.return_value = mock_resp

        source = {
            "store": "Alternate",
            "url": "https://example.com/cpu",
            "ai_only": True,
        }

        with patch("engine.tracker.extract_price_with_ai") as mock_ai:
            mock_ai.return_value = (309.0, None, {"matched": True})

            price, err = fetch_source_prices(
                source,
                self.session,
                item=self.item,
                enable_ai=False,
                api_key="key",
            )
            self.assertEqual(price, 309.0)
            self.assertIsNone(err)
            mock_ai.assert_called_once()


if __name__ == "__main__":
    unittest.main()
