# WebhookReceiver

ASP.NET Core minimal API that accepts TradingView-style webhooks, validates risk controls, and forwards normalized NDJSON trade commands to the NinjaTrader 8 Add-On over localhost TCP.

## Run

```powershell
cd WebhookReceiver
dotnet run
```

Default URL (launch profile): `http://127.0.0.1:5088`.

## Configuration

See `appsettings.json`. Important keys:

| Key | Purpose |
|-----|---------|
| `Webhook:Secret` | Shared secret (`X-Webhook-Secret` header preferred) |
| `Webhook:DryRun` | Validate/log only; do not TCP-forward |
| `Risk:EnableTrading` | Receiver kill switch |
| `Risk:MaxQuantity` | Hard quantity cap |
| `Risk:AllowedSymbols` | Symbol / ntSymbol allowlist |
| `Risk:AllowedAccounts` | Account allowlist (default `Sim101`) |
| `Tcp:Host` / `Tcp:Port` | NinjaTrader listener (`127.0.0.1:7077`) |
| `SymbolMap` | External ticker → NT instrument map |
| `Dedupe:WindowSeconds` | Duplicate command-id window |
| `TradingHours` | Optional session filter |

Environment variable example:

```powershell
$env:Webhook__Secret="my-secret-key"
$env:Webhook__DryRun="false"
dotnet run
```

## Endpoints

- `GET /health` — liveness
- `POST /webhook` — trade command intake
