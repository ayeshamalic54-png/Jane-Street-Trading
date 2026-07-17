import os

ws_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "api-server", "src", "lib", "ws.ts")

with open(ws_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Lock query to id = 1
old_query = "db.select().from(botStateTable).limit(1),"
new_query = "db.select().from(botStateTable).where(eq(botStateTable.id, 1)).limit(1),"

if old_query in content:
    content = content.replace(old_query, new_query)
    print("ws.ts query locked to id = 1.")
else:
    print("old_query target not found in ws.ts!")

# 2. Make maxTrades dynamic in WS broadcast payload
old_max_trades = "    maxTrades: 3,"
new_max_trades = "    maxTrades: Number(botState?.maxTrades ?? 3),"

if old_max_trades in content:
    content = content.replace(old_max_trades, new_max_trades)
    print("ws.ts maxTrades payload updated to dynamic property.")
else:
    print("old_max_trades target not found in ws.ts!")

with open(ws_path, "w", encoding="utf-8") as f:
    f.write(content)
print("ws.ts updated.")
