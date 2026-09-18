import sys
import MetaTrader5 as mt5
import pandas as pd
import datetime
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("TEST_EXECUTION")

if not mt5.initialize():
    logger.error("Failed to initialize MT5")
    sys.exit(1)

print("=== MT5 CONNECTED SUCCESSFULLY ===")
acc_info = mt5.account_info()
if acc_info:
    print(f"Account Login: {acc_info.login} | Server: {acc_info.server} | Equity: ${acc_info.equity:.2f} USD | Free Margin: ${acc_info.margin_free:.2f} USD")

from video_strategy_engine import calculate_zscore_and_ema, evaluate_video_strategy_signal

symbols = ["XAUUSD", "EURUSD", "GBPUSD", "AUDUSD", "USDCHF", "USDJPY"]

print("\n=== LIVE SCANNING ALL 6 ASSETS FOR VIDEO STRATEGY (Z_THRESHOLD = 3.00) ===")

for sym in symbols:
    # Resolve symbol name for broker
    info = mt5.symbol_info(sym)
    resolved_sym = sym
    if not info:
        for suf in [".c", ".raw", "m", ".p"]:
            if mt5.symbol_info(sym + suf):
                resolved_sym = sym + suf
                break

    rates = mt5.copy_rates_from_pos(resolved_sym, mt5.TIMEFRAME_M15, 0, 220)
    if rates is None or len(rates) < 200:
        print(f"[-] {resolved_sym}: Insufficient rates data (Fetched {len(rates) if rates is not None else 0} candles)")
        continue

    df = pd.DataFrame(rates)
    df['symbol'] = resolved_sym
    df = calculate_zscore_and_ema(df, period=14, ema_period=200)

    cat = "metals" if "XAU" in resolved_sym else "forex"
    sig, tp_price, sl_price, sl_dist, reason = evaluate_video_strategy_signal(df, z_threshold=3.00, category=cat)

    curr_z = df['vwap_zscore'].iloc[-1]
    prev_z = df['vwap_zscore'].iloc[-2]
    price = df['close'].iloc[-1]
    ema_200 = df['ema_200'].iloc[-1]
    trend = "BULLISH [Price > 200 EMA]" if price > ema_200 else "BEARISH [Price < 200 EMA]"

    print(f"[SCAN] {resolved_sym:8s} | Price: {price:10.5f} | 200 EMA: {ema_200:10.5f} | Trend: {trend}")
    print(f"       Z-Score: Curr={curr_z:+.3f}, Prev={prev_z:+.3f} (Entry Limit: +/- 3.00)")
    print(f"       Status: {sig} | Reason: {reason}")
    if sig != "NONE":
        print(f"       >>> SIGNAL TRIGGERED! SL: {sl_price:.5f} | TP: {tp_price:.5f} (1:2.5 RRR)")
    print("-" * 75)

mt5.shutdown()
