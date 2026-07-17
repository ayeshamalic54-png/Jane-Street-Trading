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
      Date.now() - new Date(botState.lastHeartbeat).getTime() < 30_000;

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

    const activeZones = zoneRows.map((z) => {
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
      currentPair: botState?.activePair ?? "EURUSD/GBPUSD",
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
      scannedAssets: scannedAssetsRows.map((s) => ({
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
    });
  } catch (err) {
    req.log.error({ err }, "Failed to get dashboard data");
    return res.status(500).json({ error: "Failed to get dashboard data" });
  }
});

export default router;
