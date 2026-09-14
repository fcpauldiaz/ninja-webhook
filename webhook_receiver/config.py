from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from paths import config_path


@dataclass
class SierraConfig:
    host: str = "127.0.0.1"
    port: int = 11099
    trade_account: str = "Sim1"
    symbol: str = "ESU26-CME"
    exchange: str = ""
    quantity: int = 1
    username: str = ""
    password: str = ""
    heartbeat_interval_sec: int = 10
    connect_timeout_sec: float = 5.0
    response_wait_sec: float = 2.0
    symbol_map: dict[str, str] = field(default_factory=dict)


@dataclass
class FlowConfig:
    enabled: bool = True
    discord_webhook_url: str = ""
    symbol: str = "ES1!"
    contract_label: str = "MES 09-26"
    base_contracts: int = 1
    stop_loss_ticks: int = 25
    profit_target_ticks: int = 32
    timezone: str = "America/New_York"
    eth_extreme_band: float = 30.0
    rth_extreme_band: float = 40.0
    zone_min_threshold: float = 10.0
    retail_green_min: float = 3.0
    retail_red_max: float = -3.0
    retail_zero_zone: float = 8.0
    no_new_entries_hour: int = 13
    cboe_mute_start: str = "09:44"
    cboe_mute_end: str = "09:50"
    deeply_aligned: float = 20.0


@dataclass
class OptionsConfig:
    enabled: bool = False
    webhook_url: str = ""
    api_key: str = ""
    timeout_sec: float = 20.0


@dataclass
class AppConfig:
    host: str = "127.0.0.1"
    port: int = 5088
    # ninjatrader | sierrachart | both
    target: str = "ninjatrader"
    dry_run: bool = True
    enable_trading: bool = True
    max_quantity: int = 1
    allowed_symbols: list[str] = field(default_factory=list)
    allowed_actions: list[str] = field(
        default_factory=lambda: ["BUY", "SELL", "EXIT_LONG", "EXIT_SHORT", "FLATTEN"]
    )
    allowed_order_types: list[str] = field(default_factory=lambda: ["MARKET"])
    tcp_host: str = "127.0.0.1"
    tcp_port: int = 7077
    connect_timeout_sec: float = 3.0
    dedupe_window_seconds: int = 300
    entry_cooldown_seconds: int = 300
    trading_hours_enabled: bool = False
    trading_hours_timezone: str = "America/New_York"
    trading_hours_start: str = "09:30"
    trading_hours_end: str = "16:00"
    symbol_map: dict[str, str] = field(default_factory=dict)
    sierra: SierraConfig = field(default_factory=SierraConfig)
    flow: FlowConfig = field(default_factory=FlowConfig)
    options: OptionsConfig = field(default_factory=OptionsConfig)


def _parse_target(raw: Any) -> str:
    value = str(raw or "ninjatrader").strip().lower()
    aliases = {
        "nt": "ninjatrader",
        "ninja": "ninjatrader",
        "ninjatrader": "ninjatrader",
        "sc": "sierrachart",
        "sierra": "sierrachart",
        "sierrachart": "sierrachart",
        "both": "both",
    }
    if value not in aliases:
        raise ValueError(
            f"Invalid target '{raw}'. Use ninjatrader, sierrachart, or both."
        )
    return aliases[value]


