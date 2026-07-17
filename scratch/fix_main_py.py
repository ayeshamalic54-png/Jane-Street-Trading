import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """                                        qty_a_needed_for_hedge = round(math.ceil(min_qty_a_for_hedge / step_a) * step_a, prec_a)
                                        if qty_a < qty_a_needed_for_hedge:
                                            max_allowed_qty = (usdt_bal * 7.0) / float(best_sig["price_a"])
                                            if qty_a_needed_for_hedge > max_allowed_qty:
                                                logger.info(f"Hedge Limit: Skipping {temp_s_a}/{temp_s_b} because required hedge size {qty_a_needed_for_hedge} {temp_s_a} (${qty_a_needed_for_hedge*float(best_sig['price_a']):.2f}) exceeds max margin capacity (${usdt_bal*7.0:.2f})")
                                                continue
                                            qty_a = qty_a_needed_for_hedge"""

replacement = """                                        qty_a_needed_for_hedge = round(math.ceil(min_qty_a_for_hedge / step_a) * step_a, prec_a)
                                        if qty_a < qty_a_needed_for_hedge:
                                            if qty_a_needed_for_hedge > 2.0 * qty_a:
                                                logger.info(f"Hedge Limit: Skipping {temp_s_a}/{temp_s_b} because forced hedge quantity {qty_a_needed_for_hedge} is > 2x the risk-calculated quantity {qty_a} (exceeds account risk buffer)")
                                                continue
                                            max_allowed_qty = (usdt_bal * 7.0) / float(best_sig["price_a"])
                                            if qty_a_needed_for_hedge > max_allowed_qty:
                                                logger.info(f"Hedge Limit: Skipping {temp_s_a}/{temp_s_b} because required hedge size {qty_a_needed_for_hedge} {temp_s_a} (${qty_a_needed_for_hedge*float(best_sig['price_a']):.2f}) exceeds max margin capacity (${usdt_bal*7.0:.2f})")
                                                continue
                                            qty_a = qty_a_needed_for_hedge"""

# Count occurrences before replacing
occ = content.count(target)
print(f"Target found {occ} times.")

if occ > 0:
    content = content.replace(target, replacement)
    with open(main_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Replaced successfully!")
else:
    print("Replace failed because target was not found.")
