# Options trade-receiver forwarding

Allowed flow signals can also be sent to an options `trade-receiver`.

## Order of operations

1. Chrome extension sends the signal to `POST /signal`.
2. Futures flow filters run first.
3. If blocked, neither futures nor options are sent.
4. If allowed, the futures order is submitted first.
5. Only after futures succeeds, the options envelope is posted to `/v1/ingest`.

An options error is logged and returned in the `/signal` response, but does not undo a successful futures order.

## Configuration

The installer asks for both values optionally:

```json
{
  "options": {
    "enabled": true,
    "webhook_url": "https://receiver.example",
    "api_key": "device-api-key",
    "timeout_sec": 20
  }
}
```

`webhook_url` can be either the base URL or the complete `/v1/ingest` URL. The API key is sent as `Authorization: Bearer ...`.

Environment variables `OPTIONS_WEBHOOK_URL` and `OPTIONS_API_KEY` override the JSON values.

## Required extension data

The preferred request to `/signal` is the complete eterminal envelope:

```json
{
  "type": "signal",
  "firedAt": "2026-07-21T15:00:00.000Z",
  "session": "rth",
  "caution": null,
  "signal": {
    "id": "unique-signal-id",
    "time": 1721596500,
    "price": 6325,
    "shape": "circle",
    "side": "long",
    "variant": "extreme",
    "color": "green",
    "source": "extension-overlay"
  },
  "context": {
    "currentPrice": 6325,
    "bias": "bullish",
    "gap": 3.2,
    "retailValue": 12.1,
    "instValue": -12.0
  }
}
```

Flat extension signals are also mapped, but must contain a stable `id`, `side`, and positive SPX `price`/`spxPrice`. The receiver never invents an SPX price.

Do not commit `config.json` or share the device API key.
