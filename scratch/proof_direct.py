import sys
import os
import json
import pandas as pd
import numpy as np
import MetaTrader5 as mt5

sys.path.append(r'G:\google antigravity\jane_street_trading_system')

from smc_indicators import detect_smc_zones, detect_market_structure, is_price_in_zones
from smc_strategy_engine import evaluate_smc_strategy_signal

out_path = r'G:\google antigravity\jane_street_trading_system\scratch\proof_output.txt'

with open(out_path, 'w', encoding='utf-8') as out_f:
    out_f.write("Initializing MT5 connection...\n")
    mt5_ok = mt5.initialize()
    out_f.write(f"MT5 Initialized: {mt5_ok}\n")

    if mt5_ok:
        sym = 'XAUUSD'
        info = mt5.symbol_info(sym)
        if info is None:
            all_syms = mt5.symbols_get()
            if all_syms:
                for s in all_syms:
                    if 'XAU' in s.name.upper() or 'GOLD' in s.name.upper():
                        sym = s.name
                        break
        
        rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, 220)
        if rates is not None and len(rates) > 0:
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
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
            
            out_f.write("\n========================================================================\n")
            out_f.write(f"EMPIRICAL LIVE VERIFICATION FROM MT5 FOR SYMBOL: {sym}\n")
            out_f.write("========================================================================\n")
            out_f.write(f"1. MT5 Live Price:       ${price:.2f}\n")
            out_f.write(f"2. MT5 M15 200 EMA:      ${ema:.2f}\n")
            out_f.write(f"   -> Protection 1 (200 EMA Macro Trend): Price (${price:.2f}) >= 200 EMA (${ema:.2f})\n")
            out_f.write(f"      STATUS: {'PASS' if p1_pass else 'FAIL'} (Price is ${price - ema:+.2f} relative to 200 EMA)\n")
            out_f.write(f"3. Market Structure:     {struct}\n")
            out_f.write(f"   -> Protection 2 (M15 Market Structure): Trend is {struct}\n")
            out_f.write(f"      STATUS: {'PASS' if p2_pass else 'FAIL'}\n")
            out_f.write(f"4. ICT Bullish Zones (OB / FVG / Breaker / iFVG):\n")
            total_z = 0
            for z_name, z_val in zones.items():
                if 'bullish' in z_name and z_val:
                    total_z += len(z_val)
                    out_f.write(f"   - {z_name}: {z_val}\n")
            if total_z == 0:
                out_f.write("   - No active Bullish OB / FVG / Breaker zones found in current M15 window\n")
            out_f.write(f"   -> Protection 3 (ICT Zone Retest): Is Price (${price:.2f}) inside any Bullish Zone?\n")
            out_f.write(f"      STATUS: {'PASS' if p3_pass else 'FAIL (Price is OUTSIDE all active Bullish zones)'}\n")
            out_f.write(f"5. Current M15 Rejection Candle:\n")
            out_f.write(f"   - Open: ${open_p:.2f} | High: ${high_p:.2f} | Low: ${low_p:.2f} | Close: ${price:.2f}\n")
            out_f.write(f"   -> Protection 4 (Rejection Candle): Green Bullish Candle (Close >= Open)\n")
            out_f.write(f"      STATUS: {'PASS' if p4_pass else 'FAIL (Waiting for Green Candle)'}\n")
            out_f.write("========================================================================\n")
            out_f.write(f"Engine Evaluated Signal Output: {sig}\n")
            out_f.write(f"Engine Reason Log Output:       {reason}\n")
            out_f.write("========================================================================\n")
        mt5.shutdown()
    else:
        out_f.write("MT5 Connection Failed.\n")

print("Finished writing proof_output.txt")
