#!/usr/bin/env python3
"""
Unit tests for webhook_server.py
"""

import json
from io import BytesIO
import unittest
from unittest.mock import patch, MagicMock
from engine.webhook_server import TelegramWebhookHandler


class TestWebhookServer(unittest.TestCase):
    def setUp(self):
        TelegramWebhookHandler.token = "fake_token_123"
        TelegramWebhookHandler.allowed_chat_id = "12345678"
        TelegramWebhookHandler.gemini_key = ""

    @patch("engine.webhook_server.send_telegram_notification")
    @patch("engine.webhook_server.answer_query")
    def test_authorized_message_dispatches_answer(self, mock_answer, mock_send):
        mock_answer.return_value = "Risposta simulata build più economica"
        payload = {
            "update_id": 999,
            "message": {
                "message_id": 1,
                "chat": {"id": 12345678},
                "text": "qual è la configurazione più conveniente?"
            }
        }
        body_bytes = json.dumps(payload).encode("utf-8")
        
        handler = TelegramWebhookHandler.__new__(TelegramWebhookHandler)
        handler.headers = {"Content-Length": str(len(body_bytes))}
        handler.rfile = BytesIO(body_bytes)
        handler.wfile = BytesIO()
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        
        handler.do_POST()
        
        mock_answer.assert_called_once_with(
            "qual è la configurazione più conveniente?",
            bom_path="bom.json",
            history_path="price_history.json",
            gemini_api_key="",
        )
        mock_send.assert_called_once_with("fake_token_123", "12345678", "Risposta simulata build più economica")
        handler.send_response.assert_called_with(200)

    @patch("engine.webhook_server.send_telegram_notification")
    def test_unauthorized_message_rejected(self, mock_send):
        payload = {
            "update_id": 1000,
            "message": {
                "message_id": 2,
                "chat": {"id": 99999999},
                "text": "informazioni segrete"
            }
        }
        body_bytes = json.dumps(payload).encode("utf-8")
        
        handler = TelegramWebhookHandler.__new__(TelegramWebhookHandler)
        handler.headers = {"Content-Length": str(len(body_bytes))}
        handler.rfile = BytesIO(body_bytes)
        handler.wfile = BytesIO()
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        
        handler.do_POST()
        
        mock_send.assert_called_once()
        args, _ = mock_send.call_args
        self.assertIn("Unauthorized access", args[2])
        handler.send_response.assert_called_with(200)

        # Italian override test
        handler.lang = "it"
        handler.rfile = BytesIO(body_bytes)
        mock_send.reset_mock()
        handler.do_POST()
        args_it, _ = mock_send.call_args
        self.assertIn("Accesso non autorizzato", args_it[2])


if __name__ == "__main__":
    unittest.main()
