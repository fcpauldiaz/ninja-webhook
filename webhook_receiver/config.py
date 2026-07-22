from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from paths import config_path


@dataclass
class AppConfig:
    host: str = "127.0.0.1"
    port: int = 5088
    secret: str = "change-me-now"
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
    trading_hours_enabled: bool = False
    trading_hours_timezone: str = "America/New_York"
    trading_hours_start: str = "09:30"
    trading_hours_end: str = "16:00"
    symbol_map: dict[str, str] = field(default_factory=dict)


def load_config(path: Path | None = None) -> AppConfig:
    cfg_path = path or config_path()
    raw: dict[str, Any] = {}
    if cfg_path.exists():
        raw = json.loads(cfg_path.read_text(encoding="utf-8"))

    webhook = raw.get("webhook", {})
    risk = raw.get("risk", {})
    tcp = raw.get("tcp", {})
    dedupe = raw.get("dedupe", {})
    hours = raw.get("trading_hours", {})
    symbol_map = {str(k): str(v) for k, v in raw.get("symbol_map", {}).items()}

    return AppConfig(
        host=str(raw.get("host", "127.0.0.1")),
        port=int(raw.get("port", 5088)),
        secret=str(webhook.get("secret", "")),
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
        trading_hours_enabled=bool(hours.get("enabled", False)),
        trading_hours_timezone=str(hours.get("timezone", "America/New_York")),
        trading_hours_start=str(hours.get("start", "09:30")),
        trading_hours_end=str(hours.get("end", "16:00")),
        symbol_map=symbol_map,
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
