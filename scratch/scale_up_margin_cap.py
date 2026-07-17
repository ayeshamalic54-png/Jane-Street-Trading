import os

binance_path = os.path.join(os.path.dirname(__file__), "..", "binance_execution.py")

with open(binance_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """        # Enforce maximum notional value of 35% of available buying power at 20x leverage (i.e. 7 * balance)
        max_notional = usdt_balance * 7.0"""

replacement = """        # Enforce maximum notional value of 80% of available buying power at 20x leverage (i.e. 16 * balance)
        max_notional = usdt_balance * 16.0"""

if target in content:
    content = content.replace(target, replacement)
    print("Replacement successful.")
else:
    print("Target not found!")

with open(binance_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
