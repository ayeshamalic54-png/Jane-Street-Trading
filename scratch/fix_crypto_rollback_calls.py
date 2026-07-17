import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace rollback calls on line 2128-2130 (inside SELL_SPREAD crypto logic)
target_sell_rollback = """                                        else:
                                            logger.error(f"Hedge order failed for {temp_s_b}. Rollback Leg A {temp_s_a} on MT5!")
                                            close_all_positions(temp_s_a)
                                            rollback_database_trades(signal_id)
                                            trade_placed = False"""

replacement_sell_rollback = """                                        else:
                                            logger.error(f"Hedge order failed for {temp_s_b}. Rollback Leg A {temp_s_a}!")
                                            close_all_binance_positions(temp_s_a)
                                            rollback_database_trades(signal_id)
                                            trade_placed = False"""

# Replace rollback calls on line 2233-2237 (inside BUY_SPREAD crypto logic)
target_buy_rollback = """                                        else:
                                            logger.error(f"Hedge order failed for {temp_s_b}. Rollback Leg A {temp_s_a} on MT5!")
                                            close_all_positions(temp_s_a)
                                            rollback_database_trades(signal_id)
                                            trade_placed = False"""

replacement_buy_rollback = """                                        else:
                                            logger.error(f"Hedge order failed for {temp_s_b}. Rollback Leg A {temp_s_a}!")
                                            close_all_binance_positions(temp_s_a)
                                            rollback_database_trades(signal_id)
                                            trade_placed = False"""

if target_sell_rollback in content:
    content = content.replace(target_sell_rollback, replacement_sell_rollback)
    print("SELL_SPREAD rollback fixed.")
else:
    print("SELL_SPREAD rollback target not found!")

if target_buy_rollback in content:
    content = content.replace(target_buy_rollback, replacement_buy_rollback)
    print("BUY_SPREAD rollback fixed.")
else:
    print("BUY_SPREAD rollback target not found!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
