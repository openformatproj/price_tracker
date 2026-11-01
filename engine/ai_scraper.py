#!/usr/bin/env python3
"""
AI-Powered Semantic Web Scraping and Self-Healing Extraction Module.
Uses Google Gemini with Structured JSON Outputs to extract exact product prices,
validate variants/condition, and suggest new CSS selectors when layouts change.
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

logger = logging.getLogger(__name__)

# Default recommended models per Gemini API guidelines
DEFAULT_AI_SCRAPER_MODEL = "gemini-3.5-flash-lite"
FALLBACK_AI_SCRAPER_MODEL = "gemini-3.8-flash"


def get_gemini_api_key(config_path: Optional[str] = None) -> Optional[str]:
    """
    Retrieve Gemini API key from environment variable GEMINI_API_KEY
    or from telegram_config.json / tracker_config.json.
    """
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if key:
        return key

    paths_to_check = [config_path] if config_path else []
    paths_to_check.extend(["telegram_config.json", "tracker_config.json"])

    for path in paths_to_check:
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    val = data.get("gemini_api_key") or data.get("google_api_key")
                    if val and not val.startswith("YOUR_"):
                        return val
            except Exception:
                pass
    return None

# JSON Schema for Gemini Structured Output
AI_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "matched": {
            "type": "boolean",
            "description": "True if an exact or compatible match for the target product was found. False if only unrelated products, accessories, or out-of-stock items were found.",
        },
        "matched_product_title": {
            "type": "string",
            "description": "The exact title of the product offer found on the page.",
        },
        "best_price": {
            "type": "number",
            "description": "The lowest price in EUR for the matched product in brand-new condition (or as requested).",
        },
        "currency": {
            "type": "string",
            "description": "Currency symbol or code (e.g. EUR, €).",
        },
        "seller_or_store": {
            "type": "string",
            "description": "Name of the merchant or store offering this price (e.g. Amazon, Alternate, BPM Power, etc.).",
        },
        "condition": {
            "type": "string",
            "enum": ["new", "refurbished", "used", "unknown"],
            "description": "Condition of the item (prefer 'new').",
        },
        "in_stock": {
            "type": "boolean",
            "description": "True if the item is in stock and available for purchase.",
        },
        "is_exact_variant": {
            "type": "boolean",
            "description": "True if the key technical specifications match (e.g. 16GB VRAM, 12-core, AM5 socket, DDR5-6000 CL30).",
        },
        "suggested_css_selector": {
            "type": "string",
            "description": "A specific CSS selector or element path that contains this price element, to allow self-healing in future runs.",
        },
        "notes": {
            "type": "string",
            "description": "Brief explanation of how the price was determined, including any cheaper accessories or irrelevant listings rejected.",
        },
    },
    "required": ["matched", "best_price", "in_stock", "is_exact_variant"],
}


def prune_html_for_ai(html: str, max_chars: int = 15000) -> str:
    """
    Prune and normalize raw HTML down to meaningful product and price content.
    Strips scripts, styles, navigation, footer, SVG, and boilerplate to save tokens and latency.
    """
    if not html:
        return ""

    if BeautifulSoup is None:
        # Fallback regex-based stripping if BeautifulSoup is unavailable
        cleaned = re.sub(r"<(script|style|svg|noscript|header|footer|nav)[^>]*>[\s\S]*?</\1>", "", html, flags=re.I)
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned[:max_chars]

    soup = BeautifulSoup(html, "html.parser")

    # Remove non-content tags
    for tag in soup(["script", "style", "svg", "noscript", "header", "footer", "nav", "iframe", "form", "aside"]):
        tag.decompose()

    # Look for likely product or offer containers first
    target_containers = soup.select(
        "main, article, div[class*='product'], div[class*='item'], div[class*='offer'], div[class*='listing'], table[class*='price']"
    )

    if target_containers:
        # Extract text from detected content containers
        text_parts = []
        for c in target_containers[:10]:
            t = c.get_text(separator=" ", strip=True)
            if t:
                text_parts.append(t)
        combined = "\n\n".join(text_parts)
    else:
        # Fallback to whole body
        body = soup.find("body") or soup
        combined = body.get_text(separator=" ", strip=True)

    # Normalize whitespace
    combined = re.sub(r"[ \t]+", " ", combined)
    combined = re.sub(r"\n\s*\n+", "\n\n", combined).strip()

    if len(combined) > max_chars:
        # Keep head and tail to catch top deals and summary
        return combined[:max_chars]

    return combined


def extract_price_with_ai(
    item: Dict[str, Any],
    source: Dict[str, Any],
    html: str,
    api_key: Optional[str] = None,
    model: str = DEFAULT_AI_SCRAPER_MODEL,
    timeout: int = 20,
) -> Tuple[Optional[float], Optional[str], Optional[Dict[str, Any]]]:
    """
    Extract price and metadata from pruned HTML using Google Gemini with Structured Output.
    
    Returns:
        (price, error_message, full_ai_response_dict)
    """
    effective_api_key = api_key or get_gemini_api_key()
    if not effective_api_key:
        return None, "GEMINI_API_KEY not configured for AI scraping", None

    pruned_content = prune_html_for_ai(html)
    if not pruned_content or len(pruned_content) < 30:
        return None, "Page content empty or blocked after pruning", None

    item_name = item.get("name", item.get("id", "Unknown Item"))
    item_desc = item.get("description", "")
    target_price = item.get("target_price", 0.0)
    store = source.get("store", "Store")
    url = source.get("url", "")

    system_instruction = (
        "You are an expert e-commerce data extraction AI.\n"
        "Your task is to analyze the text/HTML of an e-commerce page and extract the exact lowest purchase price "
        "for a specific requested product.\n\n"
        "Strict rules:\n"
        "1. Identify ONLY offers that match the exact requested product or its explicit specifications.\n"
        "2. Do NOT select cheaper accessories, cables, thermal paste, brackets, or unrelated items.\n"
        "3. Prefer brand-new ('new') items in stock. Ignore out-of-stock or used/refurbished items unless no new option exists.\n"
        "4. Return prices as a clean numeric float in EUR.\n"
        "5. If the product is not found or only accessories are present, set matched=false and best_price=0.0.\n"
        "6. Provide a suggested CSS selector if you can infer the DOM element or class containing the price."
    )

    user_prompt = (
        f"Target Product to Find:\n"
        f"- Name: {item_name}\n"
        f"- Category: {item.get('category', 'Hardware')}\n"
        f"- Description/Specs: {item_desc}\n"
        f"- Target Budget Reference: €{target_price:.2f}\n"
        f"- Store / Website: {store} ({url})\n\n"
        f"Page Content (Extracted text & offers):\n"
        f"\"\"\"\n{pruned_content}\n\"\"\"\n\n"
        f"Extract the exact best price and metadata adhering strictly to the JSON schema."
    )

    endpoint_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={effective_api_key}"

    payload = {
        "contents": [
            {
                "parts": [{"text": user_prompt}]
            }
        ],
        "systemInstruction": {
            "parts": [{"text": system_instruction}]
        },
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 800,
            "responseMimeType": "application/json",
            "responseSchema": AI_EXTRACTION_SCHEMA,
        },
    }

    try:
        resp = requests.post(endpoint_url, json=payload, timeout=timeout)
        if resp.status_code != 200:
            error_details = resp.text[:300]
            logger.error("Gemini API error (HTTP %s): %s", resp.status_code, error_details)
            return None, f"Gemini API HTTP {resp.status_code}: {error_details}", None

        data = resp.json()
        raw_text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        if not raw_text:
            return None, "Empty response from Gemini", None

        parsed = json.loads(raw_text)

        if not parsed.get("matched"):
            reason = parsed.get("notes") or "AI could not match target product in page content"
            return None, reason, parsed

        price = parsed.get("best_price")
        if price is None or float(price) <= 0:
            return None, "AI extracted non-positive price", parsed

        return float(price), None, parsed

    except requests.exceptions.RequestException as e:
        return None, f"Network error calling Gemini API: {e}", None
    except json.JSONDecodeError as e:
        return None, f"Failed to parse Gemini structured JSON: {e}", None
    except Exception as e:
        return None, f"Unexpected error during AI extraction: {e}", None
