from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import JSONResponse

from config import DuplicateCommandCache, EntryCooldown, load_config
from flow_rules import FlowDecision, FlowRuleEngine, FlowSignalError, parse_flow_signal
from options_forwarder import (
    OptionsForwardError,
    build_options_envelope,
    forward_options_envelope,
    options_signal_id,
)
from paths import config_path
from services import forward_command, normalize_and_validate, send_discord_notification
from setup_wizard import ensure_config_file

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("webhook")

ensure_config_file()
app = FastAPI(title="WebhookNt8Bridge Receiver", version="1.2.0")
config = load_config()
dedupe = DuplicateCommandCache(config.dedupe_window_seconds)
entry_cooldown = EntryCooldown(config.entry_cooldown_seconds)
flow_engine = FlowRuleEngine(config.flow)


def _rejected(command_id: str | None, reason: str, status_code: int) -> JSONResponse:
    body: dict[str, Any] = {"status": "rejected", "reason": reason}
    if command_id:
        body["id"] = command_id
    return JSONResponse(body, status_code=status_code)


def _dispatch_command(command: dict[str, Any]) -> tuple[dict[str, Any], int]:
    normalized, error = normalize_and_validate(command, config)
    if error or normalized is None:
        logger.warning("Rejected command %s: %s", command.get("id"), error)
        return {
            "status": "rejected",
            "id": command.get("id"),
            "reason": error or "Validation failed.",
        }, 400

    logger.info(
        "Validated command %s ntSymbol=%s",
        normalized["id"],
        normalized.get("ntSymbol"),
    )

    if not dedupe.try_accept(normalized["id"]):
        logger.warning("Rejected duplicate command %s", normalized["id"])
        return {
            "status": "rejected",
            "id": normalized["id"],
            "reason": "Duplicate command id within dedupe window.",
        }, 409

    ok_cooldown, cooldown_reason = entry_cooldown.try_accept(str(normalized["action"]))
    if not ok_cooldown:
        logger.warning("Rejected command %s: %s", normalized["id"], cooldown_reason)
        return {
            "status": "rejected",
            "id": normalized["id"],
            "reason": cooldown_reason or "Entry cooldown.",
        }, 429

    if config.dry_run:
        logger.info("DryRun enabled — not forwarding command %s", normalized["id"])
        return {
            "status": "dry_run",
            "id": normalized["id"],
            "ntSymbol": normalized.get("ntSymbol"),
        }, 200

    try:
        forward_result = forward_command(normalized, config)
    except (OSError, RuntimeError) as exc:
        logger.exception("Failed to forward command %s", normalized["id"])
        return {
            "status": "rejected",
            "id": normalized["id"],
            "reason": f"Failed to reach trading target ({config.target}): {exc}",
        }, 502

    logger.info("Accepted and forwarded command %s target=%s", normalized["id"], config.target)
    body: dict[str, Any] = {
        "status": "accepted",
        "id": normalized["id"],
        "target": config.target,
        "ntSymbol": normalized.get("ntSymbol"),
    }
    if forward_result.get("scSymbol"):
        body["scSymbol"] = forward_result["scSymbol"]
    if forward_result.get("partialErrors"):
        body["partialErrors"] = forward_result["partialErrors"]
        body["status"] = "partial"
    return body, 200


def _flow_trade_alert(decision: FlowDecision, order_status: str) -> str:
    signal = decision.signal
    emoji = "🟢" if signal.direction == "long" else "🔴"
    action = "LONG" if signal.direction == "long" else "SHORT"
    order_ok = order_status in {"accepted", "partial"}
    return "\n".join(
        [
            f"## {emoji} {action} {config.flow.contract_label}",
            f"**Signal:** {decision.reason}",
            f"**Retail:** {signal.retail:.1f} · **INST:** {signal.institutional:.1f}",
            f"**Contracts:** {decision.contracts} · "
            f"SL {config.flow.stop_loss_ticks} ticks · "
            f"PT {config.flow.profit_target_ticks} ticks",
            f"**Order:** {'✅ Accepted' if order_ok else f'❌ {order_status}'}",
            f"**Session:** {flow_engine.status()['session']}",
        ]
    )


def _flow_blocked_alert(decision: FlowDecision) -> str:
    signal = decision.signal
    return (
        "🟡 **SIGNAL BLOCKED**\n"
        f"Direction: {signal.direction or '?'} · Retail: {signal.retail:.1f} · "
        f"INST: {signal.institutional:.1f}\n"
        f"**Rule:** {decision.reason}"
    )


def _queue_discord(background_tasks: BackgroundTasks, message: str) -> None:
    if config.flow.discord_webhook_url.strip():
        background_tasks.add_task(
            send_discord_notification,
            config.flow.discord_webhook_url,
            message,
        )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "utc": datetime.now(timezone.utc).isoformat()}


