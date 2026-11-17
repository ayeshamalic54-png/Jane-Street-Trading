import { Router } from "express";
import { db } from "@workspace/db";
import { dailyMetricsTable, tradesTable, botStateTable } from "@workspace/db";
import { desc, eq } from "drizzle-orm";

const router = Router();

const pktDateFmt = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Karachi",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

function toPktDateStr(d: Date): string {
  return pktDateFmt.format(d);
}

function getPktCutoffDateStr(days: number): string {
  const nowPktStr = toPktDateStr(new Date());
  const [y, m, day] = nowPktStr.split("-").map(Number);
  const utcMid = new Date(Date.UTC(y!, m! - 1, day!));
  utcMid.setUTCDate(utcMid.getUTCDate() - Math.max(0, days - 1));
  return utcMid.toISOString().slice(0, 10);
}

interface ClosedSetup {
  key: string;
  symbol: string;
  orderType: string;
  lots: number;
  profit: number;
  closeTime: Date;
  pktDate: string;
  comment: string;
}

async function loadClosedSetupsAndState(daysParam: number) {
  const [botRows, allClosedRows, allOpenRows, dmRows] = await Promise.all([
    db.select().from(botStateTable).where(eq(botStateTable.id, 1)).limit(1),
    db
      .select()
      .from(tradesTable)
      .where(eq(tradesTable.status, "CLOSED"))
      .orderBy(desc(tradesTable.closeTime)),
    db.select().from(tradesTable).where(eq(tradesTable.status, "OPEN")),
    db.select().from(dailyMetricsTable).orderBy(desc(dailyMetricsTable.tradingDate)),
  ]);

  const botState = botRows[0];
  const cutoffStr = daysParam > 0 ? getPktCutoffDateStr(daysParam) : "1970-01-01";

  // Group multi-leg trades sharing the same signalId into one logical setup,
  // while preserving every single closed execution (JS_SMC_STRUCTURE, MT5_AUTO_IMPORTED, MANUAL, etc.)
  const signalGroups = new Map<number, typeof allClosedRows>();
  const setups: ClosedSetup[] = [];

  for (const t of allClosedRows) {
    if (!t.closeTime || t.profit == null) continue;
    if (t.signalId != null) {
      const list = signalGroups.get(t.signalId) ?? [];
      list.push(t);
      signalGroups.set(t.signalId, list);
    } else {
      const pktDate = toPktDateStr(t.closeTime);
      setups.push({
        key: String(t.ticket),
        symbol: t.symbol,
        orderType: t.orderType,
        lots: Number(t.lots ?? 0),
        profit: Number(t.profit),
        closeTime: t.closeTime,
        pktDate,
        comment: t.comment ?? "",
      });
    }
  }

  for (const [sigId, legs] of signalGroups.entries()) {
    const validLegs = legs.filter((l) => l.closeTime != null && l.profit != null);
    if (!validLegs.length) continue;
    validLegs.sort((a, b) => a.closeTime!.getTime() - b.closeTime!.getTime());
    const lastLeg = validLegs[validLegs.length - 1]!;
    const firstLeg = validLegs[0]!;
    const netProfit = validLegs.reduce((acc, l) => acc + Number(l.profit ?? 0), 0);
    const totalLots = validLegs.reduce((acc, l) => acc + Number(l.lots ?? 0), 0);
    setups.push({
      key: `sig-${sigId}`,
      symbol: firstLeg.symbol,
      orderType: firstLeg.orderType,
      lots: Number(totalLots.toFixed(2)),
      profit: Number(netProfit.toFixed(2)),
      closeTime: lastLeg.closeTime!,
      pktDate: toPktDateStr(lastLeg.closeTime!),
      comment: firstLeg.comment ?? "",
    });
  }

  // Sort chronologically newest first
  setups.sort((a, b) => b.closeTime.getTime() - a.closeTime.getTime());

  const filteredSetups = setups.filter((s) => s.pktDate >= cutoffStr);

  return { botState, setups: filteredSetups, openRows: allOpenRows, dmRows, cutoffStr };
}

