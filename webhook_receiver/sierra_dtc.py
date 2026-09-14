from __future__ import annotations

import json
import logging
import socket
import struct
import time
import uuid
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("webhook.sierra")

# DTC Protocol constants (see DTCProtocol.h / Sierra Chart docs)
CURRENT_VERSION = 8
ENCODING_REQUEST = 6
ENCODING_RESPONSE = 7
LOGON_REQUEST = 1
LOGON_RESPONSE = 2
LOGOFF = 5
SUBMIT_NEW_SINGLE_ORDER = 208
SUBMIT_FLATTEN_POSITION_ORDER = 209
ORDER_UPDATE = 301

JSON_ENCODING = 2
LOGON_SUCCESS = 1

ORDER_TYPE_MARKET = 1
TIF_DAY = 1
BUY = 1
SELL = 2


@dataclass(frozen=True)
class SierraTarget:
    host: str
    port: int
    trade_account: str
    symbol: str
    exchange: str
    quantity: int
    username: str
    password: str
    heartbeat_interval_sec: int
    connect_timeout_sec: float
    response_wait_sec: float


class SierraDtcError(RuntimeError):
    pass


def _encoding_request_json() -> bytes:
    # Binary ENCODING_REQUEST: Size=16, Type=6, ProtocolVersion=8, Encoding=JSON, ProtocolType="DTC\0"
    return struct.pack("<HHii4s", 16, ENCODING_REQUEST, CURRENT_VERSION, JSON_ENCODING, b"DTC\0")


