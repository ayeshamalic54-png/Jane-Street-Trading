import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Remove major_whitelist from get_dynamic_crypto_candidate_pairs
target_whitelist = """        major_whitelist = {"BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "BNBUSDT", "LTCUSDT", "BCHUSDT", "LINKUSDT", "AVAXUSDT", "DOTUSDT", "DOGEUSDT"}
        valid_symbols = []
        for info in symbols_info:
            sym = info["symbol"]
            if sym not in prices:
                continue
            if sym.upper() not in major_whitelist:
                continue"""

replacement_whitelist = """        valid_symbols = []
        for info in symbols_info:
            sym = info["symbol"]
            if sym not in prices:
                continue"""

if target_whitelist in content:
    content = content.replace(target_whitelist, replacement_whitelist)
    print("Whitelist removed from main.py.")
else:
    print("Whitelist target not found!")

# 2. Replace static margin check with dynamic scaling in both BUY and SELL loops
target_safeguard = """                                # Ensure Leg B notional value does not exceed 15x our account balance (margin safeguard)
                                notional_b = qty_b * price_b
                                if notional_b > usdt_bal * 15.0:
                                    logger.info(f"Hedge Limit: Skipping {temp_s_a}/{temp_s_b} because calculated Leg B notional ${notional_b:.2f} exceeds maximum margin capacity (${usdt_bal * 15.0:.2f})")
                                    continue"""

replacement_safeguard = """                                # Ensure notional values fit within the exchange's leverage bracket caps (dynamic scaling)
                                from binance_execution import get_max_notional
                                max_notional_a = get_max_notional(temp_s_a, 20)
                                max_notional_b = get_max_notional(temp_s_b, 20)
                                notional_a = qty_a * price_a
                                notional_b = qty_b * price_b
                                
                                scale_factor = 1.0
                                if notional_a > max_notional_a:
                                    scale_factor = min(scale_factor, max_notional_a / notional_a)
                                if notional_b > max_notional_b:
                                    scale_factor = min(scale_factor, max_notional_b / notional_b)
                                    
                                if scale_factor < 1.0:
                                    logger.info(f"Hedge Limit: Scaling down position size by {scale_factor:.2f}x to fit within symbol notional caps (Max A: ${max_notional_a}, Max B: ${max_notional_b})")
                                    qty_a *= scale_factor
                                    qty_b *= scale_factor
                                    filters_a = get_symbol_filters(temp_s_a)
                                    if filters_a:
                                        qty_a = round(round(qty_a / filters_a["stepSize"]) * filters_a["stepSize"], filters_a["quantityPrecision"])
                                    filters_b = get_symbol_filters(temp_s_b)
                                    if filters_b:
                                        qty_b = round(round(qty_b / filters_b["stepSize"]) * filters_b["stepSize"], filters_b["quantityPrecision"])
                                        
                                # Skip trade if either leg falls below minimum $5.5 requirement after scaling
                                if qty_a * price_a < 5.5 or qty_b * price_b < 5.5:
                                    logger.info(f"Hedge Limit: Skipping {temp_s_a}/{temp_s_b} because scaled quantity is below minimum $5.5 notional requirement.")
                                    continue"""

# Replace all occurrences of target_safeguard in main.py
if target_safeguard in content:
    content = content.replace(target_safeguard, replacement_safeguard)
    print("Safeguards updated with dynamic leverage bracket scaling.")
else:
    # Let's try with different indentation or whitespace if it fails
    # But target_safeguard matches the git diff indent exactly (32 spaces). Let's see!
    print("Safeguard target not found!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
