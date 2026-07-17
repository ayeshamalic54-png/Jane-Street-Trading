import os

dash_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "trading-dashboard", "src", "pages", "dashboard.tsx")

with open(dash_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update the destructuring block in Dashboard to include overall variables
old_destruct = """    botOnline,
    autoExecute,
  } = dashboard;"""

new_destruct = """    botOnline,
    autoExecute,
    initialBalance,
    overallDrawdown,
    maxEquityPeak,
    mt5Login,
  } = dashboard;

  const overallGain = equity - (initialBalance ?? 100000.00);
  const overallGainPercent = (initialBalance ?? 100000.00) > 0 ? (overallGain / (initialBalance ?? 100000.00)) * 100 : 0;"""

if old_destruct in content:
    content = content.replace(old_destruct, new_destruct)
    print("dashboard.tsx updated with destructured variables.")
else:
    print("old_destruct target not found in dashboard.tsx!")

# 2. Update the columns layout from 4 to 6 grid items
old_grid_class = '<div className="grid grid-cols-1 md:grid-cols-4 gap-4">'
new_grid_class = '<div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">'

content = content.replace(old_grid_class, new_grid_class, 1)

# 3. Replace Account Equity Card to display mt5Login ID and start balance
old_equity_card = """          <Card className="bg-zinc-900 border-zinc-800 border-t-2 border-t-sky-500 hover:border-sky-400/40 transition-all shadow-[0_4px_24px_rgba(14,165,233,0.06)] rounded-md">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs text-zinc-500 uppercase tracking-wider font-mono">Account Equity</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-mono text-sky-400">{formatMoney(equity)}</div>
              <div className="text-[10px] text-zinc-500 mt-1 font-mono">
                Start: <span className="text-zinc-300">{formatMoney(100000)}</span>
              </div>
            </CardContent>
          </Card>"""

new_equity_card = """          <Card className="bg-zinc-900 border-zinc-800 border-t-2 border-t-sky-500 hover:border-sky-400/40 transition-all shadow-[0_4px_24px_rgba(14,165,233,0.06)] rounded-md">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs text-zinc-500 uppercase tracking-wider font-mono flex items-center justify-between">
                <span>Account Equity</span>
                {mt5Login > 0 && <span className="text-[9px] text-zinc-500 font-mono">ID: {mt5Login}</span>}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-mono text-sky-400">{formatMoney(equity)}</div>
              <div className="text-[10px] text-zinc-500 mt-1 font-mono">
                Start: <span className="text-zinc-300">{formatMoney(initialBalance)}</span>
              </div>
            </CardContent>
          </Card>"""

content = content.replace(old_equity_card, new_equity_card)

# 4. Insert overall gain and drawdown cards inside the grid (right after Daily Drawdown)
old_drawdown_card = """          <Card className="bg-zinc-900 border-zinc-800 border-t-2 border-t-amber-500 hover:border-amber-400/40 transition-all shadow-[0_4px_24px_rgba(245,158,11,0.06)] rounded-md">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs text-zinc-500 uppercase tracking-wider font-mono">Daily Drawdown</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex justify-between items-end">
                <div className="text-2xl font-mono text-amber-400">{drawdownPercent.toFixed(2)}%</div>
                <div className="text-[10px] text-zinc-500 mb-1 font-mono">
                  Halt: <span className="text-amber-500">4.2%</span> · Limit: <span className="text-red-500">5%</span>
                </div>
              </div>
              <Progress value={Math.min((drawdownPercent / 5) * 100, 100)} className="h-1.5 bg-zinc-800 [&>div]:bg-rose-500" />
            </CardContent>
          </Card>"""

new_drawdown_cards = """          <Card className="bg-zinc-900 border-zinc-800 border-t-2 border-t-amber-500 hover:border-amber-400/40 transition-all shadow-[0_4px_24px_rgba(245,158,11,0.06)] rounded-md">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs text-zinc-500 uppercase tracking-wider font-mono">Daily Drawdown</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex justify-between items-end">
                <div className="text-2xl font-mono text-amber-400">{drawdownPercent.toFixed(2)}%</div>
                <div className="text-[10px] text-zinc-500 mb-1 font-mono">
                  Halt: <span className="text-amber-500">4.2%</span> · Limit: <span className="text-red-500">5%</span>
                </div>
              </div>
              <Progress value={Math.min((drawdownPercent / 5) * 100, 100)} className="h-1.5 bg-zinc-800 [&>div]:bg-rose-500" />
            </CardContent>
          </Card>

          <Card className="bg-zinc-900 border-zinc-800 border-t-2 border-t-emerald-500 hover:border-emerald-400/40 transition-all shadow-[0_4px_24px_rgba(16,185,129,0.06)] rounded-md">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs text-zinc-500 uppercase tracking-wider font-mono">Overall Gain</CardTitle>
            </CardHeader>
            <CardContent>
              <div className={cn("text-2xl font-mono font-bold", overallGain >= 0 ? "text-emerald-400" : "text-rose-400")}>
                {overallGain >= 0 ? "+" : ""}{formatMoney(overallGain)}
              </div>
              <div className="text-[10px] text-zinc-500 mt-1 font-mono">
                Gain %: <span className={overallGain >= 0 ? "text-emerald-400" : "text-rose-400"}>{overallGainPercent.toFixed(2)}%</span>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-zinc-900 border-zinc-800 border-t-2 border-t-rose-500 hover:border-rose-400/40 transition-all shadow-[0_4px_24px_rgba(244,63,94,0.06)] rounded-md">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs text-zinc-500 uppercase tracking-wider font-mono">Overall Drawdown</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex justify-between items-end">
                <div className="text-2xl font-mono text-rose-400">{overallDrawdown.toFixed(2)}%</div>
                <div className="text-[10px] text-zinc-500 mb-1 font-mono">
                  Peak: <span className="text-zinc-300">{formatMoney(maxEquityPeak)}</span>
                </div>
              </div>
              <Progress value={Math.min((overallDrawdown / 10) * 100, 100)} className="h-1.5 bg-zinc-800 [&>div]:bg-rose-500" />
            </CardContent>
          </Card>"""

content = content.replace(old_drawdown_card, new_drawdown_cards)

with open(dash_path, "w", encoding="utf-8") as f:
    f.write(content)
print("dashboard.tsx UI updated successfully with overall gain and drawdown cards.")
