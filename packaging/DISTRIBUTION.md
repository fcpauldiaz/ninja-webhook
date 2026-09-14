# NinjaWebhook — user distribution guide
#
# Artifacts (from scripts\pack-release.ps1):
#   release\WebhookReceiver.exe
#   release\WebhookTradeListener-AddOn.zip   ← import in NinjaTrader
#   release\NinjaWebhook-Setup.exe           ← full installer (if Inno Setup present)
#   release\NinjaWebhook-Portable.zip        ← EXE + Add-On zip + this guide

## Option A — Full installer (recommended)

1. Run **NinjaWebhook-Setup.exe**
2. When prompted, Discord / options fields are pre-filled from an existing `config.json` if present (edit or leave as-is)
3. Optionally enter/update the options trade-receiver URL and device API key
4. Finish the wizard (receiver is installed; Add-On zip is placed on the Desktop / install folder)
3. Open **NinjaTrader 8**
4. **Tools → Import → NinjaScript Add-On…**
5. Select **WebhookTradeListener-AddOn.zip**
6. Allow compile / restart if prompted
7. **New → Webhook Trade Listener**
8. Set Account, Instrument, Quantity → **Start Listener**
9. Run **Webhook Receiver** from the Start Menu
10. Point your tunnel (ngrok/cloudflare) at `http://127.0.0.1:5088`
11. For flow automation, set the Chrome extension webhook to
    `http://127.0.0.1:5088/signal` and see **FLOW_TRADING.md**

## Option B — Portable zip

1. Unzip **NinjaWebhook-Portable.zip** anywhere
2. Import **WebhookTradeListener-AddOn.zip** in NinjaTrader (same steps 3–8 above)
3. Run **WebhookReceiver.exe**

## Notes

- Receiver and NinjaTrader must run on the **same PC**
- TCP: receiver → `127.0.0.1:7077` (listener panel)
- HTTP: webhook / tunnel → `127.0.0.1:5088`
- Account, instrument, and quantity are set in the **NT panel** (not the alert)
- The integrated flow endpoint replaces the separate flow bot and signal splitter
- Discord alerts are optional; configure a new private URL in `config.json`
- Options forwarding is optional and runs only after flow filtering and futures success
