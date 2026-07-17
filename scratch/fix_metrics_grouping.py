import os

metrics_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "api-server", "src", "routes", "metrics.ts")

with open(metrics_path, "r", encoding="utf-8") as f:
    content = f.read()

# Locate the metrics/summary logic and replace it with grouping by signalId
old_logic = """    const closed = rows.filter((t) => t.status === "CLOSED" && t.profit != null);
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
    });"""

new_logic = """    const closed = rows.filter((t) => t.status === "CLOSED" && t.profit != null);
    
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
    });"""

if old_logic in content:
    content = content.replace(old_logic, new_logic)
    print("metrics.ts updated to group trades by signalId.")
else:
    print("old_logic target not found in metrics.ts!")

with open(metrics_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
