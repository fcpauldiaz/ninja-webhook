from __future__ import annotations

import json
import logging
import socket
import uuid
from datetime import datetime, timezone
from typing import Any

from config import AppConfig, within_trading_hours

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

    logger.info("Forwarding command %s to %s:%s", command.get("id"), config.tcp_host, config.tcp_port)
    with socket.create_connection((config.tcp_host, config.tcp_port), config.connect_timeout_sec) as sock:
        sock.sendall(payload)
    logger.info("Forwarded command %s successfully", command.get("id"))
