# NinjaTrader 8 — WebhookTradeListener Add-On

Localhost TCP NDJSON listener that receives trade commands from WebhookReceiver and submits orders through the NinjaTrader Account API.

## Install (recommended)

1. Use the release artifact **`WebhookTradeListener-AddOn.zip`**
2. In NinjaTrader: **Tools → Import → NinjaScript Add-On…**
3. Select the zip → compile if prompted
4. **New → Webhook Trade Listener**

Or copy the three `.cs` files into `Documents\NinjaTrader 8\bin\Custom\AddOns\` and compile manually.

## Configure

| Field | Purpose |
|-------|---------|
| TCP Port | Default `7077` (must match receiver `tcp.port`; change both if Trade Desky already uses 7077) |
| Account | Connected account (e.g. Sim101) |
| Instrument | Traded contract (alert symbol ignored) |
| Quantity | Contract size (alert qty ignored) |
| Dedupe Window | Duplicate `id` protection |
| ENABLE LIVE TRADING | Off = validate/log only; On = submit orders |

Click **Start Listener**. Status should show listening on `127.0.0.1` and the chosen TCP port.

Keep a live chart/DOM open on the instrument so bracket orders can read bid/ask.

## Order behavior

| Action | Behavior |
|--------|----------|
| `BUY` / `SELL` | Market entry (+ optional SL/PT ticks from alert) |
| `EXIT_LONG` / `EXIT_SHORT` | Close matching position |
| `FLATTEN` | Flatten instrument on panel account |

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Import/compile errors | Import all three files; recompile |
| Menu missing | Restart NT after compile |
| Receiver 502 | Listener Started; TCP port matches `tcp.port` |
| No market price for bracket | Open live chart for the panel instrument |
| Instrument not found | Use exact NT name (e.g. `ES 09-26`) |
