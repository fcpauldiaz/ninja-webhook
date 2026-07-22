# WebhookNt8Bridge

TradingView-style webhooks → local Python receiver → localhost TCP → NinjaTrader 8 Add-On.

```text
TradingView HTTPS webhook
  -> webhook_receiver (Python / FastAPI)
  -> localhost TCP NDJSON (127.0.0.1:7077)
  -> NinjaTrader 8 Add-On (WebhookTradeListener)
  -> orders on the account selected in the NT panel
```

## Components

| Path | Role |
|------|------|
| [`webhook_receiver/`](webhook_receiver/) | **Primary** Python webhook service |
| [`NinjaTrader/`](NinjaTrader/) | NT8 Add-On sources |
| [`samples/`](samples/) | curl / TradingView examples |
| [`WebhookReceiver.DotNet/`](WebhookReceiver.DotNet/) | Previous C# receiver (archived) |

## Quick start

### 1. NinjaTrader Add-On
Copy `NinjaTrader/*.cs` into `Documents\NinjaTrader 8\bin\Custom\AddOns\`, compile, open **New → Webhook Trade Listener**, pick account, **Start Listener**, optionally enable live trading.

### 2. Python receiver

```powershell
cd webhook_receiver
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

Edit `webhook_receiver/config.json` (secret, symbol map, dry_run).

### 3. Tunnel (for TradingView)

```powershell
scripts\start-cloudflare-tunnel.cmd
```

Use the printed `https://….trycloudflare.com/webhook` URL.

### ES bracket curl (via tunnel)

Replace the host with your current tunnel URL:

```powershell
curl.exe -4 -s -X POST https://YOUR-TUNNEL.trycloudflare.com/webhook `
  -H "Content-Type: application/json" `
  -H "X-Webhook-Secret: dev-secret" `
  -d "{\"id\":\"es-bracket-001\",\"symbol\":\"ES1!\",\"action\":\"BUY\",\"orderType\":\"MARKET\",\"quantity\":1,\"stopLossTicks\":16,\"profitTargetTicks\":32}"
```

No `account` field — account is chosen in the NinjaTrader panel.

## Safety checklist
- Test on Sim101 first
- Keep live trading checkbox off until ready
- Use a strong webhook secret
- Confirm TCP listener is `127.0.0.1` only
