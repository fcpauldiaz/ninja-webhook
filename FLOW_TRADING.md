# Flow signal automation

The Python receiver now accepts Chrome extension flow signals directly and applies the integrated flow rules before forwarding accepted orders to NinjaTrader or Sierra Chart.

## Extension setup

Set both extension webhook URLs to the receiver listen port (default `5088`; the installer can change this if Trade Desky already uses that port):

```text
http://127.0.0.1:5088/signal
```

If the extension runs on another machine, use the receiver's ngrok URL:

```text
https://YOUR-NGROK-URL/signal
```

The separate `flow_trading_bot_v2.py` and `signal_splitter.py` processes are no longer needed.

## Configuration

Edit `config.json` beside `WebhookReceiver.exe`:

```json
{
  "flow": {
    "enabled": true,
    "discord_webhook_url": "",
    "symbol": "ES1!",
    "contract_label": "MES 09-26",
    "base_contracts": 1,
    "stop_loss_ticks": 25,
    "profit_target_ticks": 32,
    "timezone": "America/New_York"
  }
}
```

The installer can set HTTP `port` (default `5088`) and `tcp.port` (default `7077`) so they do not collide with Trade Desky. Match `tcp.port` in the Webhook Trade Listener panel. It can also write a Discord webhook URL to `flow.discord_webhook_url`. You can also edit those fields later. Keep the Discord URL private and do not commit it.

NinjaTrader still owns the actual account, instrument, and quantity through the Webhook Trade Listener panel. The flow payload's calculated quantity is validated and logged, but the panel quantity controls NinjaTrader execution.

## Endpoints

- `POST /signal` — receive and evaluate an extension signal
- `GET /status` or `GET /flow/status` — flow session state
- `POST /reset` or `POST /flow/reset` — clear the current ETH/RTH trade reservations
- `POST /webhook` — existing direct order webhook
- `GET /health` — receiver health

## Safety

1. Use a simulation account first.
2. Keep `risk.max_quantity` at or above `flow.base_contracts`.
3. Verify the NinjaTrader listener's instrument and quantity before enabling live trading.
4. Flow state is held in memory and resets when the receiver restarts.
