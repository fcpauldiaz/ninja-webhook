from __future__ import annotations

import json
import socketserver
import threading
import unittest
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from zoneinfo import ZoneInfo

from fastapi import BackgroundTasks

import main
from config import DuplicateCommandCache, EntryCooldown
from flow_rules import FlowRuleEngine


class _Request:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    async def json(self) -> dict[str, object]:
        return self._payload


class _FuturesHandler(socketserver.BaseRequestHandler):
    received: list[bytes] = []

    def handle(self) -> None:
        self.received.append(self.request.recv(65536))


class _OptionsHandler(BaseHTTPRequestHandler):
    requests: list[dict[str, object]] = []

    def do_POST(self) -> None:
        length = int(self.headers["Content-Length"])
        self.requests.append(
            {
                "path": self.path,
                "authorization": self.headers.get("Authorization"),
                "body": json.loads(self.rfile.read(length)),
            }
        )
        body = b'{"status":"filled","trade_id":"trade-1"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return None


class OptionsGatingTests(unittest.IsolatedAsyncioTestCase):
    async def test_options_send_only_after_allowed_futures_order(self) -> None:
        _FuturesHandler.received = []
        _OptionsHandler.requests = []
        futures_server = socketserver.TCPServer(("127.0.0.1", 0), _FuturesHandler)
        options_server = HTTPServer(("127.0.0.1", 0), _OptionsHandler)
        futures_thread = threading.Thread(target=futures_server.serve_forever, daemon=True)
        options_thread = threading.Thread(target=options_server.serve_forever, daemon=True)
        futures_thread.start()
        options_thread.start()

        original_runtime = (
            main.config.dry_run,
            main.config.target,
            main.config.tcp_port,
            main.dedupe,
            main.entry_cooldown,
            main.flow_engine,
        )
        original_options = (
            main.config.options.enabled,
            main.config.options.webhook_url,
            main.config.options.api_key,
        )
        try:
            main.config.dry_run = False
            main.config.target = "ninjatrader"
            main.config.tcp_port = futures_server.server_address[1]
            main.config.options.enabled = True
            main.config.options.webhook_url = (
                f"http://127.0.0.1:{options_server.server_address[1]}"
            )
            main.config.options.api_key = "device-key"
            main.dedupe = DuplicateCommandCache(300)
            main.entry_cooldown = EntryCooldown(0)
            now = datetime(2026, 8, 5, 10, 0, tzinfo=ZoneInfo("America/New_York"))
            main.flow_engine = FlowRuleEngine(main.config.flow, lambda: now)
            payload: dict[str, object] = {
                "id": "gated-signal-1",
                "side": "long",
                "kind": "cross",
                "price": 6325,
                "instValue": -15,
                "retailValue": 10,
                "source": "extension-overlay",
            }

            allowed = await main.flow_signal(_Request(payload), BackgroundTasks())
            blocked = await main.flow_signal(_Request(payload), BackgroundTasks())
            allowed_body = json.loads(allowed.body)
            blocked_body = json.loads(blocked.body)

            self.assertEqual("traded", allowed_body["status"])
            self.assertEqual("filled", allowed_body["options"]["status"])
            self.assertEqual("blocked", blocked_body["status"])
            self.assertEqual(1, len(_FuturesHandler.received))
            self.assertEqual(1, len(_OptionsHandler.requests))
            self.assertEqual("/v1/ingest", _OptionsHandler.requests[0]["path"])
            self.assertEqual(
                "Bearer device-key",
                _OptionsHandler.requests[0]["authorization"],
            )
        finally:
            futures_server.shutdown()
            options_server.shutdown()
            futures_server.server_close()
            options_server.server_close()
            (
                main.config.dry_run,
                main.config.target,
                main.config.tcp_port,
                main.dedupe,
                main.entry_cooldown,
                main.flow_engine,
            ) = original_runtime
            (
                main.config.options.enabled,
                main.config.options.webhook_url,
                main.config.options.api_key,
            ) = original_options


if __name__ == "__main__":
    unittest.main()
