import sys
import os
import json
import urllib.request
import pandas as pd
import numpy as np

sys.path.append(r'G:\google antigravity\jane_street_trading_system')

from smc_indicators import detect_smc_zones, detect_market_structure, is_price_in_zones
from smc_strategy_engine import evaluate_smc_strategy_signal

print("Executing fast HTTP market fetch for XAUUSD (Gold Futures)...")
url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?range=5d&interval=15m"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode('utf-8'))
    timestamps = data['chart']['result'][0]['timestamp']
    quote = data['chart']['result'][0]['indicators']['quote'][0]
    df = pd.DataFrame({
        'time': pd.to_datetime(timestamps, unit='s'),
        'open': quote['open'],
        'high': quote['high'],
        'low': quote['low'],
        'close': quote['close'],
        'volume': quote['volume']
    }).dropna()

if df is not None and len(df) >= 20:
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
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
    
    p1_pass = (price >= ema)
    p2_pass = (struct == 'BULLISH')
    p3_pass = in_bull_zone
    p4_pass = (price >= open_p)
    
    print("\n================================================================================")
    print("📊 [LIVE EMPIRICAL PROOF & MATHEMATICAL VERIFICATION FOR GOLD / XAUUSD]")
    print("================================================================================")
    print(f"1. Live Price:         ${price:.2f}")
    print(f"2. M15 200 EMA:        ${ema:.2f}")
    print(f"   -> Protection 1 (200 EMA Macro Trend): Price (${price:.2f}) >= 200 EMA (${ema:.2f})")
    print(f"      STATUS: {'PASS 🟢' if p1_pass else 'FAIL 🔴'} (Price is ${price - ema:+.2f} relative to 200 EMA)")
    print(f"3. Market Structure:   {struct}")
    print(f"   -> Protection 2 (M15 Structure): Market Trend is {struct}")
    print(f"      STATUS: {'PASS 🟢' if p2_pass else 'FAIL 🔴'}")
    print(f"4. ICT Bullish Zones (OB / FVG / Breaker / iFVG):")
    total_z = 0
    for z_name, z_val in zones.items():
        if 'bullish' in z_name and z_val:
            total_z += len(z_val)
            print(f"   - {z_name}: {z_val}")
    if total_z == 0:
        print("   - No active Bullish OB / FVG / Breaker zones found in current M15 window")
    print(f"   -> Protection 3 (ICT Zone Retest): Is Price (${price:.2f}) inside any Bullish Zone?")
    print(f"      STATUS: {'PASS 🟢' if p3_pass else 'FAIL 🔴 (Price is OUTSIDE all active Bullish zones)'}")
    print(f"5. Current M15 Rejection Candle:")
    print(f"   - Open: ${open_p:.2f} | High: ${high_p:.2f} | Low: ${low_p:.2f} | Close: ${price:.2f}")
    print(f"   -> Protection 4 (Rejection Candle): Green Bullish Candle (Close >= Open)")
    print(f"      STATUS: {'PASS 🟢' if p4_pass else 'FAIL 🔴 (Waiting for Green Candle)'}")
    print("================================================================================")
    print(f"Engine Evaluated Signal Output: {sig}")
    print(f"Engine Reason Log Output:     {reason}")
    print("================================================================ me\n")
