import os

binance_path = os.path.join(os.path.dirname(__file__), "..", "binance_execution.py")

with open(binance_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """def get_binance_usdt_balance():"""

replacement = """LEVERAGE_BRACKETS_CACHE = {}

def load_leverage_brackets():
    \"\"\"Fetches and caches leverage brackets for all symbols on startup.\"\"\"
    global LEVERAGE_BRACKETS_CACHE
    try:
        res = send_signed_request("GET", "/fapi/v1/leverageBracket")
        if res is not None and res.status_code == 200:
            data = res.json()
            for entry in data:
                symbol = entry.get("symbol")
                brackets = entry.get("brackets", [])
                # Map leverage to notionalCap
                lev_map = {}
                for b in brackets:
                    lev = int(b.get("initialLeverage", 20))
                    cap = float(b.get("notionalCap", 10000.0))
                    lev_map[lev] = cap
                LEVERAGE_BRACKETS_CACHE[symbol] = lev_map
            logger.info("Successfully cached leverage brackets for all Binance symbols.")
    except Exception as e:
        logger.error(f"Error loading leverage brackets: {e}")

def get_max_notional(symbol, leverage=20):
    \"\"\"Returns the maximum allowed notional value for a symbol at a given leverage.\"\"\"
    if not LEVERAGE_BRACKETS_CACHE:
        load_leverage_brackets()
    
    symbol = symbol.upper()
    if symbol in LEVERAGE_BRACKETS_CACHE:
        lev_map = LEVERAGE_BRACKETS_CACHE[symbol]
        if leverage in lev_map:
            return lev_map[leverage]
        else:
            sorted_keys = sorted(lev_map.keys())
            for k in sorted_keys:
                if k >= leverage:
                    return lev_map[k]
            if sorted_keys:
                return lev_map[sorted_keys[-1]]
    return 10000.0

def get_binance_usdt_balance():"""

if target in content:
    content = content.replace(target, replacement)
    print("Leverage brackets functions added to binance_execution.py.")
else:
    print("Target not found!")

with open(binance_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
