import { Router } from "express";
import { db } from "@workspace/db";
import { tradesTable, botStateTable, fvgZonesTable, scannedAssetsTable } from "@workspace/db";
import { desc, eq } from "drizzle-orm";

const router = Router();

const ZONE_META: Record<string, { label: string; bullish: boolean }> = {
  bullish_ob:      { label: "OB",      bullish: true },
  bearish_ob:      { label: "OB",      bullish: false },
  bullish_fvg:     { label: "FVG",     bullish: true },
  bearish_fvg:     { label: "FVG",     bullish: false },
  bullish_breaker: { label: "BREAKER", bullish: true },
  bearish_breaker: { label: "BREAKER", bullish: false },
  bullish_ifvg:    { label: "iFVG",    bullish: true },
  bearish_ifvg:    { label: "iFVG",    bullish: false },
};

router.get("/dashboard", async (req, res) => {
  try {
    const [botStateRows, openDbTrades, recentClosedTradesRows, zoneRows, scannedAssetsRows] = await Promise.all([
      db.select().from(botStateTable).where(eq(botStateTable.id, 1)).limit(1),
      db.select().from(tradesTable).where(eq(tradesTable.status, "OPEN")),
      db.select().from(tradesTable).where(eq(tradesTable.status, "CLOSED")).orderBy(desc(tradesTable.entryTime)).limit(10),
      db.select().from(fvgZonesTable).orderBy(desc(fvgZonesTable.updatedAt)).limit(30),
      db.select().from(scannedAssetsTable).orderBy(desc(scannedAssetsTable.winRate)),
    ]);

    const botState = botStateRows[0];
    const isOnline =
      botState?.lastHeartbeat != null &&
      Date.now() - new Date(botState.lastHeartbeat).getTime() < 60_000;

    const openPositions = openDbTrades.map((t) => ({
      ticket: Number(t.ticket),
      symbol: t.symbol,
      type: t.orderType,
      lots: Number(t.lots),
      entry: Number(t.entryPrice),
      current: Number(t.closePrice ?? t.entryPrice),
      profit: Number(t.profit ?? 0),
      comment: t.comment ?? "",
    }));

    const recentClosedTrades = recentClosedTradesRows.map((t) => ({
      ticket: Number(t.ticket),
      symbol: t.symbol,
      orderType: t.orderType,
      lots: Number(t.lots),
      entryPrice: Number(t.entryPrice),
      closePrice: t.closePrice != null ? Number(t.closePrice) : null,
      profit: t.profit != null ? Number(t.profit) : null,
      entryTime: t.entryTime.toISOString(),
      closeTime: t.closeTime?.toISOString() ?? null,
      status: t.status,
      comment: t.comment ?? null,
    }));

    const forexOn = botState?.forexEnabled ?? true;
    const metalsOn = botState?.metalsEnabled ?? true;
    const indicesOn = botState?.indicesEnabled ?? true;
    const stocksOn = botState?.stocksEnabled ?? true;

    const isSymbolEnabled = (sym: string) => {
      const s = sym.toUpperCase();
      if (s.includes("XAU") || s.includes("XAG") || s.includes("XPT") || s.includes("XPD")) return metalsOn;
      if (s.includes("AAPL") || s.includes("MSFT") || s.includes("GOOGL") || s.includes("TSLA") || s.includes("NVDA") || s.includes("AMD") || s.includes("META") || s.includes("AMZN")) return stocksOn;
      if (s.includes("US30") || s.includes("NAS100") || s.includes("US500") || s.includes("GER30") || s.includes("UK100") || s.includes("USTEC")) return indicesOn;
      return forexOn;
    };

    const rawPair = botState?.activePair ?? "EURUSD/GBPUSD";
    const pairSymA = (rawPair.split(/[\/\s]/)[0] || "").toUpperCase();
    const isRawPairEnabled = isSymbolEnabled(pairSymA);

    let effectiveCurrentPair = rawPair;
    if (!isRawPairEnabled) {
      if (metalsOn) effectiveCurrentPair = "XAUUSD/XAGUSD";
      else if (indicesOn) effectiveCurrentPair = "US30/NAS100";
      else if (stocksOn) effectiveCurrentPair = "AAPL/MSFT";
      else if (forexOn) effectiveCurrentPair = "EURUSD/GBPUSD";
      
      try {
        db.update(botStateTable).set({ activePair: effectiveCurrentPair }).where(eq(botStateTable.id, 1)).execute();
      } catch (e) {}
    }

    const activeZones = zoneRows
      .filter((z) => isSymbolEnabled(z.symbol))
      .map((z) => {
        const meta = ZONE_META[z.zoneType] ?? { label: z.zoneType.toUpperCase(), bullish: true };
        const dir = meta.bullish ? "BULLISH" : "BEARISH";
        return {
          type: `${dir}_${meta.label}`,
          label: `${meta.bullish ? "🟢" : "🔴"} ${meta.label} · ${z.symbol}`,
          range: `${Number(z.lowPrice).toFixed(5)}–${Number(z.highPrice).toFixed(5)}`,
        };
      });

    return res.json({
      systemStatus: botState?.systemStatus ?? "BOT OFFLINE",
      currentPair: effectiveCurrentPair,
      lastUpdate: botState?.updatedAt?.toISOString() ?? null,
      equity: Number(botState?.equity ?? 0),
      drawdownPercent: Number(botState?.drawdownPercent ?? 0),
      floatingProfit: Number(botState?.floatingProfit ?? 0),
      zScore: Number(botState?.zScore ?? 0),
      hedgeRatio: Number(botState?.hedgeRatio ?? 0),
      obiA: Number(botState?.obiA ?? 0),
      obiB: Number(botState?.obiB ?? 0),
      tradesToday: botState?.tradesToday ?? 0,
      maxTrades: Number(botState?.maxTrades ?? 3),
      initialBalance: Number(botState?.initialBalance ?? 100000.00),
      overallDrawdown: Number(botState?.overallDrawdown ?? 0.00),
      maxEquityPeak: Number(botState?.maxEquityPeak ?? 0.00),
      mt5Login: botState?.mt5Login ?? 0,
      activePositions: openPositions,
      recentTrades: recentClosedTrades,
      activeZones,
      scannedAssets: scannedAssetsRows
        .filter((s) => isSymbolEnabled(s.symbolPair))
        .map((s) => ({
          symbolPair: s.symbolPair,
          priceA: Number(s.priceA ?? 0),
          priceB: Number(s.priceB ?? 0),
          winRate: Number(s.winRate ?? 50.0),
          zScore: Number(s.zScore ?? 0),
          action: s.action ?? "NONE",
        })),
      botOnline: isOnline,
      autoExecute: botState?.autoExecute ?? true,
      cryptoEnabled: botState?.cryptoEnabled ?? true,
      metalsEnabled: botState?.metalsEnabled ?? true,
      forexEnabled: botState?.forexEnabled ?? true,
      indicesEnabled: botState?.indicesEnabled ?? true,
      stocksEnabled: botState?.stocksEnabled ?? true,
      halt_drawdown_limit: Number(botState?.haltDrawdownLimit ?? (botState as any)?.halt_drawdown_limit ?? 0.83),
      max_drawdown_limit: Number(botState?.maxDrawdownLimit ?? (botState as any)?.max_drawdown_limit ?? 3.30),
      sessionGuardEnabled: Boolean(botState?.sessionGuardEnabled ?? (botState as any)?.session_guard_enabled ?? false),
      sessionStartHour: Number(botState?.sessionStartHour ?? (botState as any)?.session_start_hour ?? 12.5),
      sessionEndHour: Number(botState?.sessionEndHour ?? (botState as any)?.session_end_hour ?? 2.0),
      session_guard_enabled: Boolean(botState?.sessionGuardEnabled ?? (botState as any)?.session_guard_enabled ?? false),
      session_start_hour: Number(botState?.sessionStartHour ?? (botState as any)?.session_start_hour ?? 12.5),
      session_end_hour: Number(botState?.sessionEndHour ?? (botState as any)?.session_end_hour ?? 2.0),
    });

  } catch (err) {
    req.log.error({ err }, "Failed to get dashboard data");
    return res.status(500).json({ error: "Failed to get dashboard data" });
  }
});

export default router;
