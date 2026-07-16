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
    
    // Group closed trades by signalId to treat spread sets as ONE single trade
    const groups: Record<string, typeof closed> = {};
    const individualTrades: typeof closed = [];

    for (const t of closed) {
      if (t.signalId != null) {
        const key = String(t.signalId);
        if (!groups[key]) {
          groups[key] = [];
        }
        groups[key].push(t);
      } else {
        individualTrades.push(t);
      }
    }

    const netProfits: number[] = [];

    for (const sigId in groups) {
      const sum = groups[sigId].reduce((acc, t) => acc + Number(t.profit ?? 0), 0);
      netProfits.push(sum);
    }

    for (const t of individualTrades) {
      netProfits.push(Number(t.profit ?? 0));
    }

    const totalTrades = netProfits.length;
    const winning = netProfits.filter((p) => p > 0);
    const losing = netProfits.filter((p) => p < 0);
    const totalPnl = netProfits.reduce((a, b) => a + b, 0);

    const ddRows = await db.select().from(dailyMetricsTable);
    const maxDrawdown = ddRows.reduce(
      (max, r) => Math.max(max, Number(r.maxDrawdownPercent ?? 0)),
      0
    );

    res.json({
      totalTrades,
      winningTrades: winning.length,
      losingTrades: losing.length,
      winRate: totalTrades > 0 ? (winning.length / totalTrades) * 100 : 0,
      totalPnl,
      avgPnl: totalTrades > 0 ? totalPnl / totalTrades : 0,
      bestTrade: netProfits.length > 0 ? Math.max(...netProfits) : 0,
      worstTrade: netProfits.length > 0 ? Math.min(...netProfits) : 0,
      maxDrawdown,
    });
  } catch (err) {
    req.log.error({ err }, "Failed to get metrics summary");
    res.status(500).json({ error: "Failed to get metrics summary" });
  }
});

export default router;
