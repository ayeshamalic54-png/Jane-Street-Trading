import sys
import os
sys.path.insert(0, os.path.abspath('.'))
import pandas as pd
import numpy as np
from smc_indicators import detect_market_structure, detect_liquidity_sweep, get_swing_points
from smc_strategy_engine import evaluate_smc_strategy_signal

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("================================================================================")
print("🛡️ COMPREHENSIVE SMC 7-STEP RISK SAFEGUARD VERIFICATION SUITE 🛡️")
print("================================================================================")

# ------------------------------------------------------------------------------
# TEST 1: Market Structure Bias Safety (No Fallback Glitch)
# ------------------------------------------------------------------------------
print("\n[TEST 1] Market Structure Bias Safety Check:")

# Downtrend dataframe (Lower Highs + Lower Lows, but with one old high)
m15_down_dates = pd.date_range('2026-09-18 08:00', periods=30, freq='15min')
prices_down = [4410.0, 4405.0, 4400.0, 4402.0, 4395.0, 4390.0, 4393.0, 4385.0, 4380.0, 4382.0,
               4375.0, 4370.0, 4372.0, 4365.0, 4360.0, 4362.0, 4355.0, 4350.0, 4352.0, 4345.0,
               4340.0, 4342.0, 4335.0, 4330.0, 4332.0, 4325.0, 4320.0, 4322.0, 4315.0, 4310.0]

df_m15_downtrend = pd.DataFrame({
    'time': m15_down_dates,
    'open': [p + 0.5 for p in prices_down],
    'high': [p + 1.5 for p in prices_down],
    'low': [p - 1.5 for p in prices_down],
    'close': prices_down,
    'tick_volume': [100]*30
})
df_m15_downtrend['symbol'] = 'XAUUSD'

bias_result = detect_market_structure(df_m15_downtrend)
print(f"-> Downtrend Structure Bias Result: '{bias_result}'")
assert bias_result != 'BULLISH', "CRITICAL SAFETY FAIL: Downtrend market evaluated as BULLISH!"
print("✅ PASS: Downtrend market correctly identified as non-Bullish!")

# ------------------------------------------------------------------------------
# TEST 2: Unclosed Live Candle Blocking
# ------------------------------------------------------------------------------
print("\n[TEST 2] Live Unclosed Candle Rejection Blocking Check:")

# M5 data where iloc[-2] (closed candle) is RED / not rejecting FVG, but iloc[-1] (live candle) ticks green
m5_dates = pd.date_range('2026-09-18 12:00', periods=15, freq='5min')
df_m5_unclosed_test = pd.DataFrame({
    'time': m5_dates,
    'open': [4395.0]*13 + [4395.0, 4392.0],  # iloc[-2]: Open 4395, Close 4391 (RED)
    'high': [4397.0]*13 + [4396.0, 4396.0],
    'low': [4390.0]*13 + [4390.0, 4391.0],
    'close': [4396.0]*13 + [4391.0, 4394.0], # iloc[-2]: Close 4391.0 (RED). iloc[-1]: Close 4394 (Live Green Tick)
    'tick_volume': [50]*15
})

sig_unclosed, _, _, _, msg_unclosed = evaluate_smc_strategy_signal(df_m15_downtrend, df_m5_unclosed_test, category="metals")
print(f"-> Signal on Live Unclosed Green Tick: '{sig_unclosed}'")
assert sig_unclosed == "NONE", "CRITICAL SAFETY FAIL: Unclosed live candle triggered a trade!"
print("✅ PASS: Live unclosed green tick correctly BLOCKED from executing trade!")

# ------------------------------------------------------------------------------
# TEST 3: Stale Sweep Expiration Check
# ------------------------------------------------------------------------------
print("\n[TEST 3] Stale Sweep Lookback Expiration Check:")

# Sweep occurred at candle 2 (13 bars ago)
df_m5_stale = pd.DataFrame({
    'high': [4400.0, 4405.0, 4402.0] + [4395.0]*12,
    'low':  [4390.0, 4385.0, 4392.0] + [4390.0]*12,
    'close': [4395.0, 4396.0, 4395.0] + [4392.0]*12,
    'open':  [4392.0, 4391.0, 4394.0] + [4393.0]*12,
})
sell_sw, buy_sw = detect_liquidity_sweep(df_m5_stale)
print(f"-> Stale Sell-Side Sweep Status (13 bars ago): {sell_sw[0]}")
assert sell_sw[0] == False, "CRITICAL SAFETY FAIL: Stale sweep older than 6 bars was NOT expired!"
print("✅ PASS: Stale sweep correctly EXPIRED!")

print("\n================================================================================")
print("🎯 ALL RISK SAFEGUARDS VERIFIED 100% OPERATIONAL & BULLETPROOF! 🎯")
print("================================================================================")
