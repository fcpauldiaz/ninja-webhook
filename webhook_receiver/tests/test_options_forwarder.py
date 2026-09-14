from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from config import OptionsConfig
from flow_rules import FlowDecision, parse_flow_signal
from options_forwarder import (
    OptionsForwardError,
    build_options_envelope,
    forward_options_envelope,
)


class _Response:
    status = 200

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def read(self) -> bytes:
        return b'{"status":"filled","trade_id":"trade-1"}'


class OptionsForwarderTests(unittest.TestCase):
    def test_full_options_envelope_is_forwarded_unchanged(self) -> None:
        payload: dict[str, object] = {
            "type": "signal",
            "firedAt": "2026-07-21T15:00:00.000Z",
            "session": "rth",
            "caution": None,
            "signal": {
                "id": "signal-1",
                "time": 1721596500,
                "price": 6325,
                "shape": "circle",
                "side": "long",
                "variant": "extreme",
                "color": "green",
                "source": "extension-overlay",
            },
            "context": {
                "currentPrice": 6325,
                "gap": 3.2,
                "retailValue": 12.1,
                "instValue": -12.0,
            },
        }
        decision = FlowDecision(True, 1, "allowed", parse_flow_signal(payload))

        envelope = build_options_envelope(payload, decision, "signal-1", "rth")

        self.assertEqual(payload, envelope)

    def test_flat_flow_signal_maps_to_tradable_options_envelope(self) -> None:
        payload: dict[str, object] = {
            "id": "signal-2",
            "side": "short",
            "kind": "cross",
            "price": 6327,
            "retailValue": -12,
            "instValue": 15,
            "source": "extension-overlay",
        }
        decision = FlowDecision(True, 1, "allowed", parse_flow_signal(payload))

        envelope = build_options_envelope(payload, decision, "signal-2", "rth")
        signal = envelope["signal"]

        self.assertIsInstance(signal, dict)
        self.assertEqual("short", signal["side"])
        self.assertEqual("red", signal["color"])
        self.assertEqual(6327.0, signal["price"])
        self.assertEqual("signal-2", signal["id"])

    def test_options_are_skipped_without_original_spx_price(self) -> None:
        payload: dict[str, object] = {
            "side": "long",
            "instValue": -15,
            "retailValue": 10,
        }
        decision = FlowDecision(True, 1, "allowed", parse_flow_signal(payload))

        with self.assertRaises(OptionsForwardError):
            build_options_envelope(payload, decision, "signal-3", "rth")

    @patch("options_forwarder.urlopen", return_value=_Response())
    def test_post_uses_ingest_path_and_bearer_key(self, mocked_urlopen: object) -> None:
        config = OptionsConfig(
            enabled=True,
            webhook_url="https://receiver.example",
            api_key="device-key",
            timeout_sec=20,
        )
        envelope = {
            "type": "signal",
            "signal": {
                "id": "signal-4",
                "side": "long",
                "source": "extension-test",
                "price": 6325,
            },
        }

        result = forward_options_envelope(envelope, config)
        request = mocked_urlopen.call_args.args[0]
        sent = json.loads(request.data.decode("utf-8"))

        self.assertEqual(200, result.status_code)
        self.assertEqual("filled", result.body["status"])
        self.assertEqual("https://receiver.example/v1/ingest", request.full_url)
        self.assertEqual("Bearer device-key", request.get_header("Authorization"))
        self.assertEqual(envelope, sent)


if __name__ == "__main__":
    unittest.main()
