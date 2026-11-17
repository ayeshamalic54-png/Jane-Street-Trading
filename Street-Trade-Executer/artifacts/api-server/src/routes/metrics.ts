import { Router } from "express";
import { db } from "@workspace/db";
import { dailyMetricsTable, tradesTable, botStateTable } from "@workspace/db";
import { desc, eq, sql } from "drizzle-orm";

const router = Router();

let metricsColsEnsured = false;

async function ensureMetricsColumns() {
  if (metricsColsEnsured) return;
  await db.execute(sql`
    ALTER TABLE bot_state ADD COLUMN IF NOT EXISTS metrics_reset_at TIMESTAMP DEFAULT NULL;
    ALTER TABLE trades ADD COLUMN IF NOT EXISTS mt5_login BIGINT DEFAULT NULL;
  `);
  metricsColsEnsured = true;
}

const pktDateFmt = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Karachi",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

const pktTimeFmt = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Asia/Karachi",
  day: "2-digit",
  month: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: true,
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
  await ensureMetricsColumns();

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
  const activeLogin = Number(botState?.mt5Login ?? 0);
  const resetAt: Date | null = botState?.metricsResetAt ? new Date(botState.metricsResetAt) : null;

  let accStateRow: { initial_balance?: any; max_equity_peak?: any; overall_drawdown?: any } | null = null;
  if (activeLogin > 0) {
    try {
      const accRes = await db.execute(
        sql`SELECT initial_balance, max_equity_peak, overall_drawdown FROM account_states WHERE mt5_login = ${activeLogin} LIMIT 1`
      );
      accStateRow = ((accRes as any).rows || [])[0] ?? null;
    } catch {}
  }

  const cutoffStr = daysParam > 0 ? getPktCutoffDateStr(daysParam) : "1970-01-01";
  const effectiveCutoffStr =
    resetAt && toPktDateStr(resetAt) > cutoffStr ? toPktDateStr(resetAt) : cutoffStr;

  const signalGroups = new Map<number, typeof allClosedRows>();
  const setups: ClosedSetup[] = [];

  for (const t of allClosedRows) {
    if (!t.closeTime || t.profit == null) continue;
    // Strictly ignore any historical/test trades prior to metricsResetAt
    if (resetAt && t.closeTime.getTime() < resetAt.getTime()) continue;
    // Isolate closed trades per active MT5 login whenever login is tagged
    if (t.mt5Login != null && Number(t.mt5Login) > 0 && activeLogin > 0 && Number(t.mt5Login) !== activeLogin) {
      continue;
    }

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

  const filteredSetups = setups.filter((s) => s.pktDate >= effectiveCutoffStr);

  return {
    botState,
    accStateRow,
    resetAt,
    setups: filteredSetups,
    openRows: allOpenRows,
    dmRows,
    cutoffStr: effectiveCutoffStr,
  };
}

router.post("/metrics/reset", async (req, res) => {
  try {
    await ensureMetricsColumns();
    const upd = await db.execute(sql`
      UPDATE bot_state
      SET metrics_reset_at = (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
          updated_at = NOW()
      WHERE id = (SELECT MIN(id) FROM bot_state)
      RETURNING metrics_reset_at
    `);
    const row = ((upd as any).rows || [])[0];
    const ts = row?.metrics_reset_at ? new Date(String(row.metrics_reset_at) + " UTC").toISOString() : new Date().toISOString();
    return res.json({ status: "success", metricsResetAt: ts });
  } catch (err) {
    req.log.error({ err }, "Failed to reset metrics baseline");
    return res.status(500).json({ error: "Failed to reset metrics baseline" });
  }
});