def load_config(path: Path | None = None) -> AppConfig:
    cfg_path = path or config_path()
    raw: dict[str, Any] = {}
    if cfg_path.exists():
        # utf-8-sig tolerates a BOM written by PowerShell or installer tooling.
        raw = json.loads(cfg_path.read_text(encoding="utf-8-sig"))

    webhook = raw.get("webhook", {})
    risk = raw.get("risk", {})
    tcp = raw.get("tcp", {})
    dedupe = raw.get("dedupe", {})
    hours = raw.get("trading_hours", {})
    sierra_raw = raw.get("sierra", {})
    flow_raw = raw.get("flow", {})
    options_raw = raw.get("options", {})
    symbol_map = {str(k): str(v) for k, v in raw.get("symbol_map", {}).items()}

    sierra = SierraConfig(
        host=str(sierra_raw.get("host", "127.0.0.1")),
        port=int(sierra_raw.get("port", 11099)),
        trade_account=str(sierra_raw.get("trade_account", "Sim1")),
        symbol=str(sierra_raw.get("symbol", "ESU26-CME")),
        exchange=str(sierra_raw.get("exchange", "")),
        quantity=int(sierra_raw.get("quantity", 1)),
        username=str(sierra_raw.get("username", "")),
        password=str(sierra_raw.get("password", "")),
        heartbeat_interval_sec=int(sierra_raw.get("heartbeat_interval_sec", 10)),
        connect_timeout_sec=float(sierra_raw.get("connect_timeout_sec", 5.0)),
        response_wait_sec=float(sierra_raw.get("response_wait_sec", 2.0)),
        symbol_map={str(k): str(v) for k, v in sierra_raw.get("symbol_map", {}).items()},
    )
    flow = FlowConfig(
        enabled=bool(flow_raw.get("enabled", True)),
        discord_webhook_url=str(flow_raw.get("discord_webhook_url", "")),
        symbol=str(flow_raw.get("symbol", "ES1!")),
        contract_label=str(flow_raw.get("contract_label", "MES 09-26")),
        base_contracts=int(flow_raw.get("base_contracts", 1)),
        stop_loss_ticks=int(flow_raw.get("stop_loss_ticks", 25)),
        profit_target_ticks=int(flow_raw.get("profit_target_ticks", 32)),
        timezone=str(flow_raw.get("timezone", "America/New_York")),
        eth_extreme_band=float(flow_raw.get("eth_extreme_band", 30)),
        rth_extreme_band=float(flow_raw.get("rth_extreme_band", 40)),
        zone_min_threshold=float(flow_raw.get("zone_min_threshold", 10)),
        retail_green_min=float(flow_raw.get("retail_green_min", 3)),
        retail_red_max=float(flow_raw.get("retail_red_max", -3)),
        retail_zero_zone=float(flow_raw.get("retail_zero_zone", 8)),
        no_new_entries_hour=int(flow_raw.get("no_new_entries_hour", 13)),
        cboe_mute_start=str(flow_raw.get("cboe_mute_start", "09:44")),
        cboe_mute_end=str(flow_raw.get("cboe_mute_end", "09:50")),
        deeply_aligned=float(flow_raw.get("deeply_aligned", 20)),
    )
    options_url = os.environ.get(
        "OPTIONS_WEBHOOK_URL",
        str(options_raw.get("webhook_url", "")),
    ).strip()
    options_api_key = os.environ.get(
        "OPTIONS_API_KEY",
        str(options_raw.get("api_key", "")),
    ).strip()
    options = OptionsConfig(
        enabled=bool(options_raw.get("enabled", False) or options_url),
        webhook_url=options_url,
        api_key=options_api_key,
        timeout_sec=float(options_raw.get("timeout_sec", 20)),
    )

    return AppConfig(
        host=str(raw.get("host", "127.0.0.1")),
        port=int(raw.get("port", 5088)),
        target=_parse_target(raw.get("target", "ninjatrader")),
        dry_run=bool(webhook.get("dry_run", True)),
        enable_trading=bool(risk.get("enable_trading", True)),
        max_quantity=int(risk.get("max_quantity", 1)),
        allowed_symbols=[str(s) for s in risk.get("allowed_symbols", [])],
        allowed_actions=[str(s).upper() for s in risk.get("allowed_actions", [])],
        allowed_order_types=[str(s).upper() for s in risk.get("allowed_order_types", ["MARKET"])],
        tcp_host=str(tcp.get("host", "127.0.0.1")),
        tcp_port=int(tcp.get("port", 7077)),
        connect_timeout_sec=float(tcp.get("connect_timeout_sec", 3.0)),
        dedupe_window_seconds=int(dedupe.get("window_seconds", 300)),
        entry_cooldown_seconds=int(dedupe.get("entry_cooldown_seconds", 300)),
        trading_hours_enabled=bool(hours.get("enabled", False)),
        trading_hours_timezone=str(hours.get("timezone", "America/New_York")),
        trading_hours_start=str(hours.get("start", "09:30")),
        trading_hours_end=str(hours.get("end", "16:00")),
        symbol_map=symbol_map,
        sierra=sierra,
        flow=flow,
        options=options,
    )


class DuplicateCommandCache:
    def __init__(self, window_seconds: int) -> None:
        self._window = max(1, window_seconds)
        self._seen: dict[str, float] = {}
        self._lock = threading.Lock()
        self._last_prune = 0.0

    def try_accept(self, command_id: str) -> bool:
        now = time.time()
        with self._lock:
            self._prune_if_needed(now)
            previous = self._seen.get(command_id)
            if previous is not None and now - previous < self._window:
                return False
            self._seen[command_id] = now
            return True

    def _prune_if_needed(self, now: float) -> None:
        if now - self._last_prune < 30:
            return
        expired = [key for key, ts in self._seen.items() if now - ts >= self._window]
        for key in expired:
            self._seen.pop(key, None)
        self._last_prune = now


class EntryCooldown:
    """Reject repeated BUY/SELL entries while a cooldown is active for that action."""

    def __init__(self, cooldown_seconds: int) -> None:
        self._cooldown = max(0, cooldown_seconds)
        self._last_entry: dict[str, float] = {}
        self._lock = threading.Lock()

    def try_accept(self, action: str) -> tuple[bool, str | None]:
        action = (action or "").upper()
        if action not in {"BUY", "SELL"} or self._cooldown <= 0:
            return True, None

        now = time.time()
        with self._lock:
            previous = self._last_entry.get(action)
            if previous is not None:
                elapsed = now - previous
                if elapsed < self._cooldown:
                    remaining = int(self._cooldown - elapsed) + 1
                    return False, (
                        f"Entry cooldown active for {action} "
                        f"({remaining}s remaining; window={self._cooldown}s)."
                    )
            self._last_entry[action] = now
            # Opposite side clears so a reverse signal is not blocked forever.
            opposite = "SELL" if action == "BUY" else "BUY"
            self._last_entry.pop(opposite, None)
            return True, None


def within_trading_hours(config: AppConfig) -> tuple[bool, str | None]:
    if not config.trading_hours_enabled:
        return True, None

    tz = ZoneInfo(config.trading_hours_timezone)
    local_now = datetime.now(tz).time()
    start = dt_time.fromisoformat(config.trading_hours_start)
    end = dt_time.fromisoformat(config.trading_hours_end)

    if start <= end:
        open_now = start <= local_now <= end
    else:
        open_now = local_now >= start or local_now <= end

    if open_now:
        return True, None

    return False, (
        f"Outside trading hours ({config.trading_hours_start}-{config.trading_hours_end} "
        f"{config.trading_hours_timezone})."
    )