router.get("/metrics", async (req, res) => {
  try {
    const rawDays = req.query.days !== undefined ? Number(req.query.days) : 14;
    const days = Number.isFinite(rawDays) && rawDays >= 0 ? Math.min(365, Math.floor(rawDays)) : 14;

    const { botState, setups, dmRows, cutoffStr } = await loadClosedSetupsAndState(days);
    const todayPktStr = toPktDateStr(new Date());
    const activeLogin = Number(botState?.mt5Login ?? 0);
    const liveEquity = Number(botState?.equity ?? 0);
    const baseInitialEq = Number(botState?.initialBalance ?? 10000);

    // Aggregate real closed setups strictly by PKT trading date
    const setupsByDate = new Map<string, ClosedSetup[]>();
    for (const s of setups) {
      const list = setupsByDate.get(s.pktDate) ?? [];
      list.push(s);
      setupsByDate.set(s.pktDate, list);
    }

    // Index supplementary equity/DD snapshots from daily_metrics (preferring active login, non-zero DD)
    const dmByDate = new Map<string, { startEquity: number; currentEquity: number; maxDrawdownPercent: number }>();
    for (const m of dmRows) {
      const dStr = String(m.tradingDate).slice(0, 10);
      if (dStr < cutoffStr) continue;
      const existing = dmByDate.get(dStr);
      const isMatch = activeLogin > 0 && Number(m.mt5Login ?? 0) === activeLogin;
      const dd = Number(m.maxDrawdownPercent ?? 0);
      if (!existing) {
        dmByDate.set(dStr, {
          startEquity: Number(m.startEquity ?? baseInitialEq),
          currentEquity: Number(m.currentEquity ?? liveEquity),
          maxDrawdownPercent: dd,
        });
      } else {
        dmByDate.set(dStr, {
          startEquity: isMatch ? Number(m.startEquity ?? existing.startEquity) : existing.startEquity,
          currentEquity: isMatch ? Number(m.currentEquity ?? existing.currentEquity) : existing.currentEquity,
          maxDrawdownPercent: Math.max(existing.maxDrawdownPercent, dd),
        });
      }
    }

    // Collect every PKT date with real closed trades + today's live session date
    const activeDates = new Set<string>(setupsByDate.keys());
    if (days === 0 || todayPktStr >= cutoffStr) {
      if (setupsByDate.has(todayPktStr) || dmByDate.has(todayPktStr)) {
        activeDates.add(todayPktStr);
      }
    }

    const sortedDates = Array.from(activeDates).sort((a, b) => (a < b ? 1 : a > b ? -1 : 0));

    const result = sortedDates.map((dateStr) => {
      const daySetups = (setupsByDate.get(dateStr) ?? []).slice().sort(
        (a, b) => a.closeTime.getTime() - b.closeTime.getTime()
      );
      const dayPnl = Number(daySetups.reduce((acc, s) => acc + s.profit, 0).toFixed(2));
      const wins = daySetups.filter((s) => s.profit > 0).length;
      const losses = daySetups.filter((s) => s.profit < 0).length;

      const dm = dmByDate.get(dateStr);
      const startEq = dm?.startEquity ?? (liveEquity > 0 ? Number((liveEquity - dayPnl).toFixed(2)) : baseInitialEq);
      const currEq = dateStr === todayPktStr && liveEquity > 0 ? liveEquity : dm?.currentEquity ?? Number((startEq + dayPnl).toFixed(2));

      // Calculate true intraday peak-to-trough realized DD% from real trades as floor check
      let cum = 0;
      let peak = 0;
      let maxLossFromPeak = 0;
      for (const s of daySetups) {
        cum += s.profit;
        if (cum > peak) peak = cum;
        const ddUsd = peak - cum;
        if (ddUsd > maxLossFromPeak) maxLossFromPeak = ddUsd;
      }
      const computedDdPct = startEq > 0 ? Number(((maxLossFromPeak / startEq) * 100).toFixed(2)) : 0;
      const maxDd = Math.max(dm?.maxDrawdownPercent ?? 0, computedDdPct);

      return {
        tradingDate: dateStr,
        startEquity: Number(startEq.toFixed(2)),
        currentEquity: Number(currEq.toFixed(2)),
        maxDrawdownPercent: Number(maxDd.toFixed(2)),
        tradesToday: daySetups.length,
        wins,
        losses,
        pnl: dayPnl,
      };
    });

    res.json(result);
  } catch (err) {
    req.log.error({ err }, "Failed to get metrics");
    res.status(500).json({ error: "Failed to get metrics" });
  }
});

