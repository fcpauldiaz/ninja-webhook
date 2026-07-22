# ES bracket via ngrok tunnel

Instrument and account come from the **NinjaTrader panel** (default instrument `ES 09-26`). Alert `symbol` is optional.

Current tunnel (changes if ngrok restarts) — check http://127.0.0.1:4040 or `logs\ngrok-url.txt`.

```powershell
curl.exe -4 -s -X POST https://YOUR-NGROK-HOST.ngrok-free.app/webhook `
  -H "Content-Type: application/json" `
  -H "X-Webhook-Secret: YOUR_SECRET" `
  -H "ngrok-skip-browser-warning: true" `
  -d "{\"id\":\"es-bracket-$(Get-Date -Format yyyyMMddHHmmss)\",\"source\":\"curl\",\"action\":\"BUY\",\"orderType\":\"MARKET\",\"quantity\":1,\"stopLossTicks\":16,\"profitTargetTicks\":32,\"comment\":\"ES bracket SL16 PT32\"}"
```

Start tunnel: `scripts\start-ngrok-tunnel.cmd`
