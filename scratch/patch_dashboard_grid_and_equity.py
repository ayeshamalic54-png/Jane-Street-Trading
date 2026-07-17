import os

dash_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "trading-dashboard", "src", "pages", "dashboard.tsx")

with open(dash_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update columns layout in dashboard.tsx (handling whitespace)
content = content.replace(
    '        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">',
    '        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">'
)

# 2. Update Account Equity Card in dashboard.tsx
old_equity_card = """          <Card className="bg-zinc-900 border-zinc-800 border-t-2 border-t-sky-500 hover:border-sky-400/40 transition-all shadow-[0_4px_24px_rgba(14,165,233,0.06)] rounded-md">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs text-zinc-500 uppercase tracking-wider font-mono">Account Equity</CardTitle>
            </CardHeader>
            <CardContent className="pb-2">
              <div className="text-2xl font-mono text-sky-400 font-bold">{formatMoney(equity)}</div>"""

new_equity_card = """          <Card className="bg-zinc-900 border-zinc-800 border-t-2 border-t-sky-500 hover:border-sky-400/40 transition-all shadow-[0_4px_24px_rgba(14,165,233,0.06)] rounded-md">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs text-zinc-500 uppercase tracking-wider font-mono flex items-center justify-between">
                <span>Account Equity</span>
                {mt5Login > 0 && <span className="text-[9px] text-zinc-500 font-mono">ID: {mt5Login}</span>}
              </CardTitle>
            </CardHeader>
            <CardContent className="pb-2">
              <div className="text-2xl font-mono text-sky-400 font-bold">{formatMoney(equity)}</div>
              <div className="text-[10px] text-zinc-500 mt-1 mb-2 font-mono">
                Start: <span className="text-zinc-300">{formatMoney(initialBalance)}</span>
              </div>"""

if old_equity_card in content:
    content = content.replace(old_equity_card, new_equity_card)
    print("Account Equity Card updated in dashboard.tsx.")
else:
    print("old_equity_card target not found in dashboard.tsx!")

with open(dash_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