router.get("/metrics/summary", async (req, res) => {
  try {
    const rawDays = req.query.days !== undefined ? Number(req.query.days) : 30;
    const days = Number.isFinite(rawDays) && rawDays >= 0 ? Math.min(365, Math.floor(rawDays)) : 30;

    const { botState, setups, openRows, dmRows, cutoffStr } = await loadClosedSetupsAndState(days);

    const profits = setups.map((s) => s.profit);
    const totalTrades = profits.length;
    const winning = profits.filter((p) => p > 0);
    const losing = profits.filter((p) => p < 0);
    const totalPnl = Number(profits.reduce((a, b) => a + b, 0).toFixed(2));
    const grossWin = winning.reduce((a, b) => a + b, 0);
    const grossLoss = Math.abs(losing.reduce((a, b) => a + b, 0));
    const profitFactor = grossLoss > 0 ? Number((grossWin / grossLoss).toFixed(2)) : grossWin > 0 ? 9.99 : 0;

    // Peak-to-trough realized drawdown across selected window + daily_metrics peak
    const baseEquity = Number(botState?.initialBalance ?? 10000) || 10000;
    const chronoSetups = [...setups].sort((a, b) => a.closeTime.getTime() - b.closeTime.getTime());
    let cum = 0;
    let peak = 0;
    let maxDropUsd = 0;
    for (const s of chronoSetups) {
      cum += s.profit;
      if (cum > peak) peak = cum;
      if (peak - cum > maxDropUsd) maxDropUsd = peak - cum;
    }
    const realizedDdPct = baseEquity > 0 ? Number(((maxDropUsd / baseEquity) * 100).toFixed(2)) : 0;
    const dmMaxDd = dmRows
      .filter((r) => String(r.tradingDate).slice(0, 10) >= cutoffStr)
      .reduce((max, r) => Math.max(max, Number(r.maxDrawdownPercent ?? 0)), 0);

    res.json({
      days,
      totalTrades,
      winningTrades: winning.length,
      losingTrades: losing.length,
      winRate: totalTrades > 0 ? Number(((winning.length / totalTrades) * 100).toFixed(2)) : 0,
      totalPnl,
      avgPnl: totalTrades > 0 ? Number((totalPnl / totalTrades).toFixed(2)) : 0,
      bestTrade: profits.length > 0 ? Number(Math.max(...profits).toFixed(2)) : 0,
      worstTrade: profits.length > 0 ? Number(Math.min(...profits).toFixed(2)) : 0,
      profitFactor,
      maxDrawdown: Number(Math.max(realizedDdPct, dmMaxDd, Number(botState?.drawdownPercent ?? 0)).toFixed(2)),
      // Live real-time snapshot fields
      liveEquity: Number(botState?.equity ?? 0),
      floatingProfit: Number(botState?.floatingProfit ?? 0),
      openTradesCount: openRows.length,
      mt5Login: Number(botState?.mt5Login ?? 0),
      systemStatus: botState?.systemStatus ?? "BOT OFFLINE",
      lastHeartbeat: botState?.lastHeartbeat ? botState.lastHeartbeat.toISOString() : null,
      recentTrades: setups.slice(0, 15).map((s) => ({
        symbol: s.symbol,
        orderType: s.orderType,
        lots: s.lots,
        profit: s.profit,
        closeTime: s.closeTime.toISOString(),
        pktDate: s.pktDate,
        comment: s.comment,
      })),
    });
  } catch (err) {
    req.log.error({ err }, "Failed to get metrics summary");
    res.status(500).json({ error: "Failed to get metrics summary" });
  }
});

export default router;
