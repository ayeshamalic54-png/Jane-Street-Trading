import os

dashboard_api_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "api-server", "src", "routes", "dashboard.ts")

with open(dashboard_api_path, "r", encoding="utf-8") as f:
    content = f.read()

old_max_trades = "      maxTrades: 3,"
new_max_trades = "      maxTrades: Number(botState?.maxTrades ?? 3),"

if old_max_trades in content:
    content = content.replace(old_max_trades, new_max_trades)
    print("dashboard.ts maxTrades value updated to dynamic database property.")
else:
    print("Target not found in dashboard.ts!")

with open(dashboard_api_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
