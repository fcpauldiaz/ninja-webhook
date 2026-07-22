# New setup (Python on this PC)

Both pieces run on your trading PC. TradingView reaches you through Cloudflare Tunnel.

```text
TradingView → Cloudflare Tunnel → Python webhook_receiver (:5088)
                                      → TCP 127.0.0.1:7077
                                      → NinjaTrader Add-On → orders
```

## Currently running

| Piece | Status |
|-------|--------|
| Python receiver | `http://127.0.0.1:5088` |
| Cloudflare tunnel | `https://kelkoo-attractions-fare-irrigation.trycloudflare.com` |
| NT listener (:7077) | Start in NinjaTrader (see below) |

## Your steps in NinjaTrader

1. Open **New → Webhook Trade Listener**
2. Select **Account** (connected accounts only)
3. Click **Start Listener** → status must show `Listening on 127.0.0.1:7077`
4. Check **ENABLE LIVE TRADING** only when you want real Sim/live orders

## TradingView webhook

- URL: `https://kelkoo-attractions-fare-irrigation.trycloudflare.com/webhook`
- Header: `X-Webhook-Secret: dev-secret`
- Body example (no account field):

```json
{
  "id": "{{strategy.order.id}}-{{time}}",
  "source": "TradingView",
  "symbol": "{{ticker}}",
  "action": "BUY",
  "orderType": "MARKET",
  "quantity": 1,
  "stopLossTicks": 16,
  "profitTargetTicks": 32
}
```

## Restart later

```powershell
cd c:\Users\pablo\OneDrive\Documentos\WebhookNt8Bridge\webhook_receiver
.\.venv\Scripts\Activate.ps1
python main.py
```

Then in another terminal:

```powershell
c:\Users\pablo\OneDrive\Documentos\WebhookNt8Bridge\scripts\start-cloudflare-tunnel.cmd
```

Copy the new `trycloudflare.com` URL into TradingView (it changes each tunnel restart).

## Config

Edit `webhook_receiver\config.json` for secret, symbol map, dry_run, max quantity.
