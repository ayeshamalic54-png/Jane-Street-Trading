import sys
import os
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt

sys.path.append(r'G:\google antigravity\jane_street_trading_system')

from smc_indicators import detect_smc_zones, detect_market_structure, is_price_in_zones
from smc_strategy_engine import evaluate_smc_strategy_signal

print("Fetching Gold live data...")
gold = yf.Ticker("GC=F")
df = gold.history(period="5d", interval="15m")

if df is not None and len(df) > 0:
    df['ema_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    df.rename(columns={'Open':'open', 'High':'high', 'Low':'low', 'Close':'close', 'Volume':'volume'}, inplace=True)
    
    struct = detect_market_structure(df)
    zones = detect_smc_zones(df)
    sig, tp, sl, dist, reason = evaluate_smc_strategy_signal(df, category='metals')
    
    price = float(df['close'].iloc[-1])
    ema = float(df['ema_200'].iloc[-1])
    open_p = float(df['open'].iloc[-1])
    high_p = float(df['high'].iloc[-1])
    low_p = float(df['low'].iloc[-1])
    
    bull_zones = zones['bullish_ob'] + zones['bullish_fvg'] + zones['bullish_breaker'] + zones['bullish_ifvg']
    in_bull_zone = is_price_in_zones(price, bull_zones)
    
    print("\n================================================================================")
    print(f"📊 [EMPIRICAL LIVE VERIFICATION PROOF FOR GOLD (GC=F / XAUUSD)] 🚀")
    print("================================================================================")
    print(f"1. Live Market Price: ${price:.2f}")
    print(f"2. 200 EMA Level:     ${ema:.2f}")
    print(f"   -> Protection 1 (200 EMA Macro Trend): Price (${price:.2f}) >= 200 EMA (${ema:.2f})")
    print(f"      Result: {'PASS 🟢' if price >= ema else 'FAIL 🔴'} (Price is ${price - ema:+.2f} relative to 200 EMA)")
    print(f"3. Market Structure:  {struct}")
    print(f"   -> Protection 2 (M15 Structure): M15 Trend is {struct}")
    print(f"      Result: {'PASS 🟢' if struct == 'BULLISH' else 'FAIL 🔴'}")
    print(f"4. ICT Bullish Zones (OB/FVG/Breaker):")
    count_z = 0
    for z_name, z_val in zones.items():
        if 'bullish' in z_name and z_val:
            count_z += len(z_val)
            print(f"   - {z_name}: {z_val}")
    if count_z == 0:
        print("   - No active Bullish OB / FVG / Breaker zones found in current M15 window")
    print(f"   -> Protection 3 (ICT Zone Retest): Is Price (${price:.2f}) inside any Bullish Zone?")
    print(f"      Result: {'PASS 🟢' if in_bull_zone else 'FAIL 🔴 (Price is outside all active OB/FVG zones)'}")
    print(f"5. Candle Action Rejection:")
    print(f"   - Current M15 Candle: Open=${open_p:.2f} | Close=${price:.2f} | High=${high_p:.2f} | Low=${low_p:.2f}")
    print(f"   -> Protection 4 (Rejection Candle): Green Bullish (Close >= Open)")
    print(f"      Result: {'PASS 🟢' if price >= open_p else 'FAIL 🔴 (Red Bearish Candle)'}")
    print("================================================================================")
    print(f"Evaluated Engine Signal Output: {sig}")
    print(f"Evaluated Engine Reason Log:   {reason}")
    print("================================================================ me\n")
    
    # ── PLOT CHART ──
    fig, ax = plt.subplots(figsize=(12, 6))
    sub_df = df.iloc[-60:]
    ax.plot(sub_df.index, sub_df['close'], label='Gold M15 Close Price', color='gold', linewidth=2)
    ax.plot(sub_df.index, sub_df['ema_200'], label='200 EMA', color='cyan', linestyle='--', linewidth=1.5)
    
    # Highlight price
    ax.axhline(price, color='yellow', linestyle=':', label=f'Current Price: ${price:.2f}')
    ax.axhline(ema, color='cyan', linestyle=':', label=f'200 EMA: ${ema:.2f}')
    
    # Plot Bullish Zones
    for (z_low, z_high) in bull_zones:
        ax.axhspan(z_low, z_high, color='green', alpha=0.3, label='Bullish OB/FVG Zone')
        
    ax.set_title(f"Gold (XAUUSD) M15 SMC Analysis Chart\nPrice (${price:.2f}) vs 200 EMA (${ema:.2f}) | Structure: {struct}", fontsize=14, color='white')
    ax.set_facecolor('#111111')
    fig.patch.set_facecolor('#111111')
    ax.tick_params(colors='white')
    ax.xaxis.label.set_color('white')
    ax.yaxis.label.set_color('white')
    ax.legend(facecolor='#222222', edgecolor='none', labelcolor='white')
    plt.tight_layout()
    
    chart_path = r'G:\google antigravity\jane_street_trading_system\scratch\gold_smc_chart.png'
    plt.savefig(chart_path, dpi=150)
    print(f"Chart saved to {chart_path}")
