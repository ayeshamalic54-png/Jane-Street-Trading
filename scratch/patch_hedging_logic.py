import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Insert the helper function get_hedge_execution_parameters before get_hedge_quantity
old_target = "def get_hedge_quantity("
helper_code = """def get_hedge_execution_parameters(action_spread: str, beta: float, tick_b) -> tuple:
    \"\"\"
    Returns (order_type, side, price, sl_sign) for Leg B order
    taking into account spread action and correlation (sign of beta).
    \"\"\"
    is_buy_spread = (action_spread == "BUY_SPREAD")
    # For positive correlation (beta >= 0), Leg B is traded in opposite direction of Leg A
    # For negative correlation (beta < 0), Leg B is traded in same direction as Leg A
    if beta >= 0:
        if is_buy_spread:
            return 1, "SELL", float(tick_b.bid), 1.0  # mt5.ORDER_TYPE_SELL = 1
        else:
            return 0, "BUY", float(tick_b.ask), -1.0  # mt5.ORDER_TYPE_BUY = 0
    else:
        if is_buy_spread:
            return 0, "BUY", float(tick_b.ask), -1.0  # mt5.ORDER_TYPE_BUY = 0
        else:
            return 1, "SELL", float(tick_b.bid), 1.0  # mt5.ORDER_TYPE_SELL = 1

"""

if old_target in content and "get_hedge_execution_parameters" not in content:
    content = content.replace(old_target, helper_code + old_target)
    print("get_hedge_execution_parameters helper added to main.py.")
else:
    print("get_hedge_execution_parameters already exists or target not found.")

# 2. Patch Block 1: Crypto BUY_SPREAD Leg B (lines 1347-1357)
old_block_1 = """                                if best_cat_b == "crypto":
                                    hedge_params = {"symbol": S_B, "side": "SELL", "type": "MARKET", "quantity": qty_b}
                                    h_res = send_signed_request("POST", "/fapi/v1/order", hedge_params)
                                    if h_res and h_res.status_code == 200:
                                        log_trade_entry(h_res.json()["orderId"], S_B, "SELL", qty_b, float(h_res.json().get("avgPrice") or best_sig["tick_b"].bid), datetime.datetime.now(), "Binance JS_HEDGE", signal_id)
                                        price_prec = get_symbol_filters(S_B)["pricePrecision"] if get_symbol_filters(S_B) else 2
                                        send_signed_request("POST", "/fapi/v1/order", {"symbol": S_B, "side": "BUY", "type": "STOP_MARKET", "stopPrice": round(best_sig["tick_b"].bid + sl_dist_b, price_prec), "closePosition": "true", "timeInForce": "GTC"})
                                else:
                                    res_hedge = send_order(S_B, mt5.ORDER_TYPE_SELL, best_sig["tick_b"].bid, qty_b, best_sig["tick_b"].bid + sl_dist_b, 0.0, "JS_HEDGE")
                                    if res_hedge and res_hedge.retcode == mt5.TRADE_RETCODE_DONE:
                                        log_trade_entry(res_hedge.order, S_B, "SELL", qty_b, res_hedge.price, datetime.datetime.now(), "JS_HEDGE", signal_id)"""

new_block_1 = """                                order_type_b, side_b, price_b, sl_sign_b = get_hedge_execution_parameters(best_action, best_sig["beta"], best_sig["tick_b"])
                                sl_b = price_b + sl_sign_b * sl_dist_b
                                if best_cat_b == "crypto":
                                    hedge_params = {"symbol": S_B, "side": side_b, "type": "MARKET", "quantity": qty_b}
                                    h_res = send_signed_request("POST", "/fapi/v1/order", hedge_params)
                                    if h_res and h_res.status_code == 200:
                                        avg_price_b = float(h_res.json().get("avgPrice") or price_b)
                                        log_trade_entry(h_res.json()["orderId"], S_B, side_b, qty_b, avg_price_b, datetime.datetime.now(), "Binance JS_HEDGE", signal_id)
                                        price_prec = get_symbol_filters(S_B)["pricePrecision"] if get_symbol_filters(S_B) else 2
                                        opp_side_b = "BUY" if side_b == "SELL" else "SELL"
                                        send_signed_request("POST", "/fapi/v1/order", {"symbol": S_B, "side": opp_side_b, "type": "STOP_MARKET", "stopPrice": round(sl_b, price_prec), "closePosition": "true", "timeInForce": "GTC"})
                                else:
                                    res_hedge = send_order(S_B, order_type_b, price_b, qty_b, sl_b, 0.0, "JS_HEDGE")
                                    if res_hedge and res_hedge.retcode == mt5.TRADE_RETCODE_DONE:
                                        log_trade_entry(res_hedge.order, S_B, side_b, qty_b, res_hedge.price, datetime.datetime.now(), "JS_HEDGE", signal_id)"""

if old_block_1 in content:
    content = content.replace(old_block_1, new_block_1)
    print("Block 1 patched.")
else:
    print("Block 1 not found.")

