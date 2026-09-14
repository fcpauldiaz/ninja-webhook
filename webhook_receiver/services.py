from __future__ import annotations

import json
import logging
import socket
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config import AppConfig, within_trading_hours
from sierra_dtc import SierraDtcClient, SierraDtcError, SierraTarget, new_client_order_id

logger = logging.getLogger("webhook")


def _norm_token(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text.upper() if text else None


def _as_optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def normalize_and_validate(command: dict[str, Any], config: AppConfig) -> tuple[dict[str, Any] | None, str | None]:
    if not config.enable_trading:
        return None, "Trading is disabled by risk.enable_trading=false."

    ok_hours, hours_reason = within_trading_hours(config)
    if not ok_hours:
        return None, hours_reason

    action = _norm_token(command.get("action"))
    order_type = _norm_token(command.get("orderType")) or "MARKET"
    time_in_force = _norm_token(command.get("timeInForce")) or "DAY"
    source = str(command.get("source") or "Unknown").strip() or "Unknown"
    symbol = str(command.get("symbol")).strip() if command.get("symbol") else None
    nt_symbol = str(command.get("ntSymbol")).strip() if command.get("ntSymbol") else None

    command_id = str(command.get("id")).strip() if command.get("id") else uuid.uuid4().hex
    timestamp = str(command.get("timestamp")).strip() if command.get("timestamp") else (
        datetime.now(timezone.utc).isoformat()
    )

    if not action:
        return None, "action is required."
    if action not in {a.upper() for a in config.allowed_actions}:
        return None, f"action '{action}' is not allowed."
    if order_type not in {t.upper() for t in config.allowed_order_types}:
        return None, f"orderType '{order_type}' is not allowed."
    if order_type != "MARKET":
        return None, "Only MARKET orders are supported in this version."

    try:
        quantity = _as_optional_int(command.get("quantity"))
    except (TypeError, ValueError):
        return None, "quantity must be a positive integer when provided."

    # Quantity is optional here — NinjaTrader panel sets the traded size.
    if quantity is not None:
        if quantity <= 0:
            return None, "quantity must be a positive integer."
        if quantity > config.max_quantity:
            return None, f"quantity {quantity} exceeds MaxQuantity {config.max_quantity}."
    else:
        quantity = 1

    # Instrument is selected in the NinjaTrader panel. Alert symbol is optional
    # (kept for logs only). Map when present so older alerts still validate cleanly.
    if not nt_symbol and symbol:
        mapped = config.symbol_map.get(symbol) or next(
            (v for k, v in config.symbol_map.items() if k.lower() == symbol.lower()),
            None,
        )
        if mapped:
            nt_symbol = mapped

    if config.allowed_symbols and (symbol or nt_symbol):
        allowed = {s.lower() for s in config.allowed_symbols}
        symbol_ok = (symbol and symbol.lower() in allowed) or (
            nt_symbol is not None and nt_symbol.lower() in allowed
        )
        if not symbol_ok:
            return None, (
                f"symbol '{symbol}' / ntSymbol '{nt_symbol}' is not in AllowedSymbols."
            )

    try:
        stop_loss_ticks = _as_optional_int(command.get("stopLossTicks"))
        profit_target_ticks = _as_optional_int(command.get("profitTargetTicks"))
    except (TypeError, ValueError):
        return None, "stopLossTicks/profitTargetTicks must be integers when provided."

    # Account is selected in the NinjaTrader panel — never forward payload account.
    normalized = {
        "id": command_id,
        "timestamp": timestamp,
        "source": source,
        "symbol": symbol,
        "ntSymbol": nt_symbol,
        "action": action,
        "orderType": order_type,
        "quantity": quantity,
        "timeInForce": time_in_force,
        "comment": str(command["comment"]).strip() if command.get("comment") else None,
        "stopLossTicks": stop_loss_ticks,
        "profitTargetTicks": profit_target_ticks,
    }
    return {k: v for k, v in normalized.items() if v is not None}, None


def forward_to_ninjatrader(command: dict[str, Any], config: AppConfig) -> None:
    line = json.dumps(command, separators=(",", ":"), ensure_ascii=False) + "\n"
    payload = line.encode("utf-8")

    logger.info("Forwarding command %s to NT %s:%s", command.get("id"), config.tcp_host, config.tcp_port)
    with socket.create_connection((config.tcp_host, config.tcp_port), config.connect_timeout_sec) as sock:
        sock.sendall(payload)
    logger.info("Forwarded command %s to NinjaTrader successfully", command.get("id"))


def resolve_sierra_symbol(command: dict[str, Any], config: AppConfig) -> str:
    """Prefer alert symbol mapped for Sierra; fall back to configured SC symbol."""
    alert_symbol = command.get("symbol")
    sc_map = config.sierra.symbol_map
    if alert_symbol and sc_map:
        mapped = sc_map.get(str(alert_symbol)) or next(
            (v for k, v in sc_map.items() if k.lower() == str(alert_symbol).lower()),
            None,
        )
        if mapped:
            return mapped
    if alert_symbol:
        text = str(alert_symbol).strip()
        # Allow passing an SC-style symbol directly in the alert.
        if "-" in text or "_FUT_" in text.upper():
            return text
    return config.sierra.symbol


def forward_to_sierrachart(command: dict[str, Any], config: AppConfig) -> dict[str, Any]:
    sierra = config.sierra
    if sierra.quantity <= 0:
        raise SierraDtcError("sierra.quantity must be a positive integer.")
    if sierra.quantity > config.max_quantity:
        raise SierraDtcError(
            f"sierra.quantity {sierra.quantity} exceeds MaxQuantity {config.max_quantity}."
        )
    if not sierra.trade_account.strip():
        raise SierraDtcError("sierra.trade_account is required.")

    symbol = resolve_sierra_symbol(command, config)
    if not symbol.strip():
        raise SierraDtcError("sierra.symbol is required (or map alert symbol).")

    if command.get("stopLossTicks") or command.get("profitTargetTicks"):
        logger.warning(
            "Command %s has bracket ticks — Sierra path submits market/flatten only "
            "(configure brackets in Sierra Chart if needed).",
            command.get("id"),
        )

    target = SierraTarget(
        host=sierra.host,
        port=sierra.port,
        trade_account=sierra.trade_account.strip(),
        symbol=symbol.strip(),
        exchange=sierra.exchange.strip(),
        quantity=sierra.quantity,
        username=sierra.username,
        password=sierra.password,
        heartbeat_interval_sec=sierra.heartbeat_interval_sec,
        connect_timeout_sec=sierra.connect_timeout_sec,
        response_wait_sec=sierra.response_wait_sec,
    )
    client_order_id = str(command.get("id") or new_client_order_id())
    action = str(command["action"]).upper()
    comment = command.get("comment")

    logger.info(
        "Forwarding command %s to Sierra DTC %s:%s symbol=%s qty=%s account=%s action=%s",
        client_order_id,
        target.host,
        target.port,
        target.symbol,
        target.quantity,
        target.trade_account,
        action,
    )
    update = SierraDtcClient(target).submit_market(
        action=action,
        client_order_id=client_order_id,
        comment=str(comment) if comment else None,
    )
    logger.info("Sierra Chart accepted command %s", client_order_id)
    return {"scSymbol": target.symbol, "orderUpdate": update}


def forward_command(command: dict[str, Any], config: AppConfig) -> dict[str, Any]:
    """Route to NinjaTrader and/or Sierra Chart based on config.target."""
    results: dict[str, Any] = {"target": config.target}
    errors: list[str] = []

    send_nt = config.target in {"ninjatrader", "both"}
    send_sc = config.target in {"sierrachart", "both"}

    if send_nt:
        try:
            forward_to_ninjatrader(command, config)
            results["ninjatrader"] = "ok"
        except OSError as exc:
            errors.append(f"NinjaTrader: {exc}")
            results["ninjatrader"] = f"error: {exc}"

    if send_sc:
        try:
            sc_result = forward_to_sierrachart(command, config)
            results["sierrachart"] = "ok"
            results["scSymbol"] = sc_result.get("scSymbol")
        except (OSError, SierraDtcError) as exc:
            errors.append(f"Sierra Chart: {exc}")
            results["sierrachart"] = f"error: {exc}"

    if errors:
        if config.target == "both" and (
            results.get("ninjatrader") == "ok" or results.get("sierrachart") == "ok"
        ):
            results["partialErrors"] = errors
            return results
        raise RuntimeError("; ".join(errors))

    return results


def send_discord_notification(webhook_url: str, message: str) -> None:
    if not webhook_url.strip():
        return

    payload = json.dumps({"content": message}, ensure_ascii=False).encode("utf-8")
    request = Request(
        webhook_url.strip(),
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "NinjaWebhook/1.1"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=8) as response:
            if response.status >= 300:
                logger.warning("Discord webhook returned HTTP %s", response.status)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        logger.warning("Discord notification failed: %s", exc)
