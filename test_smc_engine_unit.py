import sys
import numpy as np
import pandas as pd
from smc_strategy_engine import evaluate_smc_strategy_signal

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("================================================================================")
print("UNIT TEST: PURE SMC/ICT STRATEGY ENGINE VERIFICATION")
print("================================================================================")

# Create synthetic M15 rates dataframe with Bullish Structure and Bullish FVG
dates_m15 = pd.date_range('2026-09-07 08:00', periods=40, freq='15min')
np.random.seed(42)
base_prices = [4380.0]
for i in range(1, 40):
    if i < 10:
        base_prices.append(base_prices[-1] + 1.0)
    elif i < 15:
        base_prices.append(base_prices[-1] - 0.5) # Swing High 1 created at i=9
    elif i < 25:
        base_prices.append(base_prices[-1] + 1.5) # Break of Structure (BOS)
    elif i < 30:
        base_prices.append(base_prices[-1] - 0.8) # Pullback into FVG
    else:
        base_prices.append(base_prices[-1] + 0.2)

df_m15 = pd.DataFrame({
    'time': dates_m15,
    'open': [p - 0.5 for p in base_prices],
    'high': [p + 1.0 for p in base_prices],
    'low': [p - 1.0 for p in base_prices],
    'close': base_prices,
    'tick_volume': [100]*40
})
df_m15['symbol'] = 'XAUUSD'

# Inject a clear Bullish FVG at candle 26: low[28] > high[26]
df_m15.loc[26, 'high'] = 4390.0
df_m15.loc[28, 'low'] = 4394.0 # FVG gap between 4390.0 and 4394.0

# Create synthetic M5 rates dataframe retesting into FVG (price = 4392.5)
dates_m5 = pd.date_range('2026-09-07 17:00', periods=20, freq='5min')
df_m5_bull = pd.DataFrame({
    'time': dates_m5,
    'open': [4398.0]*19 + [4391.0],
    'high': [4400.0]*19 + [4395.0],
    'low': [4397.0]*19 + [4390.5],
    'close': [4399.0]*19 + [4392.5], # Green candle (close 4392.5 > open 4391.0) inside FVG (4390.0 - 4394.0)
    'tick_volume': [50]*20
})

# Test 1: M15 Bullish Structure + FVG Retest
signal1, tp1, sl1, sl_dist1, reason1 = evaluate_smc_strategy_signal(df_m15, df_m5_bull, category="metals")
print("TEST 1: M15 Bullish Structure + Bullish FVG Retest")
print("Signal Result:", signal1)
if signal1 == "BUY":
    print("SL Price:", sl1, "| TP Price:", tp1, "| SL Dist:", sl_dist1, "| Reason:", reason1.encode('ascii', 'ignore').decode('ascii'))

# Test 2: Bearish Structure + Rising Green Candle (Must Block SELL Entry!)
bear_prices = [4450.0]
for i in range(1, 40):
    if i < 10:
        bear_prices.append(bear_prices[-1] - 1.0)
    elif i < 15:
        bear_prices.append(bear_prices[-1] + 0.5) # Swing Low 1
    elif i < 25:
        bear_prices.append(bear_prices[-1] - 1.5) # Bearish BOS
    elif i < 30:
        bear_prices.append(bear_prices[-1] + 0.8) # Retest
    else:
        bear_prices.append(bear_prices[-1] - 0.2)

df_m15_bear = pd.DataFrame({
    'time': dates_m15,
    'open': [p + 0.5 for p in bear_prices],
    'high': [p + 1.0 for p in bear_prices],
    'low': [p - 1.0 for p in bear_prices],
    'close': bear_prices,
    'tick_volume': [100]*40
})
df_m15_bear['symbol'] = 'XAUUSD'

# Inject Bearish FVG gap at candle 26: high[28] < low[26]
df_m15_bear.loc[26, 'low'] = 4425.0
df_m15_bear.loc[28, 'high'] = 4420.0 # FVG gap between 4420.0 and 4425.0
# Keep candles 29-39 below 4425 so FVG remains unmitigated
for idx in range(29, 40):
    df_m15_bear.loc[idx, 'high'] = 4418.0
    df_m15_bear.loc[idx, 'low'] = 4410.0
    df_m15_bear.loc[idx, 'close'] = 4412.0
    df_m15_bear.loc[idx, 'open'] = 4415.0

df_m5_up = df_m5_bull.copy()
df_m5_up['open'] = [4421.0]*20
df_m5_up['close'] = [4423.0]*20 # Green candle surging UP inside Bearish FVG!

signal2, tp2, sl2, sl_dist2, reason2 = evaluate_smc_strategy_signal(df_m15_bear, df_m5_up, category="metals")
print("\nTEST 2: Bearish Structure + Rising Green Candle (Must Block SELL Entry!)")
print("Signal Result:", signal2)
print("Reason:", reason2.encode('ascii', 'ignore').decode('ascii'))

# Test 3: Bearish Structure + Red Rejection Candle inside Bearish FVG
df_m5_red = df_m5_bull.copy()
df_m5_red['open'] = [4421.0]*19 + [4424.0]
df_m5_red['close'] = [4421.0]*19 + [4422.0] # Red Candle (Close 4422 < Open 4424) inside FVG (4420 - 4425)

signal3, tp3, sl3, sl_dist3, reason3 = evaluate_smc_strategy_signal(df_m15_bear, df_m5_red, category="metals")
print("\nTEST 3: Bearish Structure + Bearish FVG Retest + Red Rejection Candle")
print("Signal Result:", signal3)
if signal3 == "SELL":
    print("SL Price:", sl3, "| TP Price:", tp3, "| SL Dist:", sl_dist3, "| Reason:", reason3.encode('ascii', 'ignore').decode('ascii'))

print("================================================================================")
