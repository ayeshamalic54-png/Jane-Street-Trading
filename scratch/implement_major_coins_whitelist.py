import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """        valid_symbols = []
        for info in symbols_info:
            sym = info["symbol"]
            if sym not in prices:
                continue
            price = prices[sym]
            
            # Filter out expensive assets (> $1000) like BTC/ETH if balance is small (< $100)
            if usdt_balance < 100.0 and price > 1000.0:
                continue
                
            min_notional = info["step_size"] * price
            # We select coins where minimum trade size does not exceed 5x our balance
            if min_notional <= 5.0 * usdt_balance:
                valid_symbols.append(sym)"""

replacement = """        major_whitelist = {"BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "BNBUSDT", "LTCUSDT", "BCHUSDT", "LINKUSDT", "AVAXUSDT", "DOTUSDT", "DOGEUSDT"}
        valid_symbols = []
        for info in symbols_info:
            sym = info["symbol"]
            if sym not in prices:
                continue
            if sym.upper() not in major_whitelist:
                continue
            price = prices[sym]
            
            # Filter out expensive assets (> $1000) like BTC/ETH if balance is small (< $100)
            if usdt_balance < 100.0 and price > 1000.0:
                continue
                
            min_notional = info["step_size"] * price
            # We select coins where minimum trade size does not exceed 5x our balance
            if min_notional <= 5.0 * usdt_balance:
                valid_symbols.append(sym)"""

if target in content:
    content = content.replace(target, replacement)
    print("Whitelist applied successfully.")
else:
    print("Target not found!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
