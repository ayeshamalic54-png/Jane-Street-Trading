import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Target inside is_long = True block
target_1 = """                                 qty_b = get_hedge_quantity(temp_s_a, temp_s_b, qty_a, best_sig["beta"], best_cat_a, best_cat_b)
                                
                                # Fetch latest live ticks to ensure no slippage has breached SL before entry"""

replacement_1 = """                                 qty_b = get_hedge_quantity(temp_s_a, temp_s_b, qty_a, best_sig["beta"], best_cat_a, best_cat_b)
                                
                                # Ensure Leg B notional value does not exceed 15x our account balance (margin safeguard)
                                notional_b = qty_b * price_b
                                if notional_b > usdt_bal * 15.0:
                                    logger.info(f"Hedge Limit: Skipping {temp_s_a}/{temp_s_b} because calculated Leg B notional ${notional_b:.2f} exceeds maximum margin capacity (${usdt_bal * 15.0:.2f})")
                                    continue
                                
                                # Fetch latest live ticks to ensure no slippage has breached SL before entry"""

# 2. Target inside is_long = False block (else block)
target_2 = """                                qty_b = get_hedge_quantity(temp_s_a, temp_s_b, qty_a, best_sig["beta"], best_cat_a, best_cat_b)
                                
                                # Fetch latest live ticks to ensure no slippage has breached SL before entry"""

replacement_2 = """                                qty_b = get_hedge_quantity(temp_s_a, temp_s_b, qty_a, best_sig["beta"], best_cat_a, best_cat_b)
                                
                                # Ensure Leg B notional value does not exceed 15x our account balance (margin safeguard)
                                notional_b = qty_b * price_b
                                if notional_b > usdt_bal * 15.0:
                                    logger.info(f"Hedge Limit: Skipping {temp_s_a}/{temp_s_b} because calculated Leg B notional ${notional_b:.2f} exceeds maximum margin capacity (${usdt_bal * 15.0:.2f})")
                                    continue
                                
                                # Fetch latest live ticks to ensure no slippage has breached SL before entry"""

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