def _json_message(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\0"


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    chunks: list[bytes] = []
    remaining = n
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            raise SierraDtcError("Socket closed while reading binary DTC message.")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _recv_json_message(sock: socket.socket, deadline: float) -> dict[str, Any]:
    buf = bytearray()
    while True:
        if time.monotonic() > deadline:
            raise SierraDtcError("Timed out waiting for DTC JSON message.")
        sock.settimeout(max(0.05, deadline - time.monotonic()))
        try:
            chunk = sock.recv(4096)
        except socket.timeout:
            continue
        if not chunk:
            raise SierraDtcError("Socket closed while reading DTC JSON message.")
        buf.extend(chunk)
        null_at = buf.find(b"\0")
        if null_at >= 0:
            raw = bytes(buf[:null_at])
            del buf[: null_at + 1]
            if not raw.strip():
                continue
            try:
                msg = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise SierraDtcError(f"Invalid DTC JSON: {exc}") from exc
            if not isinstance(msg, dict):
                raise SierraDtcError("DTC JSON message must be an object.")
            return msg


def _wait_for_type(
    sock: socket.socket,
    expected_type: int,
    deadline: float,
    *,
    ignore_types: set[int] | None = None,
) -> dict[str, Any]:
    ignore = ignore_types or set()
    while True:
        msg = _recv_json_message(sock, deadline)
        msg_type = int(msg.get("Type", 0))
        if msg_type == expected_type:
            return msg
        if msg_type in ignore:
            logger.debug("Ignoring DTC Type=%s while waiting for %s", msg_type, expected_type)
            continue
        logger.debug("Skipping unexpected DTC Type=%s payload=%s", msg_type, msg)


class SierraDtcClient:
    """Short-lived DTC session: encode → logon → submit → optional update → logoff."""

    def __init__(self, target: SierraTarget) -> None:
        self._target = target

    def submit_market(self, *, action: str, client_order_id: str, comment: str | None) -> dict[str, Any]:
        action_u = action.upper()
        if action_u == "BUY":
            buy_sell = BUY
            return self._with_session(
                lambda sock: self._submit_single(
                    sock,
                    buy_sell=buy_sell,
                    client_order_id=client_order_id,
                    comment=comment,
                )
            )
        if action_u == "SELL":
            return self._with_session(
                lambda sock: self._submit_single(
                    sock,
                    buy_sell=SELL,
                    client_order_id=client_order_id,
                    comment=comment,
                )
            )
        if action_u in {"FLATTEN", "EXIT_LONG", "EXIT_SHORT"}:
            return self._with_session(
                lambda sock: self._flatten(sock, client_order_id=client_order_id, comment=comment)
            )
        raise SierraDtcError(f"Unsupported Sierra action '{action}'.")

    def _with_session(self, work) -> dict[str, Any]:
        target = self._target
        deadline = time.monotonic() + max(target.connect_timeout_sec, target.response_wait_sec) + 2.0
        with socket.create_connection(
            (target.host, target.port),
            target.connect_timeout_sec,
        ) as sock:
            sock.settimeout(target.connect_timeout_sec)
            self._negotiate_json(sock)
            self._logon(sock, deadline)
            try:
                result = work(sock)
            finally:
                self._logoff(sock)
            return result

    def _negotiate_json(self, sock: socket.socket) -> None:
        sock.sendall(_encoding_request_json())
        header = _recv_exact(sock, 16)
        size, msg_type, version, encoding, protocol = struct.unpack("<HHii4s", header)
        if size < 16 or msg_type != ENCODING_RESPONSE:
            raise SierraDtcError(
                f"Unexpected ENCODING_RESPONSE header size={size} type={msg_type}."
            )
        if encoding != JSON_ENCODING:
            raise SierraDtcError(
                f"Sierra Chart DTC Server did not accept JSON encoding "
                f"(got {encoding}; enable JSON / restart DTC server)."
            )
        logger.info(
            "DTC encoding OK version=%s protocol=%s",
            version,
            protocol.split(b"\0", 1)[0].decode("ascii", errors="replace"),
        )

    def _logon(self, sock: socket.socket, deadline: float) -> None:
        target = self._target
        payload = {
            "Type": LOGON_REQUEST,
            "ProtocolVersion": CURRENT_VERSION,
            "Username": target.username,
            "Password": target.password,
            "GeneralTextData": "WebhookNt8Bridge",
            "HeartbeatIntervalInSeconds": max(5, target.heartbeat_interval_sec),
            "TradeAccount": target.trade_account,
            "ClientName": "WebhookNt8Bridge",
        }
        sock.sendall(_json_message(payload))
        response = _wait_for_type(sock, LOGON_RESPONSE, deadline)
        result = int(response.get("Result", 0))
        if result != LOGON_SUCCESS:
            text = str(response.get("ResultText") or response)
            raise SierraDtcError(f"DTC logon failed (Result={result}): {text}")
        logger.info(
            "DTC logon OK account=%s trading=%s",
            target.trade_account,
            response.get("TradingIsSupported"),
        )

    def _logoff(self, sock: socket.socket) -> None:
        try:
            sock.sendall(_json_message({"Type": LOGOFF, "Reason": "done"}))
        except OSError:
            pass

    def _submit_single(
        self,
        sock: socket.socket,
        *,
        buy_sell: int,
        client_order_id: str,
        comment: str | None,
    ) -> dict[str, Any]:
        target = self._target
        order = {
            "Type": SUBMIT_NEW_SINGLE_ORDER,
            "Symbol": target.symbol,
            "Exchange": target.exchange,
            "TradeAccount": target.trade_account,
            "ClientOrderID": client_order_id,
            "OrderType": ORDER_TYPE_MARKET,
            "BuySell": buy_sell,
            "Price1": 0.0,
            "Price2": 0.0,
            "TimeInForce": TIF_DAY,
            "GoodTillDateTime": 0,
            "Quantity": float(target.quantity),
            "IsAutomatedOrder": 1,
            "IsParentOrder": 0,
            "FreeFormText": (comment or "webhook")[:60],
        }
        sock.sendall(_json_message(order))
        return self._await_order_ack(sock, client_order_id)

    def _flatten(
        self,
        sock: socket.socket,
        *,
        client_order_id: str,
        comment: str | None,
    ) -> dict[str, Any]:
        target = self._target
        order = {
            "Type": SUBMIT_FLATTEN_POSITION_ORDER,
            "Symbol": target.symbol,
            "Exchange": target.exchange,
            "TradeAccount": target.trade_account,
            "ClientOrderID": client_order_id,
            "FreeFormText": (comment or "webhook-flatten")[:60],
            "IsAutomatedOrder": 1,
        }
        sock.sendall(_json_message(order))
        return self._await_order_ack(sock, client_order_id)

    def _await_order_ack(self, sock: socket.socket, client_order_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + self._target.response_wait_sec
        while time.monotonic() < deadline:
            try:
                msg = _recv_json_message(sock, deadline)
            except SierraDtcError:
                break
            msg_type = int(msg.get("Type", 0))
            if msg_type != ORDER_UPDATE:
                continue
            if str(msg.get("ClientOrderID") or "") not in {"", client_order_id}:
                continue
            status = msg.get("OrderStatus")
            reason = msg.get("OrderUpdateReason")
            reject = str(msg.get("OrderRejectReason") or "").strip()
            logger.info(
                "DTC ORDER_UPDATE id=%s status=%s reason=%s reject=%s",
                client_order_id,
                status,
                reason,
                reject or "-",
            )
            if reject:
                raise SierraDtcError(f"Order rejected: {reject}")
            return msg
        logger.info(
            "No ORDER_UPDATE within %.1fs for %s — order was submitted",
            self._target.response_wait_sec,
            client_order_id,
        )
        return {"Type": ORDER_UPDATE, "ClientOrderID": client_order_id, "submitted": True}


def new_client_order_id(prefix: str = "wh") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:16]}"
