# Sierra Chart bridge (DTC)

Same webhook receiver can send orders to **Sierra Chart** over the DTC Protocol (JSON over TCP) instead of — or in addition to — NinjaTrader.

```text
TradingView HTTPS webhook
  -> webhook_receiver (Python)
  -> Sierra Chart DTC Server (default 127.0.0.1:11099)
  -> order on sierra.trade_account / sierra.symbol
```

## Enable DTC trading in Sierra Chart

1. Open **Global Settings → Sierra Chart Server Settings**.
2. Set **DTC Protocol Server** to **Yes**.
3. **Listening Port**: `11099` (or match `sierra.port` in `config.json`).
4. **Allow Trading**: **Yes**.
5. **Require Authentication**: usually **No** for localhost (or set username/password and mirror them in config).
6. **Use TLS / SSL**: **No** for local connections (this client uses plain TCP).
7. Apply / OK, then restart Sierra Chart if the server does not start.

Confirm the Trade Window / Trade Account list shows the account you will use (e.g. sim account).

## Receiver config

In `webhook_receiver/config.json`:

```json
{
  "target": "sierrachart",
  "sierra": {
    "host": "127.0.0.1",
    "port": 11099,
    "trade_account": "Sim1",
    "symbol": "ESU26-CME",
    "quantity": 1,
    "symbol_map": {
      "ES1!": "ESU26-CME",
      "NQ1!": "NQU26-CME"
    }
  }
}
```

| Field | Meaning |
|-------|---------|
| `target` | `ninjatrader` (default), `sierrachart`, or `both` |
| `sierra.trade_account` | Exact SC trade account name |
| `sierra.symbol` | Default SC symbol (use the format your data feed shows) |
| `sierra.quantity` | Contracts per webhook (alert qty is ignored for execution) |
| `sierra.symbol_map` | Optional alert ticker → SC symbol |

Symbol format depends on your service (examples: `ESU26-CME`, `ESU26_FUT_CME`). Copy it from Sierra Chart’s Find Symbol / Trade Window.

## Actions

| Webhook `action` | Sierra behavior |
|------------------|-----------------|
| `BUY` / `SELL` | Market order (`SUBMIT_NEW_SINGLE_ORDER`) |
| `FLATTEN` / `EXIT_LONG` / `EXIT_SHORT` | Flatten symbol (`SUBMIT_FLATTEN_POSITION_ORDER`) |

Bracket fields (`stopLossTicks` / `profitTargetTicks`) are **not** sent on the Sierra path yet — configure attached orders in Sierra Chart if you need them.

## Test

1. Set `"target": "sierrachart"` and `"webhook.dry_run": false`.
2. Start Sierra Chart with DTC trading enabled.
3. Start the receiver: `python main.py`.
4. Post a webhook:

```powershell
curl.exe -s -X POST http://127.0.0.1:5088/webhook `
  -H "Content-Type: application/json" `
  -d "{\"id\":\"sc-buy-001\",\"symbol\":\"ES1!\",\"action\":\"BUY\",\"orderType\":\"MARKET\"}"
```

Watch the receiver log for `DTC logon OK` / `Sierra Chart accepted`, and the Sierra Trade Window for the order.

## Notes

- Receiver and Sierra Chart should run on the **same PC** (localhost DTC).
- Use a sim account first.
- For TradingView from the cloud, keep using your existing ngrok (or similar) tunnel to `:5088`.
- With `"target": "both"`, a failure on one side returns HTTP 502 only if **both** fail; one success yields `status: partial`.
