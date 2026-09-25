# WebhookNt8Bridge

TradingView-style webhooks → local Python receiver → **NinjaTrader 8** and/or **Sierra Chart** (DTC).

```text
TradingView HTTPS webhook
  -> webhook_receiver (Python / FastAPI)
  -> target = ninjatrader | sierrachart | both
       ├─ NT: localhost TCP NDJSON (127.0.0.1:7077) → WebhookTradeListener
       └─ SC: DTC JSON TCP (127.0.0.1:11099) → Sierra Chart DTC Server
```

## Components

| Path | Role |
|------|------|
| [`webhook_receiver/`](webhook_receiver/) | **Primary** Python webhook service |
| [`NinjaTrader/`](NinjaTrader/) | NT8 Add-On sources |
| [`SIERRA_CHART.md`](SIERRA_CHART.md) | Sierra Chart DTC setup |
| [`FLOW_TRADING.md`](FLOW_TRADING.md) | Chrome extension flow-signal setup |
| [`OPTIONS_TRADING.md`](OPTIONS_TRADING.md) | Optional options trade-receiver forwarding |
| [`samples/`](samples/) | curl / TradingView examples |
| [`WebhookReceiver.DotNet/`](WebhookReceiver.DotNet/) | Previous C# receiver (archived) |

## Quick start

### 1. NinjaTrader Add-On (optional if using Sierra only)
**Recommended:** import `release\WebhookTradeListener-AddOn.zip` via **Tools → Import → NinjaScript Add-On…**  
Or copy `NinjaTrader/*.cs` into `Documents\NinjaTrader 8\bin\Custom\AddOns\`, compile, open **New → Webhook Trade Listener**, pick account/instrument/quantity, **Start Listener**.

### 2. Sierra Chart (optional if using NT only)
See [`SIERRA_CHART.md`](SIERRA_CHART.md): enable DTC Protocol Server (port `11099`, Allow Trading), set `"target": "sierrachart"` and `sierra.*` in `config.json`.

### 3. Webhook receiver

**Users:** run `WebhookReceiver.exe` (installer or portable). It lives in the Windows **system tray** — no CMD window. Right-click for status, logs, restart, or quit.

**Dev:**

```powershell
cd webhook_receiver
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python tray_app.py   # tray (same as EXE)
# or: python main.py  # console
```

Edit `webhook_receiver/config.json`:
- `"target"`: `ninjatrader` (default), `sierrachart`, or `both`
- NT: instrument/qty/account in the NT panel
- SC: instrument/qty/account in `sierra` section
- Flow extension: send signals to `http://127.0.0.1:5088/signal`; configure the `flow` section

### 4. Tunnel (for TradingView)

```powershell
scripts\start-ngrok-tunnel.cmd
```

### Distribute to users

```powershell
powershell -ExecutionPolicy Bypass -File scripts\pack-release.ps1
```

Produces under `release\`:
- `NinjaWebhook-Setup.exe` — full installer (needs [Inno Setup 6](https://jrsoftware.org/isinfo.php))
- `NinjaWebhook-Portable.zip` — EXE + Add-On zip
- `WebhookTradeListener-AddOn.zip` — NT import only

See [`packaging/DISTRIBUTION.md`](packaging/DISTRIBUTION.md).

### ES bracket curl (via tunnel)

Replace the host with your current tunnel URL:

```powershell
curl.exe -4 -s -X POST https://YOUR-TUNNEL.ngrok-free.app/webhook `
  -H "Content-Type: application/json" `
  -d "{\"id\":\"es-bracket-001\",\"symbol\":\"ES1!\",\"action\":\"BUY\",\"orderType\":\"MARKET\",\"quantity\":1,\"stopLossTicks\":16,\"profitTargetTicks\":32}"
```

No `account` field for NT — account is chosen in the NinjaTrader panel. Brackets apply on the NT path only. No webhook secret required (local use).

## Safety checklist
- Test on sim first (NT Sim101 / SC Sim)
- Keep live trading off until ready
- Confirm listeners are localhost only
- Prefer tunnel auth / firewall if exposing beyond localhost
