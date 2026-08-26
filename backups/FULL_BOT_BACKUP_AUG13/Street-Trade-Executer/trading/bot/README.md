# Jane Street Quant Bot — Fixed Python Files

Copy these files to your Windows machine (replacing originals) to fix the 3 bugs found.

## Bug Fixes Applied

### Bug 1 — EURUSD/EURUSD pair in shared_config.json (CRITICAL)
**File:** `shared_config.json`
**Problem:** Original file had `"active_pair": "EURUSD/EURUSD"` — both legs were the same symbol.
The Kalman Filter spread (`price_a - beta * price_b`) of a symbol against itself is always ~0,
so z-score never crosses ±2.0 threshold → **zero trades executed**.
**Fix:** Changed to `"active_pair": "EURUSD/GBPUSD"`.

### Bug 2 — Stop Loss too tight (CRITICAL)
**File:** `main.py`
**Problem:** `sl_dist = 3.0 * (tick_a.ask - tick_a.bid)` — on EURUSD with typical 0.2 pip spread,
this gives SL = 0.6 pips. Most brokers require minimum 5–10 pips.
Result: `TRADE_RETCODE_INVALID_STOPS` — all orders rejected.
**Fix:** Replaced with `get_sl_distance(symbol)` → fixed 10 pips (`SL_PIPS = 10.0`).
Adjust `SL_PIPS` at the top of `main.py` to match your prop firm rules.

### Bug 3 — database.py now writes live telemetry to bot_state table
**File:** `database.py`
**Problem:** Bot had no way to signal liveness to the Replit dashboard.
**Fix:** Added `update_bot_state()` function — called every 2s from `main.py`.
The Replit dashboard shows "BOT ONLINE" when heartbeat is < 30s old.

## Files Changed
| File | Changed? | Notes |
|------|----------|-------|
| `shared_config.json` | ✅ | EURUSD/GBPUSD (was EURUSD/EURUSD) |
| `main.py` | ✅ | Fixed SL + calls update_bot_state() each loop |
| `database.py` | ✅ | Added update_bot_state() for dashboard heartbeat |
| `risk_safeguards.py` | — | Unchanged |
| `execution_bot.py` | — | Unchanged |
| `math_models.py` | — | Unchanged |
| `smc_indicators.py` | — | Unchanged |
| `data_ingestion.py` | — | Unchanged |

## Setup on Windows
1. Copy all files from this `bot/` folder to your MT5 bot directory (replace originals).
2. Ensure your `.env` file has `DATABASE_URL=<your Neon connection string>`.
3. Run: `python main.py`

The Replit dashboard at your `.replit.app` URL will show live data within seconds.
