import { Router } from "express";
import { db } from "@workspace/db";
import { dailyMetricsTable, tradesTable } from "@workspace/db";
import { desc, gte } from "drizzle-orm";
import { GetMetricsQueryParams } from "@workspace/api-zod";

const router = Router();

router.get("/metrics", async (req, res) => {
  try {
    const parsed = GetMetricsQueryParams.safeParse(req.query);
    const days = parsed.success ? (parsed.data.days ?? 7) : 7;

    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - days);
    const cutoffStr = cutoff.toISOString().split("T")[0]!;

    const rows = await db
      .select()
      .from(dailyMetricsTable)
      .where(gte(dailyMetricsTable.tradingDate, cutoffStr))
      .orderBy(desc(dailyMetricsTable.tradingDate))
      .limit(days);

    res.json(
      rows.map((m) => ({
        tradingDate: m.tradingDate,
        startEquity: Number(m.startEquity),
        currentEquity: Number(m.currentEquity),
        maxDrawdownPercent: Number(m.maxDrawdownPercent ?? 0),
        tradesToday: m.tradesToday ?? 0,
        pnl: Number(m.currentEquity) - Number(m.startEquity),
      }))
    );
  } catch (err) {
    req.log.error({ err }, "Failed to get metrics");
    res.status(500).json({ error: "Failed to get metrics" });
  }
});

router.get("/metrics/summary", async (req, res) => {
  try {
    const rows = await db.select().from(tradesTable);

    const closed = rows.filter((t) => t.status === "CLOSED" && t.profit != null);
    const profits = closed.map((t) => Number(t.profit));
    const winning = profits.filter((p) => p > 0);
    const losing = profits.filter((p) => p < 0);
    const totalPnl = profits.reduce((a, b) => a + b, 0);

    const ddRows = await db.select().from(dailyMetricsTable);
    const maxDrawdown = ddRows.reduce(
      (max, r) => Math.max(max, Number(r.maxDrawdownPercent ?? 0)),
      0
    );

    res.json({
      totalTrades: closed.length,
      winningTrades: winning.length,
      losingTrades: losing.length,
      winRate: closed.length > 0 ? (winning.length / closed.length) * 100 : 0,
      totalPnl,
      avgPnl: closed.length > 0 ? totalPnl / closed.length : 0,
      bestTrade: profits.length > 0 ? Math.max(...profits) : 0,
      worstTrade: profits.length > 0 ? Math.min(...profits) : 0,
      maxDrawdown,
    });
  } catch (err) {
    req.log.error({ err }, "Failed to get metrics summary");
    res.status(500).json({ error: "Failed to get metrics summary" });
  }
});

export default router;
