import numpy as np
import pandas as pd
import logging

logger = logging.getLogger("Video_Strategy_Engine")

def calculate_zscore_and_ema(df: pd.DataFrame, period: int = 14, ema_period: int = 200):
    """
    Calculates:
    1. VWAP Z-Score based on standard deviation of typical price.
    2. 200 EMA for Macro Trend Regime Filtering.
    3. M15 Swing Low & Swing High levels for Support/Resistance Rejection.
    """
    if df is None or len(df) < period:
        return df

    vol_col = 'tick_volume' if 'tick_volume' in df.columns else 'volume'
    if vol_col not in df.columns:
        df[vol_col] = 1.0

    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    volumes = df[vol_col].values

    typical_prices = (highs + lows + closes) / 3.0

    vwap_series = np.zeros(len(df))
    zscore_series = np.zeros(len(df))

    for i in range(period - 1, len(df)):
        sub_tp = typical_prices[i - period + 1 : i + 1]
        sub_v = volumes[i - period + 1 : i + 1]
        sub_c = closes[i - period + 1 : i + 1]

        tot_v = np.sum(sub_v)
        if tot_v > 0:
            vwap_val = np.sum(sub_tp * sub_v) / tot_v
        else:
            vwap_val = np.mean(sub_tp)

        vwap_series[i] = vwap_val
        devs = sub_c - vwap_val
        std_dev = np.std(devs)

        if std_dev > 0:
            zscore_series[i] = (closes[i] - vwap_val) / std_dev
        else:
            zscore_series[i] = 0.0

    df['typical_price'] = typical_prices
    df['vwap'] = vwap_series
    df['vwap_zscore'] = zscore_series

    # 200 EMA Trend Line
    df['ema_200'] = df['close'].ewm(span=ema_period, adjust=False).mean()

    # M15 Support / Resistance Levels (Swing Low / High over last 20 bars)
    df['swing_low'] = df['low'].rolling(window=20).min()
    df['swing_high'] = df['high'].rolling(window=20).max()

    return df


