# Jane Street Quant Bot Dashboard

A live trading dashboard for a Kalman Filter pairs trading forex bot running on Windows with MetaTrader5. The Replit app reads from the same Neon PostgreSQL database the Python bot writes to.

## Run & Operate

- `pnpm --filter @workspace/api-server run dev` — API server (port 8080, proxied at `/api`)
- `pnpm --filter @workspace/trading-dashboard run dev` — React dashboard (port 24210, proxied at `/`)
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)

## Stack

- pnpm workspaces, Node.js 24, TypeScript 5.9
- API: Express 5
- DB: PostgreSQL + Drizzle ORM (Neon hosted)
- Validation: Zod (`zod/v4`), `drizzle-zod`
- API codegen: Orval (from OpenAPI spec at `lib/api-spec/openapi.yaml`)
- Build: esbuild (CJS bundle)
- Frontend: React + Vite, TanStack Query, shadcn/ui, recharts, wouter

## Where things live

- `lib/api-spec/openapi.yaml` — OpenAPI spec (source of truth for all API contracts)
- `lib/db/src/schema/trading.ts` — Drizzle schema mirroring the Python bot's PostgreSQL tables
- `lib/api-client-react/src/generated/` — Generated React Query hooks (do not edit)
- `lib/api-zod/src/generated/` — Generated Zod schemas (do not edit)
- `artifacts/api-server/src/routes/` — Express route handlers
- `artifacts/trading-dashboard/src/pages/` — Dashboard pages (Dashboard, Trades, Signals, Metrics, Config)
- `bot/` — Fixed Python bot files (copy to Windows MT5 machine)

## Architecture decisions

- Dashboard polls `/api/dashboard` every 3 seconds via React Query `refetchInterval`.
- Bot liveness is detected by checking `bot_state.last_heartbeat` — if > 30s old, shows "BOT OFFLINE".
- `bot_state` table has exactly one row (id=1), upserted by the Python bot every 2 seconds.
- API server uses ETag-based HTTP 304 caching — identical responses return 304 Not Modified (normal).
- All trades/signals are written by the Python bot and only read by the Replit API (no writes from dashboard).

## Product

- Live dashboard showing equity, drawdown, Z-score gauge, Order Book Imbalance, active positions
- Trades history page with filterable trade log
- Signals feed showing Kalman Filter signals with action (BUY_SPREAD / SELL_SPREAD / NONE)
- Metrics page with 7-day P&L bar chart and summary stats (win rate, best/worst trade, max drawdown)
- Config page to view/update the active trading pair and SL pips (writes to `bot_state` table)

## Python Bot Bug Fixes (in `bot/` directory)

1. **shared_config.json** — `EURUSD/EURUSD` → `EURUSD/GBPUSD` (z-score was always ~0)
2. **main.py** — SL from `3x spread` (~0.6 pips, rejected by broker) → fixed `10 pips`
3. **database.py** — Added `update_bot_state()` heartbeat for dashboard connectivity

## User preferences

- Do not change trading logic — fix bugs only
- Dashboard must show "BOT OFFLINE" when bot is not running or heartbeat stale
- Dark terminal theme ("Bloomberg meets dark cockpit"), monospace fonts throughout

## Gotchas

- Run `pnpm run typecheck:libs` before leaf artifact typechecks when lib schema changes — stale lib declarations cause false import errors.
- `bot_state` ON CONFLICT uses `id` serial PK — always upsert with `id=1` from Python side.
- Do not add leaf workspace packages to root `tsconfig.json` references (libs only).
- Verify artifacts with `pnpm --filter @workspace/<slug> run typecheck`, not `build` (build needs workflow env vars).

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
