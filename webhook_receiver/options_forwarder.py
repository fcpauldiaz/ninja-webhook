from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config import OptionsConfig
from flow_rules import FlowDecision


class OptionsForwardError(RuntimeError):
    pass


@dataclass(frozen=True)
class OptionsForwardResult:
    status_code: int
    body: dict[str, object]


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _positive_price(*values: object) -> float | None:
    for value in values:
        if value in (None, ""):
            continue
        try:
            price = float(value)
        except (TypeError, ValueError):
            continue
        if price > 0:
            return price
    return None


def options_signal_id(payload: Mapping[str, object]) -> str | None:
    nested_signal = _mapping(payload.get("signal"))
    for value in (nested_signal.get("id"), payload.get("id")):
        text = str(value).strip() if value is not None else ""
        if text:
            return text
    return None


def build_options_envelope(
    payload: Mapping[str, object],
    decision: FlowDecision,
    stable_id: str,
    session: str,
) -> dict[str, object]:
    nested_signal = _mapping(payload.get("signal"))
    nested_context = _mapping(payload.get("context"))

    if payload.get("type") == "signal" and nested_signal:
        price = _positive_price(
            nested_signal.get("price"),
            nested_context.get("currentPrice"),
        )
        if price is None:
            raise OptionsForwardError(
                "Options skipped: signal.price or context.currentPrice must be positive."
            )
        return dict(payload)

    signal = decision.signal
    price = _positive_price(
        payload.get("price"),
        payload.get("spxPrice"),
        signal.price,
    )
    if price is None:
        raise OptionsForwardError(
            "Options skipped: original flow signal did not include a positive SPX price."
        )

    direction = signal.direction
    if direction not in {"long", "short"}:
        raise OptionsForwardError("Options skipped: flow direction is not long or short.")

    source = str(payload.get("source") or signal.source or "extension-overlay").strip()
    if source not in {"extension-overlay", "extension-test"}:
        source = "extension-overlay"

    now = datetime.now(timezone.utc)
    fired_at = now.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    raw_time = payload.get("time")
    signal_time: int | float
    if isinstance(raw_time, (int, float)) and not isinstance(raw_time, bool):
        signal_time = raw_time
    else:
        signal_time = int(now.timestamp())

    variant = str(
        payload.get("variant")
        or payload.get("kind")
        or signal.signal_type
        or "flow"
    ).strip()

    context: dict[str, object] = {
        "currentPrice": price,
        "gap": signal.gap,
        "retailValue": signal.retail,
        "instValue": signal.institutional,
    }
    bias = payload.get("bias")
    if bias not in (None, ""):
        context["bias"] = bias

    return {
        "type": "signal",
        "firedAt": str(payload.get("firedAt") or fired_at),
        "session": str(payload.get("session") or session).lower(),
        "caution": payload.get("caution"),
        "signal": {
            "id": stable_id,
            "time": signal_time,
            "price": price,
            "shape": str(payload.get("shape") or "circle"),
            "side": direction,
            "variant": variant,
            "color": "green" if direction == "long" else "red",
            "source": source,
        },
        "context": context,
    }


def _ingest_url(configured_url: str) -> str:
    base = configured_url.strip().rstrip("/")
    if base.endswith("/v1/ingest"):
        return base
    return f"{base}/v1/ingest"


def forward_options_envelope(
    envelope: Mapping[str, object],
    config: OptionsConfig,
) -> OptionsForwardResult:
    if not config.enabled:
        raise OptionsForwardError("Options forwarding is disabled.")
    if not config.webhook_url:
        raise OptionsForwardError("Options webhook URL is not configured.")
    if not config.api_key:
        raise OptionsForwardError("Options API key is not configured.")

    request = Request(
        _ingest_url(config.webhook_url),
        data=json.dumps(envelope, separators=(",", ":")).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.api_key}",
            "User-Agent": "NinjaWebhook/1.2",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=config.timeout_sec) as response:
            raw = response.read().decode("utf-8", errors="replace")
            decoded = json.loads(raw) if raw.strip() else {}
            body = decoded if isinstance(decoded, dict) else {"response": decoded}
            return OptionsForwardResult(response.status, body)
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise OptionsForwardError(
            f"Options receiver HTTP {exc.code}: {raw[:500] or exc.reason}"
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise OptionsForwardError(f"Options receiver request failed: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise OptionsForwardError("Options receiver returned invalid JSON.") from exc
