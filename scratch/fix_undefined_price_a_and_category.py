import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Fix get_symbol_category to respect OVERRIDE_CRYPTO_ENABLED
target_cat = """def get_symbol_category(symbol: str) -> str:
    s = symbol.upper()"""

replacement_cat = """def get_symbol_category(symbol: str) -> str:
    if os.getenv("OVERRIDE_CRYPTO_ENABLED") == "True":
        return "crypto"
    s = symbol.upper()"""

if target_cat in content:
    content = content.replace(target_cat, replacement_cat)
    print("get_symbol_category updated.")
else:
    print("get_symbol_category target not found!")

# 2. Define price_a in BUY loop (is_long = True)
target_price_a_buy = """                                usdt_bal, _ = get_binance_usdt_balance()
                                qty_a = calculate_binance_quantity(temp_s_a, sl_dist, usdt_bal, current_price=float(best_sig["price_a"]), risk_pct=2.0)"""

replacement_price_a_buy = """                                usdt_bal, _ = get_binance_usdt_balance()
                                price_a = float(best_sig["price_a"])
                                qty_a = calculate_binance_quantity(temp_s_a, sl_dist, usdt_bal, current_price=price_a, risk_pct=2.0)"""

if target_price_a_buy in content:
    content = content.replace(target_price_a_buy, replacement_price_a_buy)
    print("price_a defined in BUY loop.")
else:
    print("price_a BUY loop target not found!")

# 3. Define price_a in SELL loop (is_long = False)
target_price_a_sell = """                            if best_cat_a == "crypto":
                                usdt_bal, _ = get_binance_usdt_balance()
                                qty_a = calculate_binance_quantity(temp_s_a, sl_dist, usdt_bal, current_price=float(best_sig["price_a"]), risk_pct=2.0)"""

replacement_price_a_sell = """                            if best_cat_a == "crypto":
                                usdt_bal, _ = get_binance_usdt_balance()
                                price_a = float(best_sig["price_a"])
                                qty_a = calculate_binance_quantity(temp_s_a, sl_dist, usdt_bal, current_price=price_a, risk_pct=2.0)"""

if target_price_a_sell in content:
    content = content.replace(target_price_a_sell, replacement_price_a_sell)
    print("price_a defined in SELL loop.")
else:
    print("price_a SELL loop target not found!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
