from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from config import FlowConfig
from flow_rules import FlowRuleEngine, FlowSignalError, parse_flow_signal


ET = ZoneInfo("America/New_York")


class FlowRuleEngineTests(unittest.TestCase):
    def test_valid_cross_is_reserved_once_per_session(self) -> None:
        now = datetime(2026, 8, 5, 10, 0, tzinfo=ET)
        engine = FlowRuleEngine(FlowConfig(), lambda: now)
        signal = parse_flow_signal(
            {
                "side": "long",
                "kind": "cross",
                "instValue": -15,
                "retailValue": 10,
            }
        )

        first = engine.evaluate(signal)
        second = engine.evaluate(signal)

        self.assertTrue(first.allowed)
        self.assertEqual(first.contracts, 1)
        self.assertFalse(second.allowed)
        self.assertIn("Rule 11", second.reason)

    def test_failed_order_can_release_session_reservation(self) -> None:
        now = datetime(2026, 8, 5, 10, 0, tzinfo=ET)
        engine = FlowRuleEngine(FlowConfig(), lambda: now)
        signal = parse_flow_signal(
            {
                "side": "long",
                "kind": "cross",
                "instValue": -15,
                "retailValue": 10,
            }
        )

        self.assertTrue(engine.evaluate(signal).allowed)
        engine.release_reservation("long")
        self.assertTrue(engine.evaluate(signal).allowed)

    def test_yellow_retail_blocks_only_current_signal(self) -> None:
        now = datetime(2026, 8, 5, 10, 0, tzinfo=ET)
        engine = FlowRuleEngine(FlowConfig(), lambda: now)
        yellow = parse_flow_signal(
            {"side": "long", "kind": "cross", "instValue": -15, "retailValue": 0}
        )
        green = parse_flow_signal(
            {"side": "long", "kind": "cross", "instValue": -15, "retailValue": 10}
        )

        first = engine.evaluate(yellow)
        second = engine.evaluate(green)

        self.assertIn("PM-1/14", first.reason)
        self.assertFalse(first.allowed)
        self.assertTrue(second.allowed)

    def test_yellow_discord_notifies_once_per_streak(self) -> None:
        now = datetime(2026, 8, 5, 10, 0, tzinfo=ET)
        engine = FlowRuleEngine(FlowConfig(), lambda: now)
        yellow = parse_flow_signal(
            {"side": "long", "kind": "cross", "instValue": -15, "retailValue": 0.5}
        )
        green = parse_flow_signal(
            {"side": "long", "kind": "cross", "instValue": -15, "retailValue": 10}
        )

        first = engine.evaluate(yellow)
        second = engine.evaluate(yellow)
        third = engine.evaluate(yellow)
        after_green = engine.evaluate(green)
        yellow_again = engine.evaluate(yellow)

        self.assertEqual(len(first.notifications), 1)
        self.assertEqual(len(second.notifications), 0)
        self.assertEqual(len(third.notifications), 0)
        self.assertTrue(after_green.allowed)
        self.assertEqual(len(yellow_again.notifications), 1)

    def test_retail_minus_four_point_nine_is_red_not_yellow(self) -> None:
        now = datetime(2026, 8, 5, 10, 0, tzinfo=ET)
        engine = FlowRuleEngine(FlowConfig(), lambda: now)
        signal = parse_flow_signal(
            {
                "side": "short",
                "kind": "cross",
                "instValue": 15,
                "retailValue": -4.9,
            }
        )

        decision = engine.evaluate(signal)

        self.assertTrue(decision.allowed)
        self.assertNotIn("PM-1/14", decision.reason)

    def test_retail_within_plus_minus_three_is_yellow(self) -> None:
        now = datetime(2026, 8, 5, 10, 0, tzinfo=ET)
        engine = FlowRuleEngine(FlowConfig(), lambda: now)
        signal = parse_flow_signal(
            {
                "side": "long",
                "kind": "cross",
                "instValue": -15,
                "retailValue": -2.9,
            }
        )

        decision = engine.evaluate(signal)

        self.assertFalse(decision.allowed)
        self.assertIn("PM-1/14", decision.reason)

    def test_cboe_window_blocks_signal(self) -> None:
        now = datetime(2026, 8, 5, 9, 45, tzinfo=ET)
        engine = FlowRuleEngine(FlowConfig(), lambda: now)
        signal = parse_flow_signal(
            {"side": "long", "kind": "cross", "instValue": -15, "retailValue": 10}
        )

        decision = engine.evaluate(signal)

        self.assertFalse(decision.allowed)
        self.assertIn("Rule 7", decision.reason)

    def test_non_numeric_flow_value_is_rejected(self) -> None:
        with self.assertRaises(FlowSignalError):
            parse_flow_signal(
                {"side": "long", "instValue": "not-a-number", "retailValue": 10}
            )


if __name__ == "__main__":
    unittest.main()
