---
name: Auto Execute Flag
description: How auto_execute toggle works between dashboard and bot
---
**Rule:** bot_state.auto_execute is ONLY written by dashboard (POST /api/config). update_bot_state() never includes it in UPDATE SET to preserve dashboard setting.
**Bot reads it:** fetch_db_config() returns (pair, sl_pips, smc_enabled, auto_execute) every 5 loops (~10s).
**Manual commands:** Always execute regardless of auto_execute flag.
**Status string:** "RUNNING (Signals Only)" when auto_execute=False.
