import sys
import pandas as pd
import MetaTrader5 as mt5

sys.path.insert(0, r"G:\google antigravity\jane_street_trading_system")
from vwap_strategy_engine import calculate_vwap_and_zscore, calculate_ema_filter

if mt5.initialize():
    print("=== LIVE MARKET Z-SCORE AUDIT ===")
    for sym in ['EURUSD', 'XAUUSD']:
        rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, 50)
        if rates is not None and len(rates) > 0:
            df = pd.DataFrame(rates)
            df = calculate_vwap_and_zscore(df, period=14)
            df = calculate_ema_filter(df, period=200)
            last_z = df['vwap_zscore'].iloc[-1]
            last_p = df['close'].iloc[-1]
            ema = df['ema_200'].iloc[-1]
            print(f"Asset: {sym:<8} | Price: {last_p:.5f} | 200 EMA: {ema:.5f} | Live Z-Score: {last_z:+.2f}")
    mt5.shutdown()
