---
name: FVG Zones Flow
description: How FVG/OB/Breaker/iFVG zones flow from bot to dashboard
---
**Rule:** Bot calls log_fvg_zones(symbol, zones_dict) every 10 loops (~20s). Deletes existing zones for symbol, inserts fresh. API reads fvg_zones table in /api/dashboard and WS broadcaster.
**Zone keys:** bullish_ob, bearish_ob, bullish_fvg, bearish_fvg, bullish_breaker, bearish_breaker, bullish_ifvg, bearish_ifvg.
**Display:** Rendered as activeZones in DashboardData. Label: "🟢 FVG · EURUSD", range: "1.09150–1.09200".
