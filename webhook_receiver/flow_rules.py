from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from config import FlowConfig


@dataclass(frozen=True)
class FlowSignal:
    direction: str | None
    signal_type: str
    institutional: float
    retail: float
    price: float
    gap: float
    label: str
    source: str


@dataclass(frozen=True)
class FlowDecision:
    allowed: bool
    contracts: int
    reason: str
    signal: FlowSignal
    notifications: tuple[str, ...] = ()


@dataclass
class FlowState:
    trading_date: date | None = None
    colors_seen_today: set[str] = field(default_factory=set)
    retail_color_at_open: str | None = None
    institutional_at_open: float | None = None
    session: str | None = None
    eth_long_taken: bool = False
    eth_short_taken: bool = False
    rth_long_taken: bool = False
    rth_short_taken: bool = False
    pm3_warned: bool = False
    yellow_warned: bool = False
    warned_deeply_aligned: bool = False
    warned_no_entries: bool = False


class FlowSignalError(ValueError):
    pass


def _text(data: Mapping[str, object], key: str, fallback: str = "") -> str:
    value = data.get(key, fallback)
    return str(value).strip() if value is not None else fallback


def _number(data: Mapping[str, object], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            try:
                return float(value)
            except (TypeError, ValueError) as exc:
                raise FlowSignalError(f"{key} must be numeric.") from exc
    return default


def parse_flow_signal(data: Mapping[str, object]) -> FlowSignal:
    merged: dict[str, object] = dict(data)
    context = data.get("context")
    if isinstance(context, Mapping):
        for key, value in context.items():
            merged.setdefault(str(key), value)
    nested_signal = data.get("signal")
    if isinstance(nested_signal, Mapping):
        for key, value in nested_signal.items():
            merged.setdefault(str(key), value)

    side = _text(merged, "side").lower()
    kind = _text(merged, "kind", _text(merged, "variant")).lower()
    color = _text(merged, "color").lower()
    label = _text(merged, "label")
    institutional = _number(merged, "instValue", "inst", "instFlow")
    retail = _number(merged, "retailValue", "retail", "retailFlow")

    if side in {"long", "below"} or color == "green" or "long" in kind:
        direction = "long"
    elif side in {"short", "above"} or color == "red" or "short" in kind:
        direction = "short"
    else:
        direction = None

    if "extreme" in kind or "extreme" in label.lower():
        signal_type = f"extreme_{direction}" if direction else "extreme"
    elif "cross" in kind:
        signal_type = f"cross_{direction}" if direction else "cross"
    else:
        signal_type = kind or "unknown"

    return FlowSignal(
        direction=direction,
        signal_type=signal_type,
        institutional=institutional,
        retail=retail,
        price=_number(merged, "price", "currentPrice", "spxPrice"),
        gap=_number(merged, "gap", default=retail - institutional),
        label=label,
        source=_text(merged, "source", "extension-overlay").lower(),
    )


class FlowRuleEngine:
    def __init__(
        self,
        config: FlowConfig,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._config = config
        self._timezone = ZoneInfo(config.timezone)
        self._now_provider = now_provider
        self._state = FlowState()
        self._lock = threading.Lock()

    def evaluate(self, signal: FlowSignal) -> FlowDecision:
        with self._lock:
            now = self._now()
            self._check_resets(now)
            return self._evaluate_locked(signal, now)

    def release_reservation(self, direction: str | None) -> None:
        if direction not in {"long", "short"}:
            return
        with self._lock:
            session = self._state.session
            if session == "ETH":
                setattr(self._state, f"eth_{direction}_taken", False)
            elif session == "RTH":
                setattr(self._state, f"rth_{direction}_taken", False)

    def reset_current_session(self) -> str:
        with self._lock:
            now = self._now()
            self._check_resets(now)
            session = self._session(now)
            if session == "ETH":
                self._state.eth_long_taken = False
                self._state.eth_short_taken = False
            elif session == "RTH":
                self._state.rth_long_taken = False
                self._state.rth_short_taken = False
            return session

    def status(self) -> dict[str, object]:
        with self._lock:
            now = self._now()
            self._check_resets(now)
            state = self._state
            return {
                "status": "running",
                "session": self._session(now),
                "time_et": now.strftime("%H:%M:%S %Z"),
                "day_skipped": False,
                "colors_seen": sorted(state.colors_seen_today),
                "eth_long_taken": state.eth_long_taken,
                "eth_short_taken": state.eth_short_taken,
                "rth_long_taken": state.rth_long_taken,
                "rth_short_taken": state.rth_short_taken,
                "cboe_mute": self._is_cboe_mute(now),
                "no_new_entries": self._no_new_entries(now),
            }

    def _now(self) -> datetime:
        if self._now_provider is not None:
            current = self._now_provider()
            return current.astimezone(self._timezone)
        return datetime.now(self._timezone)

    def _check_resets(self, now: datetime) -> None:
        current_date = now.date()
        if self._state.trading_date != current_date:
            self._state = FlowState(trading_date=current_date)

        current_session = self._session(now)
        if self._state.session != current_session:
            self._state.session = current_session

    @staticmethod
    def _session(now: datetime) -> str:
        if now.time() < time(9, 30):
            return "ETH"
        if now.hour >= 16:
            return "AFTER"
        return "RTH"

    def _retail_color(self, retail: float) -> str:
        if retail > self._config.retail_green_min:
            return "green"
        if retail < self._config.retail_red_max:
            return "red"
        return "yellow"

    def _is_cboe_mute(self, now: datetime) -> bool:
        start = time.fromisoformat(self._config.cboe_mute_start)
        end = time.fromisoformat(self._config.cboe_mute_end)
        return start <= now.time().replace(tzinfo=None) < end

    def _no_new_entries(self, now: datetime) -> bool:
        return self._session(now) == "RTH" and now.hour >= self._config.no_new_entries_hour

    def _blocked(
        self,
        signal: FlowSignal,
        reason: str,
        notifications: list[str] | None = None,
    ) -> FlowDecision:
        return FlowDecision(
            allowed=False,
            contracts=0,
            reason=reason,
            signal=signal,
            notifications=tuple(notifications or ()),
        )

    def _evaluate_locked(self, signal: FlowSignal, now: datetime) -> FlowDecision:
        state = self._state
        color = self._retail_color(signal.retail)
        notifications: list[str] = []

        state.colors_seen_today.add(color)
        if state.institutional_at_open is None:
            state.institutional_at_open = signal.institutional
        if state.retail_color_at_open is None:
            state.retail_color_at_open = color

        if color == "yellow":
            if not state.yellow_warned:
                notifications.append(
                    "⚠️ **SIGNAL BLOCKED** — Retail is YELLOW "
                    f"(between {self._config.retail_red_max:g} and "
                    f"{self._config.retail_green_min:g})\n"
                    "Rules PM-1 + 14: This signal is blocked; the next signal will be checked."
                )
                state.yellow_warned = True
            return self._blocked(
                signal,
                "PM-1/14: Yellow retail — signal blocked",
                notifications,
            )

        state.yellow_warned = False

        institutional_open = state.institutional_at_open
        if (
            institutional_open is not None
            and abs(institutional_open) > self._config.rth_extreme_band + 5
        ):
            return self._blocked(signal, "PM-2: INST overextended at open — wait for range")

        if color == "green" and institutional_open is not None and institutional_open > 0:
            if not state.pm3_warned:
                notifications.append(
                    f"⚠️ **WAIT** — INST already positive at open ({institutional_open:.1f})\n"
                    "Rule PM-3: Cross already happened. Wait for INST to pull back."
                )
                state.pm3_warned = True
            return self._blocked(signal, "PM-3: INST already crossed at open", notifications)

        if self._is_cboe_mute(now):
            return self._blocked(signal, "Rule 7: CBOE mute window 9:44-9:50 ET")

        if self._no_new_entries(now):
            state.warned_no_entries = True
            return self._blocked(signal, "Rule 22: After 13:00 ET — no new entries")

        if self._session(now) == "AFTER":
            return self._blocked(signal, "After hours — no trading")

        direction = signal.direction
        if direction is None:
            return self._blocked(signal, "No clear direction in signal")

        mixed_flow = len(state.colors_seen_today) > 1
        counter_trend = (color == "green" and direction == "short") or (
            color == "red" and direction == "long"
        )
        counter_trend_exception = (
            mixed_flow and self._session(now) == "RTH" and "extreme" in signal.signal_type
        )
        if counter_trend and not counter_trend_exception:
            return self._blocked(
                signal,
                f"Rule 2: Retail {color.upper()} — no {direction}s allowed",
            )

        if "cross" in signal.signal_type:
            if direction == "long" and signal.institutional >= signal.retail:
                return self._blocked(signal, "Rule 8: INST not coming from below retail")
            if direction == "short" and signal.institutional <= signal.retail:
                return self._blocked(signal, "Rule 8: INST not coming from above retail")

        if abs(signal.institutional) < self._config.zone_min_threshold:
            return self._blocked(
                signal,
                f"Rule 9: INST ({signal.institutional:.1f}) not in zone "
                f"(±{self._config.zone_min_threshold:g})",
            )

        session = self._session(now)
        already_taken = bool(getattr(state, f"{session.lower()}_{direction}_taken"))
        if already_taken:
            return self._blocked(
                signal,
                f"Rule 11: {session} {direction} already taken",
            )

        if len(state.colors_seen_today) == 1 and "extreme" in signal.signal_type:
            if (color == "green" and direction == "short") or (
                color == "red" and direction == "long"
            ):
                return self._blocked(
                    signal,
                    f"Rule 16: {color.title()} all day — no counter-trend "
                    f"{direction} extremes",
                )

        deeply_aligned = (
            abs(signal.institutional) > self._config.deeply_aligned
            and abs(signal.retail) > self._config.deeply_aligned
            and ((signal.institutional > 0) == (signal.retail > 0))
        )
        if deeply_aligned and "extreme" in signal.signal_type:
            if not state.warned_deeply_aligned:
                notifications.append(
                    "⚠️ **NO FADE** — Both flows deeply aligned\n"
                    f"INST: {signal.institutional:.1f} · Retail: {signal.retail:.1f}\n"
                    "Rule 20: No counter-trend fading on one-sided day."
                )
                state.warned_deeply_aligned = True
            return self._blocked(
                signal,
                "Rule 20: Both flows deeply aligned — no fading",
                notifications,
            )

        contracts = self._config.base_contracts
        if color == "red" and signal.institutional > 0 and direction == "long":
            contracts = max(1, contracts // 2)
        if abs(signal.retail) < self._config.retail_zero_zone:
            contracts = max(1, contracts // 2)

        setattr(state, f"{session.lower()}_{direction}_taken", True)
        reason = (
            f"{signal.signal_type} | retail={signal.retail:.1f}({color}) "
            f"inst={signal.institutional:.1f} gap={signal.gap:.1f}"
        )
        return FlowDecision(True, contracts, reason, signal, tuple(notifications))
