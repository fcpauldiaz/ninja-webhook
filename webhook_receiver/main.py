from __future__ import annotations

import argparse
import hmac
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from config import DuplicateCommandCache, load_config
from paths import config_path
from services import forward_to_ninjatrader, normalize_and_validate
from setup_wizard import prompt_secret

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("webhook")

app = FastAPI(title="WebhookNt8Bridge Receiver", version="1.0.0")
config = load_config()
dedupe = DuplicateCommandCache(config.dedupe_window_seconds)


def reload_runtime_config() -> None:
    global config, dedupe
    config = load_config()
    dedupe = DuplicateCommandCache(config.dedupe_window_seconds)


def _secrets_equal(expected: str, provided: str) -> bool:
    left = expected.encode("utf-8")
    right = provided.encode("utf-8")
    if len(left) != len(right):
        return False
    return hmac.compare_digest(left, right)


def _rejected(command_id: str | None, reason: str, status_code: int) -> JSONResponse:
    body: dict[str, Any] = {"status": "rejected", "reason": reason}
    if command_id:
        body["id"] = command_id
    return JSONResponse(body, status_code=status_code)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "utc": datetime.now(timezone.utc).isoformat()}


@app.post("/webhook")
async def webhook(
    request: Request,
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
) -> JSONResponse:
    try:
        command = await request.json()
    except Exception:
        logger.warning("Rejected: empty or invalid JSON body")
        return _rejected(None, "Invalid or empty JSON body.", 400)

    if not isinstance(command, dict):
        return _rejected(None, "Invalid or empty JSON body.", 400)

    logger.info(
        "Received command candidate id=%s source=%s symbol=%s action=%s qty=%s",
        command.get("id"),
        command.get("source"),
        command.get("symbol"),
        command.get("action"),
        command.get("quantity"),
    )

    provided_secret = x_webhook_secret or command.get("secret")
    if not config.secret or not provided_secret or not _secrets_equal(config.secret, str(provided_secret)):
        logger.warning("Rejected command %s: invalid webhook secret", command.get("id"))
        return _rejected(command.get("id"), "Invalid webhook secret.", 401)

    command.pop("secret", None)

    normalized, error = normalize_and_validate(command, config)
    if error or normalized is None:
        logger.warning("Rejected command %s: %s", command.get("id"), error)
        return _rejected(command.get("id"), error or "Validation failed.", 400)

    logger.info(
        "Validated command %s ntSymbol=%s",
        normalized["id"],
        normalized.get("ntSymbol"),
    )

    if not dedupe.try_accept(normalized["id"]):
        logger.warning("Rejected duplicate command %s", normalized["id"])
        return _rejected(normalized["id"], "Duplicate command id within dedupe window.", 409)

    if config.dry_run:
        logger.info("DryRun enabled — not forwarding command %s", normalized["id"])
        return JSONResponse(
            {
                "status": "dry_run",
                "id": normalized["id"],
                "ntSymbol": normalized.get("ntSymbol"),
            }
        )

    try:
        forward_to_ninjatrader(normalized, config)
    except OSError as exc:
        logger.exception("Failed to forward command %s", normalized["id"])
        return _rejected(
            normalized["id"],
            f"Failed to reach NinjaTrader TCP listener: {exc}",
            502,
        )

    logger.info("Accepted and forwarded command %s", normalized["id"])
    return JSONResponse(
        {
            "status": "accepted",
            "id": normalized["id"],
            "ntSymbol": normalized.get("ntSymbol"),
        }
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WebhookNt8Bridge Python receiver")
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Prompt for webhook secret (and exit after saving unless --run is also set).",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Start the server after --setup (default when --setup is omitted).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    import uvicorn

    args = _parse_args(argv)
    setup_only = args.setup and not args.run

    prompt_secret(force=args.setup)
    reload_runtime_config()

    if setup_only:
        print("Setup complete. Run again without --setup to start the receiver.")
        return

    if not config.secret:
        print("Webhook secret is not configured. Re-run with --setup.", file=sys.stderr)
        raise SystemExit(1)

    logger.info(
        "WebhookReceiver (Python) starting on http://%s:%s  DryRun=%s  config=%s",
        config.host,
        config.port,
        config.dry_run,
        config_path(),
    )
    # Pass the app object (required for PyInstaller frozen builds).
    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
