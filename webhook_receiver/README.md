# Python Webhook Receiver

Forwards TradingView-style webhooks to **NinjaTrader** (TCP) and/or **Sierra Chart** (DTC).

Intended for **local** use (same PC as the platform). No webhook secret.

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

Listens on `http://127.0.0.1:5088` by default (`config.json` `port`; the installer can change this).

## Configure

| Key | Purpose |
|-----|---------|
| `target` | `ninjatrader` \| `sierrachart` \| `both` |
| `webhook.dry_run` | Validate only; do not forward |
| `risk.*` | Optional allowlists / max quantity |
| `tcp.host` / `tcp.port` | NinjaTrader listener (`127.0.0.1:7077` by default; installer can change `tcp.port`) |
| `sierra.*` | Sierra Chart DTC account / symbol / qty / port |
| `symbol_map` | Alert ticker → NT name (logs / legacy) |
| `sierra.symbol_map` | Alert ticker → SC symbol |
| `flow.*` | Chrome extension signal rules, brackets, and optional Discord alerts |
| `options.*` | Optional trade-receiver URL, device API key, and timeout |

**NinjaTrader:** account, instrument, and quantity are set in the NT listener panel.  
**Sierra Chart:** account, instrument, and quantity are set under `sierra` in `config.json`. See [`../SIERRA_CHART.md`](../SIERRA_CHART.md).

## Endpoints

- `GET /health`
- `POST /webhook`
- `POST /signal` — integrated flow-rule endpoint
- `GET /status` — flow session state
- `POST /reset` — reset current flow session

See [`../FLOW_TRADING.md`](../FLOW_TRADING.md) for extension setup.

## Distribute (EXE)

```powershell
cd webhook_receiver
.\build_exe.ps1
```

Or full release: `scripts\pack-release.ps1`

First launch writes `config.json` next to the EXE (no secret prompt).