# 3. Patch Block 2: Forex/Metals BUY_SPREAD Leg B (lines 1375-1385)
old_block_2 = """                                if best_cat_b == "crypto":
                                    hedge_params = {"symbol": S_B, "side": "SELL", "type": "MARKET", "quantity": qty_b}
                                    h_res = send_signed_request("POST", "/fapi/v1/order", hedge_params)
                                    if h_res and h_res.status_code == 200:
                                        log_trade_entry(h_res.json()["orderId"], S_B, "SELL", qty_b, float(h_res.json().get("avgPrice") or best_sig["tick_b"].bid), datetime.datetime.now(), "Binance JS_HEDGE", signal_id)
                                        price_prec = get_symbol_filters(S_B)["pricePrecision"] if get_symbol_filters(S_B) else 2
                                        send_signed_request("POST", "/fapi/v1/order", {"symbol": S_B, "side": "BUY", "type": "STOP_MARKET", "stopPrice": round(best_sig["tick_b"].bid + sl_dist_b, price_prec), "closePosition": "true", "timeInForce": "GTC"})
                                else:
                                    res_hedge = send_order(S_B, mt5.ORDER_TYPE_SELL, best_sig["tick_b"].bid, qty_b, best_sig["tick_b"].bid + sl_dist_b, 0.0, "JS_HEDGE")
                                    if res_hedge and res_hedge.retcode == mt5.TRADE_RETCODE_DONE:
                                        log_trade_entry(res_hedge.order, S_B, "SELL", qty_b, res_hedge.price, datetime.datetime.now(), "JS_HEDGE", signal_id)"""

# We can replace the second occurrence too (since it is identical to old_block_1, content.replace would have replaced it if we set count, or let's target it specifically)
# Actually, content.replace(old_block_1, new_block_1) replaces ALL occurrences by default in Python!
# Let's verify if Block 2 was also replaced since they are identical text blocks.
# Yes, they are identical! Python's replace() will replace both.

# 4. Patch Block 3: Crypto/Forex SELL_SPREAD Leg B (lines 1397-1407 and 1425-1435)
old_block_3 = """                                if best_cat_b == "crypto":
                                    hedge_params = {"symbol": S_B, "side": "BUY", "type": "MARKET", "quantity": qty_b}
                                    h_res = send_signed_request("POST", "/fapi/v1/order", hedge_params)
                                    if h_res and h_res.status_code == 200:
                                        log_trade_entry(h_res.json()["orderId"], S_B, "BUY", qty_b, float(h_res.json().get("avgPrice") or best_sig["tick_b"].ask), datetime.datetime.now(), "Binance JS_HEDGE", signal_id)
                                        price_prec = get_symbol_filters(S_B)["pricePrecision"] if get_symbol_filters(S_B) else 2
                                        send_signed_request("POST", "/fapi/v1/order", {"symbol": S_B, "side": "SELL", "type": "STOP_MARKET", "stopPrice": round(best_sig["tick_b"].ask - sl_dist_b, price_prec), "closePosition": "true", "timeInForce": "GTC"})
                                else:
                                    res_hedge = send_order(S_B, mt5.ORDER_TYPE_BUY, best_sig["tick_b"].ask, qty_b, best_sig["tick_b"].ask - sl_dist_b, 0.0, "JS_HEDGE")
                                    if res_hedge and res_hedge.retcode == mt5.TRADE_RETCODE_DONE:
                                        log_trade_entry(res_hedge.order, S_B, "BUY", qty_b, res_hedge.price, datetime.datetime.now(), "JS_HEDGE", signal_id)"""

new_block_3 = """                                order_type_b, side_b, price_b, sl_sign_b = get_hedge_execution_parameters(best_action, best_sig["beta"], best_sig["tick_b"])
                                sl_b = price_b + sl_sign_b * sl_dist_b
                                if best_cat_b == "crypto":
                                    hedge_params = {"symbol": S_B, "side": side_b, "type": "MARKET", "quantity": qty_b}
                                    h_res = send_signed_request("POST", "/fapi/v1/order", hedge_params)
                                    if h_res and h_res.status_code == 200:
                                        avg_price_b = float(h_res.json().get("avgPrice") or price_b)
                                        log_trade_entry(h_res.json()["orderId"], S_B, side_b, qty_b, avg_price_b, datetime.datetime.now(), "Binance JS_HEDGE", signal_id)
                                        price_prec = get_symbol_filters(S_B)["pricePrecision"] if get_symbol_filters(S_B) else 2
                                        opp_side_b = "BUY" if side_b == "SELL" else "SELL"
                                        send_signed_request("POST", "/fapi/v1/order", {"symbol": S_B, "side": opp_side_b, "type": "STOP_MARKET", "stopPrice": round(sl_b, price_prec), "closePosition": "true", "timeInForce": "GTC"})
                                else:
                                    res_hedge = send_order(S_B, order_type_b, price_b, qty_b, sl_b, 0.0, "JS_HEDGE")
                                    if res_hedge and res_hedge.retcode == mt5.TRADE_RETCODE_DONE:
                                        log_trade_entry(res_hedge.order, S_B, side_b, qty_b, res_hedge.price, datetime.datetime.now(), "JS_HEDGE", signal_id)"""

if old_block_3 in content:
    content = content.replace(old_block_3, new_block_3)
    print("Block 3 & 4 patched.")
else:
    print("Block 3 & 4 not found.")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
