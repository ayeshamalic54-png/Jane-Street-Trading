import os

api_dash_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "api-server", "src", "routes", "dashboard.ts")

with open(api_dash_path, "r", encoding="utf-8") as f:
    content = f.read()

# Add new overall metrics fields to response payload
old_payload = """      tradesToday: botState?.tradesToday ?? 0,
      maxTrades: Number(botState?.maxTrades ?? 3),"""

new_payload = """      tradesToday: botState?.tradesToday ?? 0,
      maxTrades: Number(botState?.maxTrades ?? 3),
      initialBalance: Number(botState?.initialBalance ?? 100000.00),
      overallDrawdown: Number(botState?.overallDrawdown ?? 0.00),
      maxEquityPeak: Number(botState?.maxEquityPeak ?? 0.00),
      mt5Login: botState?.mt5Login ?? 0,"""

if old_payload in content:
    content = content.replace(old_payload, new_payload)
    print("dashboard.ts API route updated with overall gain and drawdown columns.")
else:
    print("old_payload target not found in dashboard.ts!")

# Also fix TS7030 error in dashboard.ts catch block if any (by adding return before res.status(500))
content = content.replace("res.status(500).json({ error: \"Failed to get dashboard data\" });", "return res.status(500).json({ error: \"Failed to get dashboard data\" });")

with open(api_dash_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
