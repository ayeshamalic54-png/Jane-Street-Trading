import sys
import pandas as pd
import numpy as np

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from smc_strategy_engine import evaluate_smc_strategy_signal
from smc_indicators import detect_market_structure

print("================================================================================")
print("PROOF 1: MAIN.PY ENGINE EXECUTION CODE LINES")
print("================================================================================")
with open('main.py', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines, 1):
    if 'SMC_ENABLED' in line or 'evaluate_smc_strategy_signal' in line:
        print(f"Line {i}: {line.strip()}")

print("\n================================================================================")
print("PROOF 2: ICT BIAS (BOS/CHoCH) ENFORCEMENT TEST")
print("================================================================================")

dates = pd.date_range('2026-09-07 08:00', periods=40, freq='15min')
base = [4380.0]
for i in range(1, 40):
    if i < 10: base.append(base[-1] + 1.0)
    elif i < 15: base.append(base[-1] - 0.5)
    elif i < 25: base.append(base[-1] + 1.5)
    elif i < 30: base.append(base[-1] - 0.8)
    else: base.append(base[-1] + 0.2)

df_m15 = pd.DataFrame({'time': dates, 'open': [p-0.5 for p in base], 'high': [p+1.0 for p in base], 'low': [p-1.0 for p in base], 'close': base, 'symbol': 'XAUUSD'})
df_m15.loc[26, 'high'] = 4390.0
df_m15.loc[28, 'low'] = 4394.0

bias = detect_market_structure(df_m15)
print(f"1. M15 Market Structure Bias Detected: {bias}")

df_m5 = pd.DataFrame({'time': pd.date_range('2026-09-07 17:00', periods=20, freq='5min'), 'open': [4398]*19 + [4391], 'high': [4400]*19 + [4395], 'low': [4397]*19 + [4390.5], 'close': [4399]*19 + [4392.5]})

sig, tp, sl, dist, reason = evaluate_smc_strategy_signal(df_m15, df_m5, category='metals')
print(f"2. Evaluated Signal: {sig}")
print(f"3. Reason Log: {reason.encode('ascii', 'ignore').decode('ascii')}")
print("================================================================================")