router.get("/metrics", async (req, res) => {
  try {
    const rawDays = req.query.days !== undefined ? Number(req.query.days) : 14;
    const days = Number.isFinite(rawDays) && rawDays >= 0 ? Math.min(365, Math.floor(rawDays)) : 14;

    const { botState, resetAt, setups, dmRows, cutoffStr } = await loadClosedSetupsAndState(days);
    const todayPktStr = toPktDateStr(new Date());
    const activeLogin = Number(botState?.mt5Login ?? 0);
    const liveEquity = Number(botState?.equity ?? 0);
    const baseInitialEq = Number(botState?.initialBalance ?? 10000);

    // Aggregate real closed setups strictly by PKT trading date (only post-reset setups)
    const setupsByDate = new Map<string, ClosedSetup[]>();
    for (const s of setups) {
      const list = setupsByDate.get(s.pktDate) ?? [];
      list.push(s);
      setupsByDate.set(s.pktDate, list);
    }

    const dmByDate = new Map<string, { startEquity: number; currentEquity: number; maxDrawdownPercent: number }>();
    for (const m of dmRows) {
      const dStr = String(m.tradingDate).slice(0, 10);
      if (dStr < cutoffStr) continue;
      if (resetAt && m.updatedAt && new Date(m.updatedAt).getTime() < resetAt.getTime()) continue;
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

    // Strictly emit dates that have real closed setups after reset
    const sortedDates = Array.from(setupsByDate.keys()).sort((a, b) => (a < b ? 1 : a > b ? -1 : 0));

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

    const { botState, accStateRow, resetAt, setups, openRows, dmRows, cutoffStr } = await loadClosedSetupsAndState(days);

    const profits = setups.map((s) => s.profit);
    const totalTrades = profits.length;
    const winning = profits.filter((p) => p > 0);
    const losing = profits.filter((p) => p < 0);
    const totalPnl = Number(profits.reduce((a, b) => a + b, 0).toFixed(2));
    const grossWin = winning.reduce((a, b) => a + b, 0);
    const grossLoss = Math.abs(losing.reduce((a, b) => a + b, 0));
    const profitFactor = grossLoss > 0 ? Number((grossWin / grossLoss).toFixed(2)) : grossWin > 0 ? 9.99 : 0;

    // Chronological cumulative realized P&L curve for Metrics Chart
    const baseEquity = Number(accStateRow?.initial_balance ?? botState?.initialBalance ?? 10000) || 10000;
    const chronoSetups = [...setups].sort((a, b) => a.closeTime.getTime() - b.closeTime.getTime());
    let cum = 0;
    let peak = 0;
    let maxDropUsd = 0;
    const equityCurve: Array<{
      label: string;
      pktTime: string;
      tradePnl: number;
      cumPnl: number;
      symbol: string;
      orderType: string;
    }> = [];

    if (chronoSetups.length > 0) {
      equityCurve.push({
        label: "Start",
        pktTime: resetAt ? pktTimeFmt.format(resetAt) : "Reset",
        tradePnl: 0,
        cumPnl: 0,
        symbol: "BASELINE",
        orderType: "BASE",
      });
      chronoSetups.forEach((s, i) => {
        cum = Number((cum + s.profit).toFixed(2));
        if (cum > peak) peak = cum;
        if (peak - cum > maxDropUsd) maxDropUsd = peak - cum;
        equityCurve.push({
          label: `#${i + 1}`,
          pktTime: pktTimeFmt.format(s.closeTime),
          tradePnl: s.profit,
          cumPnl: cum,
          symbol: s.symbol,
          orderType: s.orderType,
        });
      });
    }

    const realizedDdPct = baseEquity > 0 ? Number(((maxDropUsd / baseEquity) * 100).toFixed(2)) : 0;
    const activeDatesSet = new Set(setups.map((s) => s.pktDate));
    const dmMaxDd = dmRows
      .filter((r) => {
        const dStr = String(r.tradingDate).slice(0, 10);
        if (dStr < cutoffStr || !activeDatesSet.has(dStr)) return false;
        if (resetAt && r.updatedAt && new Date(r.updatedAt).getTime() < resetAt.getTime()) return false;
        return true;
      })
      .reduce((max, r) => Math.max(max, Number(r.maxDrawdownPercent ?? 0)), 0);

    const liveEqVal = Number(botState?.equity ?? 0);
    const accInitialBal = Number(accStateRow?.initial_balance ?? botState?.initialBalance ?? 10000) || 10000;
    const accMaxPeak = Number(accStateRow?.max_equity_peak ?? botState?.maxEquityPeak ?? accInitialBal) || accInitialBal;
    const accNetProfit = Number((liveEqVal - accInitialBal).toFixed(2));
    const accNetPct = accInitialBal > 0 ? Number(((accNetProfit / accInitialBal) * 100).toFixed(2)) : 0;
    const accOverallDd =
      accInitialBal > 0 && liveEqVal < accInitialBal
        ? Number((((accInitialBal - liveEqVal) / accInitialBal) * 100).toFixed(2))
        : Number(accStateRow?.overall_drawdown ?? botState?.overallDrawdown ?? 0);

    const maxDdComposite =
      totalTrades > 0
        ? Math.max(realizedDdPct, dmMaxDd)
        : 0;

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
      maxDrawdown: Number(maxDdComposite.toFixed(2)),
      // Live real-time active MT5 account snapshot fields
      liveEquity: liveEqVal,
      initialBalance: accInitialBal,
      maxEquityPeak: accMaxPeak,
      overallDrawdown: Number(accOverallDd.toFixed(2)),
      accountNetProfit: accNetProfit,
      accountNetPct: accNetPct,
      dailyDrawdown: Number(botState?.drawdownPercent ?? 0),
      floatingProfit: Number(botState?.floatingProfit ?? 0),
      openTradesCount: openRows.length,
      mt5Login: Number(botState?.mt5Login ?? 0),
      systemStatus: botState?.systemStatus ?? "BOT OFFLINE",
      lastHeartbeat: botState?.lastHeartbeat ? botState.lastHeartbeat.toISOString() : null,
      metricsResetAt: resetAt ? resetAt.toISOString() : null,
      equityCurve,
      recentTrades: setups.slice(0, 20).map((s) => ({
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
