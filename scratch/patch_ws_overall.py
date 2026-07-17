import os

ws_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "api-server", "src", "lib", "ws.ts")

with open(ws_path, "r", encoding="utf-8") as f:
    content = f.read()

# Add new overall metrics fields to WebSocket broadcast payload
old_payload = """    tradesToday: botState?.tradesToday ?? 0,
    maxTrades: Number(botState?.maxTrades ?? 3),"""

new_payload = """    tradesToday: botState?.tradesToday ?? 0,
    maxTrades: Number(botState?.maxTrades ?? 3),
    initialBalance: Number(botState?.initialBalance ?? 100000.00),
    overallDrawdown: Number(botState?.overallDrawdown ?? 0.00),
    maxEquityPeak: Number(botState?.maxEquityPeak ?? 0.00),
    mt5Login: botState?.mt5Login ?? 0,"""

if old_payload in content:
    content = content.replace(old_payload, new_payload)
    print("ws.ts updated with overall metrics.")
else:
    print("old_payload target not found in ws.ts!")

with open(ws_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
