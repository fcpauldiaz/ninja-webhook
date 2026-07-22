## PowerShell test helpers (Python receiver)

```powershell
cd webhook_receiver
.\.venv\Scripts\Activate.ps1
python main.py
```

```powershell
$secret = "dev-secret"
$base = "http://127.0.0.1:5088"
# Or tunnel:
# $base = "https://YOUR-TUNNEL.trycloudflare.com"
```

Health:

```powershell
Invoke-RestMethod "$base/health"
```

ES bracket (account from NT panel):

```powershell
$body = @{
  id = "es-" + [guid]::NewGuid().ToString("N")
  symbol = "ES1!"
  action = "BUY"
  orderType = "MARKET"
  quantity = 1
  stopLossTicks = 16
  profitTargetTicks = 32
} | ConvertTo-Json -Compress

Invoke-RestMethod -Method Post -Uri "$base/webhook" `
  -Headers @{ "X-Webhook-Secret" = $secret } `
  -ContentType "application/json" `
  -Body $body
```
