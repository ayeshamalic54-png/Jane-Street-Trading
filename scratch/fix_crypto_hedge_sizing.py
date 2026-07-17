import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """def get_hedge_quantity(symbol_a: str, symbol_b: str, qty_a: float, beta: float, cat_a: str, cat_b: str) -> float:
    \"\"\"
    Calculates the correct hedge quantity for Leg B based on Leg A quantity, beta,
    and the relative contract sizes of symbol_a and symbol_b.
    \"\"\"
    if cat_b == "crypto":
        if cat_a == "crypto":
            contract_ratio = 1.0
        else:
            info_a = mt5.symbol_info(symbol_a)
            contract_ratio = info_a.trade_contract_size if info_a else 1.0
            
        filters_b = get_symbol_filters(symbol_b)
        raw_qty = qty_a * abs(beta) * contract_ratio
        if filters_b:
            step_b = float(filters_b["stepSize"])
            qty_prec_b = filters_b["quantityPrecision"]
            rounded_qty = round(round(raw_qty / step_b) * step_b, qty_prec_b)
            if rounded_qty < step_b:
                rounded_qty = step_b
            return rounded_qty
        else:
            return round(raw_qty, 3)"""

replacement = """def get_hedge_quantity(symbol_a: str, symbol_b: str, qty_a: float, beta: float, cat_a: str, cat_b: str) -> float:
    \"\"\"
    Calculates the correct hedge quantity for Leg B based on Leg A quantity, beta,
    and the relative price ratio of symbol_a and symbol_b (ensuring equal dollar-value notional hedge).
    \"\"\"
    if cat_b == "crypto":
        price_a = 1.0
        price_b = 1.0
        try:
            tick_a = get_binance_live_tick(symbol_a)
            tick_b = get_binance_live_tick(symbol_b)
            if tick_a and tick_b:
                price_a = (tick_a.bid + tick_a.ask) / 2.0
                price_b = (tick_b.bid + tick_b.ask) / 2.0
        except Exception as e_pr:
            logger.error(f"Error fetching live prices for hedge quantity calculation: {e_pr}")

        raw_qty = qty_a * abs(beta) * (price_a / price_b)
        
        filters_b = get_symbol_filters(symbol_b)
        if filters_b:
            step_b = float(filters_b["stepSize"])
            qty_prec_b = filters_b["quantityPrecision"]
            rounded_qty = round(round(raw_qty / step_b) * step_b, qty_prec_b)
            if rounded_qty < step_b:
                rounded_qty = step_b
            return rounded_qty
        else:
            return round(raw_qty, 3)"""

if target in content:
    content = content.replace(target, replacement)
    print("Hedge sizing math fixed.")
else:
    print("Target not found!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
