# Python Webhook Receiver

Forwards TradingView-style webhooks to the NinjaTrader Add-On over localhost TCP.

## Setup

```powershell
cd webhook_receiver
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

```powershell
python main.py
```

Listens on `http://127.0.0.1:5088` by default (`config.json`).

## Configure

Edit `config.json`:

| Key | Purpose |
|-----|---------|
| `webhook.secret` | Shared secret (`X-Webhook-Secret`) |
| `webhook.dry_run` | Validate only; do not TCP-forward |
| `risk.*` | Quantity / optional symbol / action allowlists |
| `tcp.host` / `tcp.port` | NinjaTrader listener (`127.0.0.1:7077`) |
| `symbol_map` | Optional alert ticker → NT name (for logs/legacy) |

**Account and instrument** are set in the NinjaTrader listener panel (instrument defaults to `ES 09-26`). Alert `symbol` is optional and does not choose the traded contract.

## Endpoints

- `GET /health`
- `POST /webhook`

## Distribute (EXE)

Build a single-file Windows EXE users can double-click:

```powershell
cd webhook_receiver
.\build_exe.ps1
```

Output: `dist\WebhookReceiver.exe`

On first launch the app prompts for the webhook secret (hidden input, confirmed twice) and writes `config.json` next to the EXE. Re-run setup anytime:

```powershell
.\WebhookReceiver.exe --setup
.\WebhookReceiver.exe --setup --run
```

Ship only the EXE. Users should also run the NinjaTrader Add-On listener on the same PC (`127.0.0.1:7077`).