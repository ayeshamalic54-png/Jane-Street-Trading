import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update binance_execution import block to include PUBLIC_BASE_URL
target_import = """from binance_execution import (
    get_binance_usdt_balance,
    calculate_binance_quantity,
    execute_three_part_binance_trade,
    close_all_binance_positions,
    check_closed_binance_trades,
    send_signed_request,
    set_binance_leverage,
    get_binance_live_tick,
    get_binance_market_book,
    get_symbol_filters,
    get_binance_rates_df,
    close_binance_partial,
    get_symbol_filters
)"""

replacement_import = """from binance_execution import (
    get_binance_usdt_balance,
    calculate_binance_quantity,
    execute_three_part_binance_trade,
    close_all_binance_positions,
    check_closed_binance_trades,
    send_signed_request,
    set_binance_leverage,
    get_binance_live_tick,
    get_binance_market_book,
    get_symbol_filters,
    get_binance_rates_df,
    close_binance_partial,
    PUBLIC_BASE_URL
)"""

# 2. Update requests urls in get_dynamic_crypto_candidate_pairs
target_reqs = """        r = requests.get("https://fapi.binance.com/fapi/v1/exchangeInfo", timeout=10)"""
replacement_reqs = """        r = requests.get(f"{PUBLIC_BASE_URL}/exchangeInfo", timeout=10)"""

target_reqs2 = """        price_res = requests.get("https://fapi.binance.com/fapi/v1/ticker/price", timeout=10)"""
replacement_reqs2 = """        price_res = requests.get(f"{PUBLIC_BASE_URL}/ticker/price", timeout=10)"""

target_reqs3 = """        vol_res = requests.get("https://fapi.binance.com/fapi/v1/ticker/24hr", timeout=10)"""
replacement_reqs3 = """        vol_res = requests.get(f"{PUBLIC_BASE_URL}/ticker/24hr", timeout=10)"""

if target_import in content:
    content = content.replace(target_import, replacement_import)
    print("Import updated.")
else:
    print("Import target not found!")

if target_reqs in content:
    content = content.replace(target_reqs, replacement_reqs)
    print("exchangeInfo URL updated.")
else:
    print("exchangeInfo URL target not found!")

if target_reqs2 in content:
    content = content.replace(target_reqs2, replacement_reqs2)
    print("ticker/price URL updated.")
else:
    print("ticker/price URL target not found!")

if target_reqs3 in content:
    content = content.replace(target_reqs3, replacement_reqs3)
    print("ticker/24hr URL updated.")
else:
    print("ticker/24hr URL target not found!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
