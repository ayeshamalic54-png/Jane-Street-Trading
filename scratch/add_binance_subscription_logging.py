import os

di_path = os.path.join(os.path.dirname(__file__), "..", "data_ingestion.py")
main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

# 1. Update data_ingestion.py
with open(di_path, "r", encoding="utf-8") as f:
    di_content = f.read()

sub_func = """SUBSCRIBED_BINANCE_SYMBOLS = set()

def check_and_subscribe_binance_symbol(symbol):
    \"\"\"Logs order book subscription for Binance symbols, matching the Forex MT5 logging format.\"\"\"
    symbol_upper = symbol.upper()
    if symbol_upper in SUBSCRIBED_BINANCE_SYMBOLS:
        return True
    logger.info(f"Subscribed to Order Book updates for {symbol_upper}")
    SUBSCRIBED_BINANCE_SYMBOLS.add(symbol_upper)
    return True
"""

if "def check_and_subscribe_binance_symbol" not in di_content:
    di_content += "\n" + sub_func
    print("Added function to data_ingestion.py")
else:
    print("Function already in data_ingestion.py")

with open(di_path, "w", encoding="utf-8") as f:
    f.write(di_content)

# 2. Update main.py imports
with open(main_path, "r", encoding="utf-8") as f:
    main_content = f.read()

import_target = "from data_ingestion import initialize_mt5, check_and_subscribe_symbol,"
import_replacement = "from data_ingestion import initialize_mt5, check_and_subscribe_symbol, check_and_subscribe_binance_symbol,"

if import_target in main_content and "check_and_subscribe_binance_symbol" not in main_content:
    main_content = main_content.replace(import_target, import_replacement)
    print("Import updated in main.py")
else:
    print("Import target not found or already updated in main.py")

# 3. Update main.py scanning loop to call the subscription logger for Binance symbols
loop_target = """                    if cat_a == "crypto":
                        tick_a_scan = get_binance_live_tick(s_a_resolved)
                        bids_a_scan, asks_a_scan = get_binance_market_book(s_a_resolved)"""

loop_replacement = """                    if cat_a == "crypto":
                        check_and_subscribe_binance_symbol(s_a_resolved)
                        tick_a_scan = get_binance_live_tick(s_a_resolved)
                        bids_a_scan, asks_a_scan = get_binance_market_book(s_a_resolved)"""

loop_target2 = """                    if cat_b == "crypto":
                        tick_b_scan = get_binance_live_tick(s_b_resolved)
                        bids_b_scan, asks_b_scan = get_binance_market_book(s_b_resolved)"""

loop_replacement2 = """                    if cat_b == "crypto":
                        check_and_subscribe_binance_symbol(s_b_resolved)
                        tick_b_scan = get_binance_live_tick(s_b_resolved)
                        bids_b_scan, asks_b_scan = get_binance_market_book(s_b_resolved)"""

if loop_target in main_content:
    main_content = main_content.replace(loop_target, loop_replacement)
    print("Loop target A replaced.")
if loop_target2 in main_content:
    main_content = main_content.replace(loop_target2, loop_replacement2)
    print("Loop target B replaced.")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(main_content)
print("Files updated successfully.")
