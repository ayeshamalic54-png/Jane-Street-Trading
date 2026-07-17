import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

# Target 1: inside is_long = True, crypto hedge failure (around line 2088)
target_1 = """                                        else:
                                            logger.error(f"Hedge order failed for {temp_s_b}. Rollback Leg A {temp_s_a}!")
                                            close_all_binance_positions(temp_s_a)
                                            rollback_database_trades(signal_id)
                                            trade_placed = False"""

replacement_1 = """                                        else:
                                            logger.warning(f"Hedge order failed for {temp_s_b}. Keeping Leg A {temp_s_a} open with active SL/TP on Binance.")
                                            trade_placed = True"""

# Target 2: inside is_long = False, crypto hedge failure (around line 2188)
target_2 = """                                        else:
                                            logger.error(f"Hedge order failed for {temp_s_b}. Rollback Leg A {temp_s_a}!")
                                            close_all_binance_positions(temp_s_a)
                                            rollback_database_trades(signal_id)
                                            trade_placed = False"""

replacement_2 = """                                        else:
                                            logger.warning(f"Hedge order failed for {temp_s_b}. Keeping Leg A {temp_s_a} open with active SL/TP on Binance.")
                                            trade_placed = True"""

if target_1 in content:
    content = content.replace(target_1, replacement_1)
    print("Target 1 replaced.")
else:
    print("Target 1 not found!")

if target_2 in content:
    content = content.replace(target_2, replacement_2)
    print("Target 2 replaced.")
else:
    print("Target 2 not found!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
