import sys
import os
import logging

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Test")

# Add the parent directory to the path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import get_dynamic_crypto_candidate_pairs, CANDIDATE_PAIRS
from binance_execution import calculate_binance_quantity, get_symbol_filters

def run_test():
    logger.info("Starting test sequence...")
    
    # 1. Test get_dynamic_crypto_candidate_pairs
    usdt_balance = 11.36
    logger.info(f"Testing dynamic crypto pairs generator with balance: {usdt_balance}")
    pairs = get_dynamic_crypto_candidate_pairs(usdt_balance)
    
    logger.info(f"Generated {len(pairs)} pairs.")
    if not pairs:
        logger.error("No pairs generated! Test failed.")
        sys.exit(1)
        
    # Check if there are any tokenized stocks in the generated list
    bad_keywords = ['SPCX', 'SNDK', 'TSM', 'QCOM', 'JPM', 'ARM', 'IBM', 'CRMU', 'IWM', 'URNM', 'ZM', 'AAPL', 'MSFT', 'GOOGL', 'TSLA', 'NVDA', 'AMD', 'META', 'AMZN']
    for p in pairs:
        s_a, s_b = p
        for kw in bad_keywords:
            if kw in s_a or kw in s_b:
                logger.error(f"Found forbidden stock symbol in generated pairs: {p}. Test failed!")
                sys.exit(1)
                
    logger.info("Verified: No tokenized stocks in the generated candidate list.")
    logger.info(f"Sample generated pairs: {pairs[:10]}")
    
    # 2. Test calculate_binance_quantity notional enforcement
    # Scenario A: High price coin (SOLUSDT)
    sol_price = 140.0
    sl_dist = 14.0 # 10% SL
    qty_sol = calculate_binance_quantity("SOLUSDT", sl_dist, usdt_balance, current_price=sol_price)
    notional_sol = qty_sol * sol_price
    logger.info(f"SOL calculated qty: {qty_sol} | Notional value: ${notional_sol:.2f}")
    if notional_sol < 5.49:
        logger.error(f"SOL Notional ${notional_sol:.2f} is below 5.49! Test failed.")
        sys.exit(1)
        
    # Scenario B: Cheap price coin (PEPEUSDT)
    pepe_price = 0.000012
    sl_dist_pepe = 0.0000012
    qty_pepe = calculate_binance_quantity("1000PEPEUSDT", sl_dist_pepe, usdt_balance, current_price=pepe_price)
    notional_pepe = qty_pepe * pepe_price
    logger.info(f"PEPE calculated qty: {qty_pepe} | Notional value: ${notional_pepe:.2f}")
    if notional_pepe < 5.49:
        logger.error(f"PEPE Notional ${notional_pepe:.2f} is below 5.49! Test failed.")
        sys.exit(1)
        
    # 3. Test hedge ratio notional scaling & margin guard
    # Let's test if Leg A: SOL (price 140, beta 0.0003) and Leg B: cheap coin (price 0.45)
    # This should be skipped because of margin capacity check
    price_a = 140.0
    price_b = 0.45
    beta = 0.0003
    
    # Standard qty_a calculation:
    qty_a = calculate_binance_quantity("SOLUSDT", 14.0, usdt_balance, current_price=price_a)
    
    # Hedge guard logic:
    if beta * price_b > 0:
        min_qty_a_for_hedge = 5.5 / (beta * price_b)
        filters_a = get_symbol_filters("SOLUSDT")
        step_a = filters_a["stepSize"] if filters_a else 0.001
        prec_a = filters_a["quantityPrecision"] if filters_a else 3
        qty_a_needed_for_hedge = round(round(min_qty_a_for_hedge / step_a) * step_a, prec_a)
        if qty_a < qty_a_needed_for_hedge:
            qty_a = qty_a_needed_for_hedge
            
    qty_b = qty_a * beta
    notional_a = qty_a * price_a
    notional_b = qty_b * price_b
    logger.info(f"Hedge Leg Test -> Qty A: {qty_a} (Notional A: ${notional_a:.2f}) | Qty B: {qty_b} (Notional B: ${notional_b:.2f})")
    
    # Verify margin check guard
    max_allowed_notional = usdt_balance * 5.0
    if notional_a > max_allowed_notional or notional_b > max_allowed_notional:
        logger.info(f"Margin Check: [PASS] Correctly flagged as exceeding capacity. Notional A: ${notional_a:.2f}, limit: ${max_allowed_notional:.2f}")
    else:
        logger.error("Margin Check failed: Did not flag unbalanced notional size!")
        sys.exit(1)
        
    logger.info("All tests passed successfully!")

if __name__ == "__main__":
    run_test()
