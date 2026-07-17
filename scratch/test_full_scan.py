import sys
import os
sys.path.append(os.getcwd())

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_full_scan")

import MetaTrader5 as mt5
from math_models import KalmanFilterRegression
from main import get_symbol_category, get_kf_for_pair, detect_smc_zones, is_price_in_zones, calculate_obi, get_binance_live_tick, get_binance_market_book, get_binance_rates_df
from database import update_scanned_asset

# Init MT5
if not mt5.initialize():
    print("MT5 Init Failed")
else:
    print("MT5 Init Success")

pairs = [("BTCUSDT", "ETHUSDT")]
Z_ENTRY_THRESHOLD = 1.5
REQUIRE_SMC_CONFLUENCE = False
SMC_ZONES_CACHE = {}

for s_a, s_b in pairs:
    print(f"\n--- Full dry run for: {s_a}/{s_b} ---")
    try:
        cat_a = get_symbol_category(s_a)
        cat_b = get_symbol_category(s_b)
        
        tick_a_scan = get_binance_live_tick(s_a)
        bids_a_scan, asks_a_scan = get_binance_market_book(s_a)
        tick_b_scan = get_binance_live_tick(s_b)
        bids_b_scan, asks_b_scan = get_binance_market_book(s_b)
        
        if tick_a_scan is None or tick_b_scan is None:
            print("Skipped: Tick is None!")
            continue
            
        p_a = (tick_a_scan.bid + tick_a_scan.ask) / 2.0
        p_b = (tick_b_scan.bid + tick_b_scan.ask) / 2.0
        
        print(f"Prices: p_a={p_a}, p_b={p_b}")
        
        kf_pair = get_kf_for_pair(s_a, s_b)
        beta, alpha, spread, z = kf_pair.update(p_b, p_a)
        print(f"Kalman update: beta={beta}, alpha={alpha}, spread={spread}, z={z}")
        
        r_df = get_binance_rates_df(s_a, timeframe_minutes=5, count=100)
        if r_df is not None:
            zones = detect_smc_zones(r_df)
            print(f"SMC zones detected successfully: {list(zones.keys()) if zones else None}")
        else:
            print("Failed to fetch klines for SMC")
            
        # OBI checks
        obi_a = calculate_obi(bids_a_scan, asks_a_scan, depth=5)
        obi_b = calculate_obi(bids_b_scan, asks_b_scan, depth=5)
        net_obi = obi_a - obi_b
        print(f"OBI calculation: obi_a={obi_a}, obi_b={obi_b}, net={net_obi}")
        
        update_scanned_asset(f"{s_a}/{s_b}", p_a, p_b, 50.0, z, "NONE")
        print("update_scanned_asset completed successfully!")
        
    except Exception as e:
        import traceback
        print(f"Exception raised: {e}")
        traceback.print_exc()
