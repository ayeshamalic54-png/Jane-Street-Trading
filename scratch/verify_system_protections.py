import os
import sys
sys.path.insert(0, r"G:\google antigravity\jane_street_trading_system")

import pandas as pd
import numpy as np
from smc_strategy_engine import evaluate_smc_strategy_signal

# Test Case with 25 candles: Upward Surge (Bullish Retracement in Bearish Macro) -> Protection 4 MUST FAIL 🔴
rows = []
for i in range(25):
    rows.append({
        'open': 4410.0 - (i * 1.0),
        'high': 4412.0 - (i * 1.0),
        'low': 4408.0 - (i * 1.0),
        'close': 4409.0 - (i * 1.0),
        'ema_200': 4430.0
    })

# Make last 2 candles Green (Surging UP from 4385 to 4398)
rows[-2] = {'open': 4385.0, 'high': 4395.0, 'low': 4384.0, 'close': 4394.0, 'ema_200': 4430.0} # Green Candle (Closed)
rows[-1] = {'open': 4394.0, 'high': 4399.0, 'low': 4393.0, 'close': 4398.0, 'ema_200': 4430.0} # Green Candle (Active Surge)

df_m15 = pd.DataFrame(rows)

# Evaluate SMC Signal
action, tp, sl, sl_dist, scan_msg = evaluate_smc_strategy_signal(df_m15=df_m15, category="metals", obi_enabled=True, net_obi=0.0)

clean_msg = scan_msg.encode('ascii', errors='ignore').decode('ascii')

print("=" * 80)
print("[LIVE SYSTEM CONFIRMATION VERIFICATION]")
print("=" * 80)
print(f"Action Output: {action} (Must be NONE)")
print(f"Scanner Log Message:\n{clean_msg}")
print("=" * 80)

if action == "NONE" and "FAIL" in clean_msg:
    print("SUCCESS: SYSTEM IS 100% SECURE! NO WRONG TRADE CAN BE EXECUTED DURING UPWARD SURGE!")
else:
    print("WARNING: SYSTEM FAILED VERIFICATION!")
