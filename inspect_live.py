import MetaTrader5 as mt5
import pandas as pd

if not mt5.initialize():
    print("Failed MT5 initialization")
    exit()

symbols = ["XAUUSD", "EURUSD", "GBPUSD", "AUDUSD", "USDCHF", "USDJPY"]

print("=== LIVE ASSET STEVES Z-SCORE INSPECTOR ===")

for sym in symbols:
    s_info = mt5.symbol_info(sym)
    resolved = sym
    if not s_info:
        for suf in [".c", ".raw", "m", ".p"]:
            if mt5.symbol_info(sym + suf):
                resolved = sym + suf
                break

    rates = mt5.copy_rates_from_pos(resolved, mt5.TIMEFRAME_M15, 0, 200)
    if rates is None or len(rates) < 50:
        print(f"No rates for {sym}")
        continue
    df = pd.DataFrame(rates)

    # TradingView Steves Z-score calculation (SMA 20, StdDev 20)
    df['sma20'] = df['close'].rolling(20).mean()
    df['std20'] = df['close'].rolling(20).std()
    df['z_steves'] = (df['close'] - df['sma20']) / df['std20']
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()

    c_price = df['close'].iloc[-1]
    c_ema = df['ema200'].iloc[-1]
    c_z = df['z_steves'].iloc[-1]
    p_z = df['z_steves'].iloc[-2]
    max_z = df['z_steves'].iloc[-50:].max()
    min_z = df['z_steves'].iloc[-50:].min()

    trend = "BULLISH" if c_price > c_ema else "BEARISH"
    print(f"{resolved:8s} | Price: {c_price:10.5f} | 200 EMA: {c_ema:10.5f} ({trend:7s}) | Z: Curr={c_z:+.3f}, Prev={p_z:+.3f} | MaxZ(50): {max_z:+.2f}, MinZ(50): {min_z:+.2f}")

mt5.shutdown()
