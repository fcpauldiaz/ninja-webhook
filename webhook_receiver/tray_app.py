"""
Windows system-tray shell for the NinjaTrader webhook receiver.

Runs uvicorn in a background thread with no console window. Logs go to a file
next to the EXE; the tray menu opens that log and the install folder.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pystray
import uvicorn
from PIL import Image, ImageDraw

from paths import app_dir, config_path, log_path

APP_NAME = "Trade Desky NT Receiver"
APP_NAME_COMPACT = "TradeDeskyNT"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"

logger = logging.getLogger("tray")


def setup_file_logging() -> Path:
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    handler = RotatingFileHandler(
        path,
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )
    root.addHandler(handler)
    return path


def _load_icon() -> Image.Image:
    for name in ("icon.ico", "icon.png"):
        candidate = ASSETS_DIR / name
        if candidate.exists():
            return Image.open(candidate)
    img = Image.new("RGBA", (64, 64), (250, 204, 21, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle((2, 2, 61, 61), outline=(0, 0, 0, 255), width=4)
    draw.rectangle((18, 22, 46, 42), outline=(0, 0, 0, 255), width=3)
    return img


class ReceiverTrayApp:
    def __init__(self) -> None:
        self._log_file = setup_file_logging()
        self._status = "Starting..."
        self._listen_url = ""
        self._icon: pystray.Icon | None = None
        self._server: uvicorn.Server | None = None
        self._server_thread: threading.Thread | None = None
        self._lock = threading.Lock()

        self._start_server()
        self._build_tray()

    def _set_status(self, status: str) -> None:
        self._status = status
        if self._icon:
            self._icon.title = f"{APP_NAME} — {status}"
            self._icon.update_menu()

    def _status_label(self) -> str:
        if self._listen_url:
            return f"{self._status} · {self._listen_url}"
        return self._status

    def _start_server(self) -> None:
        with self._lock:
            self._stop_server_locked()
            try:
                # Import after logging is configured so main.basicConfig is a no-op.
                import main as receiver_main
                from config import DuplicateCommandCache, EntryCooldown, load_config
                from flow_rules import FlowRuleEngine
                from setup_wizard import ensure_config_file

                ensure_config_file()
                cfg = load_config()
                receiver_main.config = cfg
                receiver_main.dedupe = DuplicateCommandCache(cfg.dedupe_window_seconds)
                receiver_main.entry_cooldown = EntryCooldown(cfg.entry_cooldown_seconds)
                receiver_main.flow_engine = FlowRuleEngine(cfg.flow)

                host = cfg.host
                port = cfg.port
                self._listen_url = f"http://{host}:{port}"
                logger.info(
                    "Starting receiver on %s target=%s dry_run=%s config=%s",
                    self._listen_url,
                    cfg.target,
                    cfg.dry_run,
                    config_path(),
                )

                config = uvicorn.Config(
                    receiver_main.app,
                    host=host,
                    port=port,
                    reload=False,
                    log_level="info",
                    log_config=None,
                )
                self._server = uvicorn.Server(config)
                self._server_thread = threading.Thread(
                    target=self._run_server,
                    name="uvicorn",
                    daemon=True,
                )
                self._server_thread.start()
                self._set_status("Listening")
            except OSError as exc:
                logger.exception("Failed to bind receiver")
                self._listen_url = ""
                self._set_status(f"Error: {exc}")
            except Exception as exc:
                logger.exception("Failed to start receiver")
                self._listen_url = ""
                self._set_status(f"Error: {exc}")

    def _run_server(self) -> None:
        server = self._server
        if server is None:
            return
        try:
            server.run()
        except Exception:
            logger.exception("Receiver server exited with error")
            self._set_status("Stopped (error)")
            return
        if self._status.startswith("Listening"):
            self._set_status("Stopped")

    def _stop_server_locked(self) -> None:
        server = self._server
        thread = self._server_thread
        if server is not None:
            server.should_exit = True
        if thread is not None and thread.is_alive():
            thread.join(timeout=5.0)
        self._server = None
        self._server_thread = None

    def _stop_server(self) -> None:
        with self._lock:
            self._stop_server_locked()
        self._set_status("Stopped")

    def _build_tray(self) -> None:
        self._icon = pystray.Icon(
            APP_NAME_COMPACT,
            _load_icon(),
            f"{APP_NAME} — {self._status}",
            menu=self._build_menu,
        )

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(lambda _: self._status_label(), None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Open logs", self._open_logs),
            pystray.MenuItem("Open config folder", self._open_config_folder),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Restart", self._restart),
            pystray.MenuItem("Quit", self._quit),
        )

    def _open_logs(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        path = self._log_file
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("", encoding="utf-8")
        if sys.platform == "win32":
            subprocess.run(["notepad.exe", str(path)], check=False)
        else:
            subprocess.run(["open", str(path)], check=False)

    def _open_config_folder(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        folder = str(app_dir())
        if sys.platform == "win32":
            os.startfile(folder)  # type: ignore[attr-defined]
        else:
            subprocess.run(["open", folder], check=False)

    def _restart(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self._set_status("Restarting...")
        self._stop_server()
        time.sleep(0.3)
        self._start_server()

    def _quit(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self._stop_server()
        if self._icon:
            self._icon.stop()

    def run(self) -> None:
        if self._icon:
            self._icon.run()


def main() -> None:
    ReceiverTrayApp().run()


if __name__ == "__main__":
    main()
