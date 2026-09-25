from __future__ import annotations

import sys
from pathlib import Path


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def bundled_resource(name: str) -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / name
    return Path(__file__).resolve().parent / name


def config_path() -> Path:
    return app_dir() / "config.json"


def log_path() -> Path:
    return app_dir() / "logs" / "receiver.log"
