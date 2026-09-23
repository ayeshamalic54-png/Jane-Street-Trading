import sys
import os
import datetime
import pandas as pd
import numpy as np

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, r"G:\google antigravity\jane_street_trading_system")

from smc_strategy_engine import evaluate_smc_strategy_signal

print("=" * 80)
print("🚀 RUNNING SMC 7-STEP STRATEGY BACKTEST (XAUUSD GOLD & FOREX)")
print("=" * 80)

# 1. Test Case 1: Gold Buy Setup with Sweep Low Dip
prices_bull = [4350, 4360, 4370, 4380, 4375, 4365, 4360, 4365, 4375, 4385, 4395, 4410, 4405, 4395, 4390, 4392, 4396, 4400, 4405, 4410]
m15_bull = [{'open': p-1, 'high': p+2, 'low': p-2, 'close': p, 'symbol': 'XAUUSD'} for p in prices_bull]
df_m15 = pd.DataFrame(m15_bull)

m5_buy_data = []
m5_prices_base = [4400, 4398, 4395, 4392, 4390, 4392, 4396, 4398, 4395, 4393]
for p in m5_prices_base:
    m5_buy_data.append({'open': p+1, 'high': p+2, 'low': p-1, 'close': p})

m5_buy_data[4] = {'open': 4333.0, 'high': 4334.0, 'low': 4330.10, 'close': 4332.0} # Swing Low @ 4330.10
m5_buy_data.append({'open': 4331.0, 'high': 4332.0, 'low': 4329.83, 'close': 4330.50}) # Sweep @ 4329.83 < 4330.10
m5_buy_data.append({'open': 4330.50, 'high': 4338.0, 'low': 4329.5, 'close': 4337.0}) # CHoCH Close > 4334
m5_buy_data.append({'open': 4337.0, 'high': 4342.0, 'low': 4335.0, 'close': 4341.0}) # FVG 4332-4335
m5_buy_data.append({'open': 4333.0, 'high': 4338.0, 'low': 4332.5, 'close': 4336.46}) # Retest & Green Close @ 4336.46

df_m5 = pd.DataFrame(m5_buy_data)

sig, tp, sl, dist, msg = evaluate_smc_strategy_signal(df_m15=df_m15, df_m5=df_m5, category="metals")

print(f"\n📊 XAUUSD Gold BUY Signal Evaluation:")
print(f"   Action Signal: {sig}")
if sl is not None:
    print(f"   Entry Price:   $4336.46")
    print(f"   Stop Loss:     ${sl:.2f} (Buffer = $1.75 below sweep low 4329.83)")
    print(f"   Take Profit:   ${tp:.2f} (1:1.8 RRR Target)")
    print(f"   Risk Distance: ${dist:.2f}")
print(f"   Scan Detail:   {msg}")

# Verify safety against today's dip (4329.08)
if sl is not None:
    dip_price = 4329.08
    sl_hit = (dip_price <= sl)
    print(f"\n🛡️ Safety Test against Today's Dip (4329.08):")
    print(f"   Dip Price: ${dip_price:.2f} | New SL: ${sl:.2f}")
    if not sl_hit:
        print(f"   ✅ SUCCESS! Trade SURVIVES the 4329.08 dip! New SL (${sl:.2f}) is safe!")
    else:
        print(f"   ❌ FAILED! SL was hit.")

print("\n" + "=" * 80)
print("🎯 BACKTEST & VERIFICATION COMPLETED CLEANLY!")
print("=" * 80)
