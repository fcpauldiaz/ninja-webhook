from __future__ import annotations

import getpass
import json
import shutil
from pathlib import Path
from typing import Any

from paths import bundled_resource, config_path

PLACEHOLDER_SECRETS = frozenset(
    {
        "",
        "change-me-now",
        "YOUR_SECRET_HERE",
    }
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def ensure_config_file() -> Path:
    dest = config_path()
    if dest.exists():
        return dest

    defaults = bundled_resource("config.defaults.json")
    if defaults.exists():
        shutil.copyfile(defaults, dest)
        return dest

    _write_json(
        dest,
        {
            "host": "127.0.0.1",
            "port": 5088,
            "webhook": {"secret": "", "dry_run": False},
            "risk": {
                "enable_trading": True,
                "max_quantity": 1,
                "allowed_symbols": [],
                "allowed_actions": ["BUY", "SELL", "EXIT_LONG", "EXIT_SHORT", "FLATTEN"],
                "allowed_order_types": ["MARKET"],
            },
            "tcp": {"host": "127.0.0.1", "port": 7077, "connect_timeout_sec": 3.0},
            "dedupe": {"window_seconds": 300},
            "trading_hours": {
                "enabled": False,
                "timezone": "America/New_York",
                "start": "09:30",
                "end": "16:00",
            },
            "symbol_map": {},
        },
    )
    return dest


def current_secret(path: Path | None = None) -> str:
    cfg = path or ensure_config_file()
    raw = _read_json(cfg)
    return str(raw.get("webhook", {}).get("secret", "")).strip()


def needs_secret_setup(path: Path | None = None) -> bool:
    return current_secret(path) in PLACEHOLDER_SECRETS


def save_secret(secret: str, path: Path | None = None) -> Path:
    cfg_path = path or ensure_config_file()
    raw = _read_json(cfg_path)
    webhook = dict(raw.get("webhook", {}))
    webhook["secret"] = secret
    raw["webhook"] = webhook
    _write_json(cfg_path, raw)
    return cfg_path


def prompt_secret(force: bool = False) -> str:
    ensure_config_file()
    if not force and not needs_secret_setup():
        return current_secret()

    print()
    print("=== WebhookNt8Bridge setup ===")
    print("Set the shared webhook secret used by TradingView / curl")
    print("(header X-Webhook-Secret). Stored in config.json next to this app.")
    print()

    while True:
        secret = getpass.getpass("Webhook secret: ").strip()
        if not secret:
            print("Secret cannot be empty.")
            continue
        if secret in PLACEHOLDER_SECRETS:
            print("Choose a unique secret, not a placeholder value.")
            continue
        confirm = getpass.getpass("Confirm secret: ").strip()
        if secret != confirm:
            print("Secrets do not match. Try again.")
            continue
        saved = save_secret(secret)
        print(f"Saved secret to {saved}")
        print()
        return secret