@app.post("/webhook")
async def webhook(request: Request) -> JSONResponse:
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

    command.pop("secret", None)
    body, status_code = _dispatch_command(command)
    return JSONResponse(body, status_code=status_code)


@app.post("/signal")
async def flow_signal(request: Request, background_tasks: BackgroundTasks) -> JSONResponse:
    if not config.flow.enabled:
        return _rejected(None, "Flow signal processing is disabled.", 404)

    try:
        payload = await request.json()
    except Exception:
        return _rejected(None, "Invalid or empty JSON body.", 400)
    if not isinstance(payload, dict):
        return _rejected(None, "Invalid or empty JSON body.", 400)

    try:
        signal = parse_flow_signal(payload)
    except FlowSignalError as exc:
        logger.warning("Flow signal parse failed: %s", exc)
        return _rejected(None, str(exc), 400)

    decision = flow_engine.evaluate(signal)

    if not decision.allowed:
        logger.info("Flow signal blocked: %s", decision.reason)
        if decision.notifications:
            _queue_discord(background_tasks, decision.notifications[0])
        else:
            significant = ("Rule 2", "Rule 11", "Rule 16", "Rule 20", "PM-")
            if any(marker in decision.reason for marker in significant):
                _queue_discord(background_tasks, _flow_blocked_alert(decision))
        return JSONResponse(
            {
                "status": "blocked",
                "direction": signal.direction,
                "reason": decision.reason,
            }
        )

    for notification in decision.notifications:
        _queue_discord(background_tasks, notification)

    action = "BUY" if signal.direction == "long" else "SELL"
    stable_id = options_signal_id(payload) or f"flow-{uuid.uuid4().hex}"
    command: dict[str, Any] = {
        "id": stable_id,
        "source": signal.source or "flow-bot-v2",
        "symbol": config.flow.symbol,
        "action": action,
        "orderType": "MARKET",
        "quantity": decision.contracts,
        "stopLossTicks": config.flow.stop_loss_ticks,
        "profitTargetTicks": config.flow.profit_target_ticks,
        "comment": decision.reason[:100],
    }
    order_body, status_code = _dispatch_command(command)
    order_status = str(order_body.get("status", "unknown"))
    if status_code >= 400 or order_status == "dry_run":
        flow_engine.release_reservation(signal.direction)

    options_body: dict[str, object] | None = None
    if config.options.enabled and order_status in {"accepted", "partial"}:
        try:
            session = str(flow_engine.status()["session"]).lower()
            envelope = build_options_envelope(payload, decision, stable_id, session)
            options_result = forward_options_envelope(envelope, config.options)
            options_body = {
                "http_status": options_result.status_code,
                **options_result.body,
            }
            logger.info(
                "Options receiver result signal=%s status=%s",
                stable_id,
                options_result.body.get("status", "unknown"),
            )
        except OptionsForwardError as exc:
            logger.error("Options forwarding failed for signal %s: %s", stable_id, exc)
            options_body = {"status": "error", "reason": str(exc)}

    _queue_discord(background_tasks, _flow_trade_alert(decision, order_status))
    response_body: dict[str, object] = {
        "status": "traded" if order_status in {"accepted", "partial"} else order_status,
        "direction": signal.direction,
        "contracts": decision.contracts,
        "reason": decision.reason,
        "order": order_body,
    }
    if options_body is not None:
        response_body["options"] = options_body
    return JSONResponse(response_body, status_code=status_code)


@app.get("/flow/status")
@app.get("/status")
def flow_status() -> dict[str, object]:
    status = flow_engine.status()
    status.update(
        {
            "bot": "Flow Bot integrated",
            "contract": config.flow.contract_label,
            "sl_ticks": config.flow.stop_loss_ticks,
            "pt_ticks": config.flow.profit_target_ticks,
            "extension_url": f"http://127.0.0.1:{config.port}/signal",
            "options_enabled": config.options.enabled,
        }
    )
    return status


@app.post("/flow/reset")
@app.post("/reset")
def flow_reset(background_tasks: BackgroundTasks) -> dict[str, str]:
    session = flow_engine.reset_current_session()
    _queue_discord(background_tasks, f"🔄 Manual reset — {session} session flags cleared")
    return {"status": "reset", "session": session}


def main() -> None:
    import uvicorn

    ensure_config_file()
    global config, dedupe, entry_cooldown, flow_engine
    config = load_config()
    dedupe = DuplicateCommandCache(config.dedupe_window_seconds)
    entry_cooldown = EntryCooldown(config.entry_cooldown_seconds)
    flow_engine = FlowRuleEngine(config.flow)

    logger.info(
        "WebhookReceiver starting on http://%s:%s  target=%s  DryRun=%s  entryCooldown=%ss  config=%s",
        config.host,
        config.port,
        config.target,
        config.dry_run,
        config.entry_cooldown_seconds,
        config_path(),
    )
    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
