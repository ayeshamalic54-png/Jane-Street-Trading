import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")
binance_path = os.path.join(os.path.dirname(__file__), "..", "binance_execution.py")

# ==========================================
# 1. FIX BINANCE_EXECUTION.PY
# ==========================================
with open(binance_path, "r", encoding="utf-8") as f:
    bin_content = f.read()

bin_target = """    sl_params = {
        "symbol": symbol,
        "side": reverse_side,
        "type": "STOP_MARKET",
        "stopPrice": round(round(sl_price / tick_size) * tick_size, price_prec),
        "closePosition": "true"
    }
    sl_res = send_signed_request("POST", "/fapi/v1/order", sl_params)"""

bin_replacement = """    sl_params = {
        "symbol": symbol,
        "algoType": "CONDITIONAL",
        "side": reverse_side,
        "type": "STOP_MARKET",
        "triggerPrice": round(round(sl_price / tick_size) * tick_size, price_prec),
        "closePosition": "true"
    }
    sl_res = send_signed_request("POST", "/fapi/v1/algoOrder", sl_params)"""

if bin_target in bin_content:
    bin_content = bin_content.replace(bin_target, bin_replacement)
    print("binance_execution.py replacement successful.")
else:
    print("binance_execution.py target not found!")

with open(binance_path, "w", encoding="utf-8") as f:
    f.write(bin_content)

# ==========================================
# 2. FIX MAIN.PY
# ==========================================
with open(main_path, "r", encoding="utf-8") as f:
    main_content = f.read()

# Delete local import that causes UnboundLocalError
import_target = "                        from binance_execution import send_signed_request"
if import_target in main_content:
    main_content = main_content.replace(import_target, "")
    print("main.py local import removal successful.")
else:
    print("main.py local import target not found!")

# Replace STOP_MARKET targets
sl_buy_target = 'send_signed_request("POST", "/fapi/v1/order", {"symbol": temp_s_b, "side": "BUY", "type": "STOP_MARKET", "stopPrice": round(best_sig["tick_b"].bid + sl_dist_b, price_prec), "closePosition": "true", "timeInForce": "GTC"})'
sl_buy_replacement = 'send_signed_request("POST", "/fapi/v1/algoOrder", {"symbol": temp_s_b, "algoType": "CONDITIONAL", "side": "BUY", "type": "STOP_MARKET", "triggerPrice": round(best_sig["tick_b"].bid + sl_dist_b, price_prec), "closePosition": "true"})'

sl_sell_target = 'send_signed_request("POST", "/fapi/v1/order", {"symbol": temp_s_b, "side": "SELL", "type": "STOP_MARKET", "stopPrice": round(best_sig["tick_b"].ask - sl_dist_b, price_prec), "closePosition": "true", "timeInForce": "GTC"})'
sl_sell_replacement = 'send_signed_request("POST", "/fapi/v1/algoOrder", {"symbol": temp_s_b, "algoType": "CONDITIONAL", "side": "SELL", "type": "STOP_MARKET", "triggerPrice": round(best_sig["tick_b"].ask - sl_dist_b, price_prec), "closePosition": "true"})'

# Let's count target matches first
buy_matches = main_content.count(sl_buy_target)
sell_matches = main_content.count(sl_sell_target)
print(f"main.py: Found {buy_matches} BUY stop targets, {sell_matches} SELL stop targets.")

main_content = main_content.replace(sl_buy_target, sl_buy_replacement)
main_content = main_content.replace(sl_sell_target, sl_sell_replacement)

with open(main_path, "w", encoding="utf-8") as f:
    f.write(main_content)
print("main.py updated.")
