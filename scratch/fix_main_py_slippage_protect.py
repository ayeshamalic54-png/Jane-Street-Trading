import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

# Target 1: BUY spread execution block
target_buy = """                                qty_b = get_hedge_quantity(temp_s_a, temp_s_b, qty_a, best_sig["beta"], best_cat_a, best_cat_b)
                                
                                signal_id = do_log_signal()"""

replacement_buy = """        qty_b = get_hedge_quantity(temp_s_a, temp_s_b, qty_a, best_sig["beta"], best_cat_a, best_cat_b)
                                
                                # Fetch latest live ticks to ensure no slippage has breached SL before entry
                                tick_a_live = get_binance_live_tick(temp_s_a)
                                tick_b_live = get_binance_live_tick(temp_s_b)
                                if tick_a_live and tick_b_live:
                                    price_a_live = tick_a_live.ask
                                    price_b_live = tick_b_live.bid
                                    sl_a = price_a_live - sl_dist
                                    sl_b = price_b_live + sl_dist_b
                                    if (price_a_live <= sl_a) or (price_b_live >= sl_b):
                                        logger.warning(f"[SLIPPAGE PROTECT] Skipping entry for {temp_s_a}/{temp_s_b} because live price is already past Stop Loss due to volatility.")
                                        continue
                                
                                signal_id = do_log_signal()"""

# Target 2: SELL spread execution block
target_sell = """                                qty_b = get_hedge_quantity(temp_s_a, temp_s_b, qty_a, best_sig["beta"], best_cat_a, best_cat_b)
                                
                                signal_id = do_log_signal()
                                if execute_three_part_binance_trade(
                                    temp_s_a, False,"""

replacement_sell = """        qty_b = get_hedge_quantity(temp_s_a, temp_s_b, qty_a, best_sig["beta"], best_cat_a, best_cat_b)
                                
                                # Fetch latest live ticks to ensure no slippage has breached SL before entry
                                tick_a_live = get_binance_live_tick(temp_s_a)
                                tick_b_live = get_binance_live_tick(temp_s_b)
                                if tick_a_live and tick_b_live:
                                    price_a_live = tick_a_live.bid
                                    price_b_live = tick_b_live.ask
                                    sl_a = price_a_live + sl_dist
                                    sl_b = price_b_live - sl_dist_b
                                    if (price_a_live >= sl_a) or (price_b_live <= sl_b):
                                        logger.warning(f"[SLIPPAGE PROTECT] Skipping entry for {temp_s_a}/{temp_s_b} because live price is already past Stop Loss due to volatility.")
                                        continue
                                
                                signal_id = do_log_signal()
                                if execute_three_part_binance_trade(
                                    temp_s_a, False,"""

if target_buy in content:
    content = content.replace(target_buy, replacement_buy)
    print("Buy block replacement successful.")
else:
    print("Buy block target not found!")

if target_sell in content:
    content = content.replace(target_sell, replacement_sell)
    print("Sell block replacement successful.")
else:
    print("Sell block target not found!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