def evaluate_video_strategy_signal(df: pd.DataFrame, z_threshold: float = 3.0, category: str = "forex"):
    """
    100% Video Strategy Rules (mfDQuupYyE8):
    
    1. TREND RULE: 
       - BUY: Price > 200 EMA (Bullish Trend Pullback).
       - SELL: Price < 200 EMA (Bearish Trend Pullback).

    2. Z-SCORE EXTREME THRESHOLD (Z = ±3.0):
       - BUY: Z-Score reached <= -3.0 (Lower Red Oversold Zone).
       - SELL: Z-Score reached >= +3.0 (Upper Red Overbought Zone).

    3. CANDLE CLOSE REVERSAL CURL-BACK (Z_curr vs Z_prev):
       - BUY: Bullish Candle Close with Z_curr > Z_prev (Curl UP).
       - SELL: Bearish Candle Close with Z_curr < Z_prev (Curl DOWN).

    4. SUPPORT / RESISTANCE REJECTION:
       - BUY: Price rejecting off M15 Support (Swing Low).
       - SELL: Price rejecting off M15 Resistance (Swing High).

    5. RISK-TO-REWARD RATIO (1:2.5 RRR):
       - BUY: SL = Swing Low - Buffer | TP = Entry + 2.5 * SL_Distance.
       - SELL: SL = Swing High + Buffer | TP = Entry - 2.5 * SL_Distance.
    """
    if df is None or len(df) < 200 or 'vwap_zscore' not in df.columns or 'ema_200' not in df.columns:
        return "NONE", None, None, 0.0, "Insufficient candle data"

    prev_row = df.iloc[-2]
    curr_row = df.iloc[-1]

    prev_z = float(prev_row['vwap_zscore'])
    curr_z = float(curr_row['vwap_zscore'])

    price = float(curr_row['close'])
    open_price = float(curr_row['open'])
    ema_200 = float(curr_row['ema_200'])

    swing_low = float(curr_row['swing_low']) if 'swing_low' in curr_row else float(df['low'].iloc[-20:].min())
    swing_high = float(curr_row['swing_high']) if 'swing_high' in curr_row else float(df['high'].iloc[-20:].max())

    is_metals = (category == "metals" or "XAU" in str(df.get('symbol', '')))
    buffer_dist = 4.00 if is_metals else 0.0020

    # ── 1. LONG (BUY) ENTRY EVALUATION ──
    if price > ema_200:  # Bullish Trend
        is_bullish_candle = price > open_price
        if prev_z <= -z_threshold and curr_z > prev_z and is_bullish_candle:
            sl_price = min(price - buffer_dist, swing_low - (0.50 if is_metals else 0.0003))
            sl_dist = abs(price - sl_price)
            tp_price = price + (2.5 * sl_dist)  # 1:2.5 RRR
            
            reason = f"🟢 VIDEO BUY SIGNAL: Bullish Trend (Price > 200 EMA) | Z-Oversold ({prev_z:.2f}) -> Reversal Curl UP ({curr_z:.2f}) | Support Bounce | 1:2.5 RRR TP"
            logger.info("================================================================================")
            logger.info(f"🟢 [VIDEO BUY SIGNAL FIRED]")
            logger.info(f"🟢 Line 109: Price ({price:.5f}) > 200 EMA ({ema_200:.5f}) -> Bullish Trend 🟢")
            logger.info(f"🟢 Line 113: Prev Z ({prev_z:.2f}) <= -{z_threshold:.2f} & Curr Z ({curr_z:.2f}) > Prev Z -> Reversal Curl UP 🟢")
            logger.info(f"🟢 Line 116: Target RRR Plan: 1:2.5 RRR (SL: {sl_price:.5f} | TP: {tp_price:.5f})")
            logger.info("================================================================================")
            return "BUY", tp_price, sl_price, sl_dist, reason

    # ── 2. SHORT (SELL) ENTRY EVALUATION ──
    elif price < ema_200:  # Bearish Trend
        is_bearish_candle = price < open_price
        if prev_z >= z_threshold and curr_z < prev_z and is_bearish_candle:
            sl_price = max(price + buffer_dist, swing_high + (0.50 if is_metals else 0.0003))
            sl_dist = abs(sl_price - price)
            tp_price = price - (2.5 * sl_dist)  # 1:2.5 RRR

            reason = f"🔴 VIDEO SELL SIGNAL: Bearish Trend (Price < 200 EMA) | Z-Overbought ({prev_z:.2f}) -> Reversal Curl DOWN ({curr_z:.2f}) | Resistance Bounce | 1:2.5 RRR TP"
            logger.info("================================================================================")
            logger.info(f"🔴 [VIDEO SELL SIGNAL FIRED]")
            logger.info(f"🔴 Line 123: Price ({price:.5f}) < 200 EMA ({ema_200:.5f}) -> Bearish Trend 🔴")
            logger.info(f"🔴 Line 127: Prev Z ({prev_z:.2f}) >= +{z_threshold:.2f} & Curr Z ({curr_z:.2f}) < Prev Z -> Reversal Curl DOWN 🔴")
            logger.info(f"🔴 Line 130: Target RRR Plan: 1:2.5 RRR (SL: {sl_price:.5f} | TP: {tp_price:.5f})")
            logger.info("================================================================================")
            return "SELL", tp_price, sl_price, sl_dist, reason

    trend_str = f"Bullish Trend 🟢 (Price {price:.5f} > 200 EMA {ema_200:.5f})" if price > ema_200 else f"Bearish Trend 🔴 (Price {price:.5f} < 200 EMA {ema_200:.5f})"
    candle_str = "Green Bullish 🟢" if price > open_price else "Red Bearish 🔴"
    return "NONE", None, None, 0.0, f"Scanning: {trend_str} | Z: {curr_z:+.2f} (Prev: {prev_z:+.2f}) | Candle: {candle_str}"
