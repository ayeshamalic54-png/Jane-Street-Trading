import os
import sys
sys.path.insert(0, r"G:\google antigravity\jane_street_trading_system")

import pandas as pd
import numpy as np
from smc_strategy_engine import evaluate_smc_strategy_signal
from smc_indicators import detect_market_structure, detect_liquidity_sweep, detect_choch_bos, detect_smc_zones, is_price_in_zones

# --- 1. TEST CASE 1: 5-STEP BUY SETUP ---
prices_bull = [4350, 4360, 4370, 4380, 4375, 4365, 4360, 4365, 4375, 4385, 4395, 4410, 4405, 4395, 4390, 4392, 4396, 4400, 4405, 4410]
m15_bull = []
for p in prices_bull:
    m15_bull.append({'open': p-1, 'high': p+2, 'low': p-2, 'close': p, 'symbol': 'XAUUSD'})
df_m15_bull = pd.DataFrame(m15_bull)

m5_buy_data = []
m5_prices_base = [4400, 4398, 4395, 4392, 4390, 4392, 4396, 4398, 4395, 4393]
for p in m5_prices_base:
    m5_buy_data.append({'open': p+1, 'high': p+2, 'low': p-1, 'close': p})

m5_buy_data[4] = {'open': 4393.0, 'high': 4394.0, 'low': 4388.0, 'close': 4392.0} # Swing Low @ 4388.0
m5_buy_data.append({'open': 4391.0, 'high': 4392.0, 'low': 4386.0, 'close': 4390.0}) # Sweep @ 4386 < 4388
m5_buy_data.append({'open': 4390.0, 'high': 4398.0, 'low': 4389.5, 'close': 4397.0}) # CHoCH Close > 4394
m5_buy_data.append({'open': 4397.0, 'high': 4402.0, 'low': 4395.0, 'close': 4401.0}) # FVG 4392-4395
m5_buy_data.append({'open': 4393.0, 'high': 4395.5, 'low': 4392.5, 'close': 4394.8}) # Retest & Green Close

df_m5_buy = pd.DataFrame(m5_buy_data)

act_buy, tp_b, sl_b, dist_b, msg_b = evaluate_smc_strategy_signal(df_m15=df_m15_bull, df_m5=df_m5_buy, category="metals")
clean_b = msg_b.encode('ascii', errors='ignore').decode('ascii')

# --- 2. TEST CASE 2: 5-STEP SELL SETUP ---
prices_bear = [4450, 4440, 4430, 4410, 4415, 4425, 4430, 4425, 4415, 4405, 4395, 4380, 4385, 4395, 4400, 4398, 4394, 4390, 4385, 4380]
m15_bear = []
for p in prices_bear:
    m15_bear.append({'open': p+1, 'high': p+2, 'low': p-2, 'close': p, 'symbol': 'XAUUSD'})
df_m15_bear = pd.DataFrame(m15_bear)

m5_sell_data = []
m5_prices_sell_base = [4396, 4398, 4400, 4402, 4403, 4401, 4400, 4402, 4403, 4404]
for p in m5_prices_sell_base:
    m5_sell_data.append({'open': p-1, 'high': p+1, 'low': p-1, 'close': p})

m5_sell_data[4] = {'open': 4402.0, 'high': 4405.0, 'low': 4401.0, 'close': 4404.0} # Swing High @ 4405.0
m5_sell_data.append({'open': 4404.0, 'high': 4408.0, 'low': 4402.0, 'close': 4404.0}) # Buy Sweep @ 4408 > 4405
m5_sell_data.append({'open': 4404.0, 'high': 4405.0, 'low': 4394.0, 'close': 4395.0}) # Bearish CHoCH Close 4395 < minor low ~4400
m5_sell_data.append({'open': 4395.0, 'high': 4394.0, 'low': 4388.0, 'close': 4390.0}) # FVG Creation (4394-4402)
m5_sell_data.append({'open': 4398.0, 'high': 4399.0, 'low': 4396.0, 'close': 4397.0}) # Retest & Red Close

df_m5_sell = pd.DataFrame(m5_sell_data)

act_sell, tp_s, sl_s, dist_s, msg_s = evaluate_smc_strategy_signal(df_m15=df_m15_bear, df_m5=df_m5_sell, category="metals")
clean_s = msg_s.encode('ascii', errors='ignore').decode('ascii')

# --- 3. TEST CASE 3: FOREX MAJOR (EURUSD) 5-STEP BUY SETUP ---
m15_forex = [{'open': d['open']/4000.0, 'high': d['high']/4000.0, 'low': d['low']/4000.0, 'close': d['close']/4000.0, 'symbol': 'EURUSD'} for d in m15_bull]
df_m15_fx = pd.DataFrame(m15_forex)

m5_fx_data = [{'open': d['open']/4000.0, 'high': d['high']/4000.0, 'low': d['low']/4000.0, 'close': d['close']/4000.0} for d in m5_buy_data]
df_m5_fx = pd.DataFrame(m5_fx_data)

act_fx, tp_fx, sl_fx, dist_fx, msg_fx = evaluate_smc_strategy_signal(df_m15=df_m15_fx, df_m5=df_m5_fx, category="forex")
clean_fx = msg_fx.encode('ascii', errors='ignore').decode('ascii')

# --- 4. TEST CASE 4: MISSING STEP REJECTION ---
m5_no_sweep = pd.DataFrame([
    {'open': 4400, 'high': 4402, 'low': 4395, 'close': 4398},
    {'open': 4398, 'high': 4399, 'low': 4395, 'close': 4396}
] * 10)
act_rej, _, _, _, msg_rej = evaluate_smc_strategy_signal(df_m15=df_m15_bull, df_m5=m5_no_sweep, category="metals")
clean_rej = msg_rej.encode('ascii', errors='ignore').decode('ascii')

print("=" * 80)
print("[PURE SMC / ICT 5-STEP STRATEGY ENGINE VERIFICATION]")
print("=" * 80)
print(f"1. BUY SETUP (GOLD) ACTION: {act_buy} (Expected: BUY)")
if sl_b is not None:
    print(f"   BUY SL: {sl_b:.2f} | TP: {tp_b:.2f} | Risk Dist: {dist_b:.2f}")
print(f"   BUY Msg: {clean_b}")
print("-" * 80)
print(f"2. SELL SETUP (GOLD) ACTION: {act_sell} (Expected: SELL)")
if sl_s is not None:
    print(f"   SELL SL: {sl_s:.2f} | TP: {tp_s:.2f} | Risk Dist: {dist_s:.2f}")
print(f"   SELL Msg: {clean_s}")
print("-" * 80)
print(f"3. FOREX MAJOR (EURUSD) ACTION: {act_fx} (Expected: BUY)")
if sl_fx is not None:
    print(f"   FOREX SL: {sl_fx:.5f} | TP: {tp_fx:.5f} | Risk Dist: {dist_fx:.5f}")
print(f"   FOREX Msg: {clean_fx}")
print("-" * 80)
print(f"4. MISSING STEP REJECTION ACTION: {act_rej} (Expected: NONE)")
print(f"   REJECTION Msg: {clean_rej}")
print("=" * 80)

if act_buy == "BUY" and act_sell == "SELL" and act_fx == "BUY" and act_rej == "NONE":
    print("SUCCESS: ALL TEST CASES PASSED 100% PERFECTLY FOR BOTH GOLD & FOREX MAJORS!")
else:
    print("WARNING: ONE OR MORE TEST CASES FAILED!")

