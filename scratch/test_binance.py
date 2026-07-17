import sys
import os
import requests

# Add current directory to path
sys.path.append(os.getcwd())

import logging
logging.basicConfig(level=logging.INFO)

from binance_execution import get_binance_live_tick, get_binance_rates_df, get_binance_usdt_balance

print("=== TESTING BINANCE TICK ===")
tick = get_binance_live_tick("BTCUSDT")
print(f"BTCUSDT Tick: {tick.bid if tick else None} / {tick.ask if tick else None}")

print("\n=== TESTING BINANCE KLINES ===")
df = get_binance_rates_df("BTCUSDT", count=10)
if df is not None:
    print(f"Klines: Loaded {len(df)} rows. Last close: {df['close'].iloc[-1]}")
else:
    print("Klines: Failed to load")

print("\n=== TESTING BINANCE BALANCE ===")
bal, avail = get_binance_usdt_balance()
print(f"USDT Balance: {bal} | Available: {avail}")
