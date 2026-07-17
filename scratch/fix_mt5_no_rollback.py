import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. First block: is_long = True, best_cat_b == "crypto" (hedge is crypto, entry is MT5)
# Wait, if entry is MT5 (best_cat_a != "crypto"), and hedge is MT5:
# Let's search for "Hedge order failed on MT5 for" in main.py to replace them cleanly.

target_1 = """                                        else:
                                            logger.error(f"Hedge order failed on MT5 for {temp_s_b}. Rollback Leg A {temp_s_a}!")
                                            close_all_binance_positions(temp_s_a)
                                            rollback_database_trades(signal_id)
                                            trade_placed = False"""

replacement_1 = """                                        else:
                                            logger.warning(f"Hedge order failed on MT5 for {temp_s_b}. Keeping Leg A {temp_s_a} open with active SL/TP to satisfy broker hold time rules.")
                                            trade_placed = True"""

# Target 2: is_long = False, hedge order failed on MT5
target_2 = """                                        else:
                                            logger.error(f"Hedge order failed on MT5 for {temp_s_b}. Rollback Leg A {temp_s_a} on MT5!")
                                            close_all_positions(temp_s_a)
                                            rollback_database_trades(signal_id)
                                            trade_placed = False"""

replacement_2 = """                                        else:
                                            logger.warning(f"Hedge order failed on MT5 for {temp_s_b}. Keeping Leg A {temp_s_a} open with active SL/TP to satisfy broker hold time rules.")
                                            trade_placed = True"""

# Target 3: inside BUY_SPREAD mt5 hedge failure
target_3 = """                                        else:
                                            logger.error(f"Hedge order failed on MT5 for {temp_s_b}. Rollback Leg A {temp_s_a} on MT5!")
                                            close_all_positions(temp_s_a)
                                            rollback_database_trades(signal_id)
                                            trade_placed = False"""

# Note: target_2 and target_3 are identical in text, replace will handle occurrences.

content = content.replace(target_1, replacement_1)
content = content.replace(target_2, replacement_2)

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated and MT5 rollbacks disabled.")
