import os

binance_path = os.path.join(os.path.dirname(__file__), "..", "binance_execution.py")

with open(binance_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """            if history_res is not None and history_res.status_code == 200:
                trades_history = history_res.json()
                if trades_history:
                    # Find exit price and sum total realized profit
                    close_price = float(trades_history[0].get("price", 0.0))
                    profit = sum(float(t.get("realizedProfit", 0.0)) for t in trades_history)
                    close_time = datetime.datetime.fromtimestamp(int(trades_history[0].get("time")) / 1000.0)"""

replacement = """            if history_res is not None and history_res.status_code == 200:
                trades_history = history_res.json()
                if trades_history:
                    # Find exit price and sum total realized profit
                    close_price = float(trades_history[-1].get("price", 0.0))
                    profit = sum(float(t.get("realizedProfit", 0.0)) for t in trades_history)
                    close_time = datetime.datetime.fromtimestamp(int(trades_history[-1].get("time")) / 1000.0)"""

if target in content:
    content = content.replace(target, replacement)
    print("Replacement successful.")
else:
    print("Target not found!")

with open(binance_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
