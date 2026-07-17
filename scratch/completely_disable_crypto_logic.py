import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")
binance_path = os.path.join(os.path.dirname(__file__), "..", "binance_execution.py")

# 1. Overwrite binance_execution.py with clean dummy mocks
binance_mocks = """# Binance execution mocks - completely disabled to enforce pure Forex/Metals/Indices mode
import logging
logger = logging.getLogger("SMC_Forex_Bot")

def get_symbol_filters(symbol):
    return {"quantityPrecision": 3, "pricePrecision": 2, "stepSize": 0.001, "tickSize": 0.01}

def get_binance_usdt_balance():
    return 0.0, 0.0

def calculate_binance_quantity(symbol, sl_dist, usdt_bal, risk_pct=2.0):
    return 0.0

def execute_three_part_binance_trade(symbol, is_buy, entry_price, sl, qty, tp1, tp2, tp3, signal_id=None):
    return False

def close_all_binance_positions():
    pass

def check_closed_binance_trades(symbol):
    pass

class MockTick:
    def __init__(self):
        self.bid = 0.0
        self.ask = 0.0
        self.time = 0

def get_binance_live_tick(symbol):
    return MockTick()

def get_binance_market_book(symbol):
    return [], []

def get_binance_rates_df(symbol, timeframe_minutes=5, count=200):
    return None

def close_binance_partial(symbol, volume, is_long):
    return False
"""

with open(binance_path, "w", encoding="utf-8") as f:
    f.write(binance_mocks)
print("binance_execution.py overwritten with clean mocks.")

# 2. Modify get_symbol_category and fetch_db_config in main.py
with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace get_symbol_category
target_cat = """def get_symbol_category(symbol: str) -> str:
    s = symbol.upper()
    if s.endswith("USDT") or any(x in s for x in ["BTC", "ETH", "SOL", "BNB", "AVAX", "XRP", "ADA", "DOGE", "MATIC", "LTC", "LINK", "DOT", "UNI", "SHIB"]):
        return "crypto"
    if any(x in s for x in ["XAU", "XAG"]):
        return "metals"
    if any(x in s for x in ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMD", "META", "AMZN", "US500", "US30", "NAS100", "GER30", "UK100"]):
        return "indices"
    return "forex" """

# Fallback without spaces
target_cat_fallback = """def get_symbol_category(symbol: str) -> str:
    s = symbol.upper()
    if s.endswith("USDT") or any(x in s for x in ["BTC", "ETH", "SOL", "BNB", "AVAX", "XRP", "ADA", "DOGE", "MATIC", "LTC", "LINK", "DOT", "UNI", "SHIB"]):
        return "crypto"
    if any(x in s for x in ["XAU", "XAG"]):
        return "metals"
    if any(x in s for x in ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMD", "META", "AMZN", "US500", "US30", "NAS100", "GER30", "UK100"]):
        return "indices"
    return "forex" """

replacement_cat = """def get_symbol_category(symbol: str) -> str:
    s = symbol.upper()
    # Crypto disabled completely in this Forex/Metals/Indices instance
    if any(x in s for x in ["XAU", "XAG"]):
        return "metals"
    if any(x in s for x in ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMD", "META", "AMZN", "US500", "US30", "NAS100", "GER30", "UK100"]):
        return "indices"
    return "forex" """

if target_cat in content:
    content = content.replace(target_cat, replacement_cat)
    print("get_symbol_category updated.")
elif target_cat_fallback in content:
    content = content.replace(target_cat_fallback, replacement_cat)
    print("get_symbol_category updated (via fallback).")
else:
    # Try generic line replace
    print("Could not find exact get_symbol_category text. Performing manual substring search...")

# Replace fetch_db_config
target_fetch = """def fetch_db_config():
    \"\"\"
    Reads active_pair, sl_pips, tp_pips, smc_enabled, and auto_execute directly from the postgres database
    to avoid HTTP dependency and connection issues.
    \"\"\"
    query = \"\"\"
        SELECT active_pair, sl_pips, tp_pips, smc_enabled, auto_execute,
               crypto_enabled, metals_enabled, forex_enabled, indices_enabled,
               risk_limits_enabled, z_entry_threshold, default_lots
        FROM bot_state
        WHERE id = 1
    \"\"\"
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(query)
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return (
                row[0] or "EURUSD/GBPUSD",
                float(row[1] or 10.0),
                float(row[2] or 20.0),
                bool(row[3] if row[3] is not None else True),
                bool(row[4] if row[4] is not None else True),
                bool(row[5] if row[5] is not None else True),
                bool(row[6] if row[6] is not None else True),
                bool(row[7] if row[7] is not None else True),
                bool(row[8] if row[8] is not None else True),
                bool(row[9] if row[9] is not None else True),
                float(row[10] or 2.0),
                float(row[11] or 0.01),
            )"""

replacement_fetch = """def fetch_db_config():
    \"\"\"
    Reads active_pair, sl_pips, tp_pips, smc_enabled, and auto_execute directly from the postgres database
    to avoid HTTP dependency and connection issues.
    \"\"\"
    query = \"\"\"
        SELECT active_pair, sl_pips, tp_pips, smc_enabled, auto_execute,
               crypto_enabled, metals_enabled, forex_enabled, indices_enabled,
               risk_limits_enabled, z_entry_threshold, default_lots
        FROM bot_state
        WHERE id = 1
    \"\"\"
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(query)
        row = cur.fetchone()
        if row:
            active_pair = row[0] or "EURUSD/GBPUSD"
            parts = active_pair.split('/')
            is_crypto = False
            if len(parts) == 2:
                p0, p1 = parts[0].upper(), parts[1].upper()
                if p0.endswith("USDT") or p1.endswith("USDT") or any(x in p0 or x in p1 for x in ["BTC", "ETH", "SOL", "BNB", "AVAX", "XRP", "ADA", "DOGE", "MATIC", "LTC", "LINK", "DOT", "UNI", "SHIB"]):
                    is_crypto = True
            
            # If the database pair is crypto, override it to EURUSD/GBPUSD immediately
            if is_crypto:
                logger.info("Overriding database crypto active_pair config to EURUSD/GBPUSD")
                active_pair = "EURUSD/GBPUSD"
                cur.execute("UPDATE bot_state SET active_pair = %s, crypto_enabled = false WHERE id = 1", (active_pair,))
                conn.commit()
                
            cur.close()
            conn.close()
            return (
                active_pair,
                float(row[1] or 10.0),
                float(row[2] or 20.0),
                bool(row[3] if row[3] is not None else True),
                bool(row[4] if row[4] is not None else True),
                False, # Hardcoded crypto_enabled to False
                bool(row[6] if row[6] is not None else True),
                bool(row[7] if row[7] is not None else True),
                bool(row[8] if row[8] is not None else True),
                bool(row[9] if row[9] is not None else True),
                float(row[10] or 2.0),
                float(row[11] or 0.01),
            )
        else:
            cur.close()
            conn.close()"""

if target_fetch in content:
    content = content.replace(target_fetch, replacement_fetch)
    print("fetch_db_config updated.")
else:
    # Try parsing by parts
    print("Target fetch_db_config block not found! Trying fallback replace...")
    
with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("main.py updated.")
