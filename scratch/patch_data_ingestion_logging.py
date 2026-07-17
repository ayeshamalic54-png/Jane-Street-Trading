import os

ingest_path = os.path.join(os.path.dirname(__file__), "..", "data_ingestion.py")

with open(ingest_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Change logger.error to logger.debug for invalid symbols in check_and_subscribe_symbol
old_error_log = '        logger.error(f"Symbol {resolved} is invalid or not found in the broker\'s database.")'
new_debug_log = '        logger.debug(f"Symbol {resolved} is invalid or not found in the broker\'s database.")'

if old_error_log in content:
    content = content.replace(old_error_log, new_debug_log)
    print("Changed invalid symbol log level to DEBUG.")
else:
    print("old_error_log not found in data_ingestion.py!")

# 2. Add check_and_subscribe_symbol check at the start of get_rates_df
old_rates_func = """def get_rates_df(symbol, timeframe, count=200):
    \"\"\"Fetches historical price candles and returns them as a pandas DataFrame.\"\"\"
    resolved = resolve_broker_symbol(symbol)
    rates = mt5.copy_rates_from_pos(resolved, timeframe, 0, count)"""

new_rates_func = """def get_rates_df(symbol, timeframe, count=200):
    \"\"\"Fetches historical price candles and returns them as a pandas DataFrame.\"\"\"
    resolved = resolve_broker_symbol(symbol)
    if not check_and_subscribe_symbol(resolved):
        return None
    rates = mt5.copy_rates_from_pos(resolved, timeframe, 0, count)"""

if old_rates_func in content:
    content = content.replace(old_rates_func, new_rates_func)
    print("Added check_and_subscribe_symbol guard to get_rates_df.")
else:
    print("old_rates_func not found in data_ingestion.py!")

# 3. Add check_and_subscribe_symbol check at the start of get_live_ticks
old_ticks_func = """def get_live_ticks(symbol):
    \"\"\"Fetches the latest tick (bid, ask, time) for a symbol.\"\"\"
    resolved = resolve_broker_symbol(symbol)
    tick = mt5.symbol_info_tick(resolved)"""

new_ticks_func = """def get_live_ticks(symbol):
    \"\"\"Fetches the latest tick (bid, ask, time) for a symbol.\"\"\"
    resolved = resolve_broker_symbol(symbol)
    if not check_and_subscribe_symbol(resolved):
        return None
    tick = mt5.symbol_info_tick(resolved)"""

if old_ticks_func in content:
    content = content.replace(old_ticks_func, new_ticks_func)
    print("Added check_and_subscribe_symbol guard to get_live_ticks.")
else:
    print("old_ticks_func not found in data_ingestion.py!")

with open(ingest_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
