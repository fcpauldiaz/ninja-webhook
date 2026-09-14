from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from paths import bundled_resource, config_path

FALLBACK_CONFIG: dict[str, Any] = {
    "host": "127.0.0.1",
    "port": 5088,
    "target": "ninjatrader",
    "webhook": {"dry_run": False},
    "flow": {
        "enabled": True,
        "discord_webhook_url": "",
        "symbol": "ES1!",
        "contract_label": "MES 09-26",
        "base_contracts": 1,
        "stop_loss_ticks": 25,
        "profit_target_ticks": 32,
        "timezone": "America/New_York",
    },
    "options": {
        "enabled": False,
        "webhook_url": "",
        "api_key": "",
        "timeout_sec": 20,
    },
    "risk": {
        "enable_trading": True,
        "max_quantity": 1,
        "allowed_symbols": [],
        "allowed_actions": ["BUY", "SELL", "EXIT_LONG", "EXIT_SHORT", "FLATTEN"],
        "allowed_order_types": ["MARKET"],
    },
    "tcp": {"host": "127.0.0.1", "port": 7077, "connect_timeout_sec": 3.0},
    "sierra": {
        "host": "127.0.0.1",
        "port": 11099,
        "trade_account": "Sim1",
        "symbol": "ESU26-CME",
        "quantity": 1,
    },
    "dedupe": {"window_seconds": 300, "entry_cooldown_seconds": 300},
    "trading_hours": {
        "enabled": False,
        "timezone": "America/New_York",
        "start": "09:30",
        "end": "16:00",
    },
    "symbol_map": {},
}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _load_defaults() -> dict[str, Any]:
    defaults = bundled_resource("config.defaults.json")
    if not defaults.exists():
        return FALLBACK_CONFIG
    try:
        return json.loads(defaults.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return FALLBACK_CONFIG


def _fill_missing(current: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    merged = dict(current)
    for key, default_value in defaults.items():
        current_value = merged.get(key)
        if key not in merged:
            merged[key] = default_value
        elif isinstance(default_value, dict) and isinstance(current_value, dict):
            merged[key] = _fill_missing(current_value, default_value)
    return merged


def ensure_config_file() -> Path:
    """Create config.json, or top up an older one with newly added settings."""
    dest = config_path()
    defaults = _load_defaults()

    if not dest.exists():
        _write_json(dest, defaults)
        return dest

    try:
        current = json.loads(dest.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return dest

    if not isinstance(current, dict):
        return dest

    merged = _fill_missing(current, defaults)
    if merged != current:
        _write_json(dest, merged)
    return dest
