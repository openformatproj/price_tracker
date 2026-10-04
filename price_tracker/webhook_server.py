#!/usr/bin/env python3
"""
Lightweight HTTP Webhook server for local Telegram bot query testing.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import logging
import os
import sys
from typing import Optional

try:
    from .query_engine import answer_query
    from .tracker import send_telegram_notification, load_telegram_config
    from .i18n import t, resolve_lang
except ImportError:
    from query_engine import answer_query
    from tracker import send_telegram_notification, load_telegram_config
    from i18n import t, resolve_lang

logger = logging.getLogger("price_tracker.webhook_server")


class TelegramWebhookHandler(BaseHTTPRequestHandler):
    token: Optional[str] = None
    allowed_chat_id: Optional[str] = None
    gemini_key: Optional[str] = None
    bom_path: str = "bom.json"
    history_path: str = "price_history.json"
    config_path: str = "telegram_config.json"
    lang: Optional[str] = None

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)

        try:
            update = json.loads(post_data.decode("utf-8"))
        except Exception as e:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Invalid JSON")
            return

        message = update.get("message", {})
        chat = message.get("chat", {})
        chat_id = str(chat.get("id", ""))
        text = message.get("text", "").strip()

        if not text:
            self.send_response(200)
            self.end_headers()
            return

        logger.info("Received message from chat %s: %s", chat_id, text)
        actual_lang = resolve_lang(self.lang, config_path=self.config_path)

        if self.allowed_chat_id and chat_id != str(self.allowed_chat_id):
            logger.warning("Unauthorized message from chat_id %s rejected.", chat_id)
            if self.token:
                send_telegram_notification(
                    self.token,
                    chat_id,
                    t("unauthorized_access", lang=actual_lang),
                )
            self.send_response(200)
            self.end_headers()
            return

        query_kwargs = {
            "bom_path": self.bom_path,
            "history_path": self.history_path,
            "gemini_api_key": self.gemini_key,
        }
        if self.lang is not None:
            query_kwargs["lang"] = self.lang

        reply_html = answer_query(text, **query_kwargs)

        if self.token and chat_id:
            send_telegram_notification(self.token, chat_id, reply_html)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Price Tracker Webhook Server is active!\n")

    def log_message(self, format, *args):
        logger.info("%s - - [%s] %s", self.client_address[0], self.log_date_time_string(), format % args)


def run_webhook_server(
    port: int = 8080,
    config_path: str = "telegram_config.json",
    bom_path: str = "bom.json",
    history_path: str = "price_history.json",
    gemini_key: Optional[str] = None,
    lang: Optional[str] = None,
) -> None:
    """Run local HTTP server for processing Telegram Webhook requests."""
    token, chat_id, _ = load_telegram_config(config_path)

    TelegramWebhookHandler.token = token
    TelegramWebhookHandler.allowed_chat_id = chat_id
    TelegramWebhookHandler.gemini_key = gemini_key or os.environ.get("GEMINI_API_KEY")
    TelegramWebhookHandler.bom_path = bom_path
    TelegramWebhookHandler.history_path = history_path
    TelegramWebhookHandler.config_path = config_path
    TelegramWebhookHandler.lang = lang

    server_address = ("", port)
    httpd = HTTPServer(server_address, TelegramWebhookHandler)

    print(f"🚀 Telegram Webhook server listening on port {port}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Webhook server stopped.")
        httpd.server_close()
