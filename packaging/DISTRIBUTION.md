# NinjaWebhook — user distribution guide
#
# Artifacts (from scripts\pack-release.ps1):
#   release\WebhookReceiver.exe
#   release\WebhookTradeListener-AddOn.zip   ← import in NinjaTrader
#   release\NinjaWebhook-Setup.exe           ← full installer (if Inno Setup present)
#   release\NinjaWebhook-Portable.zip        ← EXE + Add-On zip + this guide

## Option A — Full installer (recommended)

1. Run **NinjaWebhook-Setup.exe**
2. When prompted, set the HTTP listen port (default `5088`) and NinjaTrader TCP port (default `7077`) if Trade Desky already uses those ports
3. Discord / options fields are pre-filled from an existing `config.json` if present (edit or leave as-is)
4. Optionally enter/update the options trade-receiver URL and device API key
5. Finish the wizard (receiver is installed; Add-On zip is placed on the Desktop / install folder)
6. Open **NinjaTrader 8**
7. **Tools → Import → NinjaScript Add-On…**
8. Select **WebhookTradeListener-AddOn.zip**
9. Allow compile / restart if prompted
10. **New → Webhook Trade Listener**
11. Set Account, Instrument, Quantity, and the same TCP port as setup → **Start Listener**
12. Run **Webhook Receiver** from the Start Menu
13. Point your tunnel (ngrok/cloudflare) at `http://127.0.0.1:<listen-port>` (default `5088`)
14. For flow automation, set the Chrome extension webhook to
    `http://127.0.0.1:<listen-port>/signal` and see **FLOW_TRADING.md**

## Option B — Portable zip

1. Unzip **NinjaWebhook-Portable.zip** anywhere
2. Import **WebhookTradeListener-AddOn.zip** in NinjaTrader (same steps 3–8 above)
3. Run **WebhookReceiver.exe**

## Notes

- Receiver and NinjaTrader must run on the **same PC**
- TCP: receiver → `127.0.0.1:<tcp-port>` (installer default `7077`; must match the listener panel)
- HTTP: webhook / tunnel → `127.0.0.1:<listen-port>` (installer default `5088`)
- Account, instrument, and quantity are set in the **NT panel** (not the alert)
- The integrated flow endpoint replaces the separate flow bot and signal splitter
- Discord alerts are optional; configure a new private URL in `config.json`
- Options forwarding is optional and runs only after flow filtering and futures success
