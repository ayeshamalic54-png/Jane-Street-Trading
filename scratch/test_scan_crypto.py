import sys
import os
sys.path.append(os.getcwd())

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_scan_crypto")

import MetaTrader5 as mt5
from data_ingestion import initialize_mt5
from binance_execution import get_binance_live_tick, get_binance_market_book, get_binance_rates_df

# Init MT5
if not mt5.initialize():
    print("MT5 Init Failed")
else:
    print("MT5 Init Success")

pairs = [("BTCUSDT", "ETHUSDT"), ("SOLUSDT", "BTCUSDT"), ("ETHUSDT", "SOLUSDT")]

for s_a, s_b in pairs:
    print(f"\n--- Scanning Pair: {s_a}/{s_b} ---")
    try:
        tick_a = get_binance_live_tick(s_a)
        bids_a, asks_a = get_binance_market_book(s_a)
        print(f"Symbol A ({s_a}) Tick: {tick_a.bid if tick_a else None} / {tick_a.ask if tick_a else None}")
        print(f"Symbol A Depth: bids={len(bids_a)}, asks={len(asks_a)}")

        tick_b = get_binance_live_tick(s_b)
        bids_b, asks_b = get_binance_market_book(s_b)
        print(f"Symbol B ({s_b}) Tick: {tick_b.bid if tick_b else None} / {tick_b.ask if tick_b else None}")
        print(f"Symbol B Depth: bids={len(bids_b)}, asks={len(asks_b)}")

        if tick_a is None or tick_b is None:
            print("Skipping because tick is None!")
        else:
            print("Tick data fetched successfully!")
    except Exception as e:
        print(f"Exception during scan: {e}")
