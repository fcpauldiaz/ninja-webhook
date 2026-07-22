# NinjaTrader 8 — WebhookTradeListener Add-On

Localhost TCP NDJSON listener that receives normalized trade commands from WebhookReceiver and optionally submits orders through the NinjaTrader Account API.

## Install

1. Copy all `.cs` files from this folder to:
   ```
   Documents\NinjaTrader 8\bin\Custom\AddOns\
   ```
   Files:
   - `WebhookTradeListener.cs`
   - `WebhookTradeCommand.cs`
   - `WebhookDuplicateCache.cs`
2. Open NinjaTrader 8.
3. **New** → **NinjaScript Editor**.
4. Right-click in the editor explorer → **Compile**.
5. Confirm compile succeeds (Output window).

## Open and configure

1. **Control Center** → **New** → **Webhook Trade Listener**.
2. Settings:
   - **EnableLiveTrading**: leave **OFF** initially (simulation / log only)
   - **TCP Port**: `7077`
   - **Default Account**: `Sim101`
   - **Max Quantity**: start with `1` or `2`
   - **Allowed NT Symbols**: exact NT full names, e.g. `ES 09-26,NQ 09-26`
   - **Dedupe Window Seconds**: `300`
3. Click **Start Listener**.
4. Status must read: `Listening on 127.0.0.1:<port>`

The listener binds to **loopback only**. It is not reachable from other machines.

## Order behavior

| Action | Behavior |
|--------|----------|
| `BUY` | Market buy |
| `SELL` | Market sell |
| `EXIT_LONG` | If long, market sell position quantity; else ignore |
| `EXIT_SHORT` | If short, market buy position quantity; else ignore |
| `FLATTEN` | `Account.Flatten` for the instrument |

Orders use `Account.CreateOrder` + `Account.Submit` with `OrderEntry.Manual`.

When **EnableLiveTrading** is OFF, commands are validated and logged but **not** submitted.

## Logging

- NinjaTrader **Output** tab (`NinjaTrader.Code.Output`)
- File (best-effort): `Documents\WebhookNt8Bridge\logs\nt-listener.log`

Log lifecycle examples:

```text
Received: {"id":"...","action":"BUY",...}
SIMULATION (EnableLiveTrading=false): accepted but NOT submitted
```

```text
Submitting Buy MARKET qty=1 ES 09-26 account=Sim101 ...
Order submitted: ...
```

## Shutdown

- Click **Stop Listener**, or close the window (auto-stops).
- Safe to leave NinjaTrader running; restart listener after compile/reload if needed.

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Compile errors | Ensure all three files are under `AddOns\`; recompile |
| Menu item missing | Restart NT after successful compile |
| Receiver 502 | Listener must be Started; port must match |
| Instrument not found | `ntSymbol` must match NT instrument full name exactly |
| Account not found | Account connected and name matches (`Sim101`) |
| Duplicate rejected | Change `id` or wait for dedupe window |

## Why an Add-On (not a Strategy)?

- Always-on without attaching to a chart
- Multi-instrument from one listener
- Uses Account-level order API suitable for external signals
- Clear EnableLiveTrading UI kill switch
