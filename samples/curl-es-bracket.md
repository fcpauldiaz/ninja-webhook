# ES bracket via ngrok tunnel

Instrument, account, and quantity come from the **NinjaTrader panel**. Alert `symbol` / `quantity` are optional.

```powershell
curl.exe -4 -s -X POST https://YOUR-NGROK-HOST.ngrok-free.app/webhook `
  -H "Content-Type: application/json" `
  -H "ngrok-skip-browser-warning: true" `
  -d "{\"id\":\"es-bracket-$(Get-Date -Format yyyyMMddHHmmss)\",\"source\":\"curl\",\"action\":\"BUY\",\"orderType\":\"MARKET\",\"stopLossTicks\":16,\"profitTargetTicks\":32,\"comment\":\"ES bracket SL16 PT32\"}"
```

No webhook secret (local receiver). Start tunnel: `scripts\start-ngrok-tunnel.cmd`
