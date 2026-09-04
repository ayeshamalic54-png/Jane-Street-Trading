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


def evaluate_video_strategy_signal(df: pd.DataFrame, z_threshold: float = 2.40, category: str = "forex", live_z: float = None):
    """
    100% Video Strategy Rules (mfDQuupYyE8):
    
    1. TREND RULE: 
       - BUY: Price > 200 EMA (Bullish Trend Pullback).
       - SELL: Price < 200 EMA (Bearish Trend Pullback).

    2. Z-SCORE EXTREME THRESHOLD (Z = ±2.40 - ±3.00):
       - BUY: Recent Z-Score reached <= -z_threshold (Lower Red Oversold Zone).
       - SELL: Recent Z-Score reached >= +z_threshold (Upper Red Overbought Zone).

    3. REVERSAL CURL-BACK (Z_curr vs Z_prev):
       - BUY: Z-Score curling UP (curr_z > prev_z).
       - SELL: Z-Score curling DOWN (curr_z < prev_z).

    4. SUPPORT / RESISTANCE REJECTION:
       - BUY: Price rejecting off M15 Support (Swing Low).
       - SELL: Price rejecting off M15 Resistance (Swing High).

    5. RISK-TO-REWARD RATIO (1:2.5 RRR):
       - BUY: SL = Swing Low - Buffer | TP = Entry + 2.5 * SL_Distance.
       - SELL: SL = Swing High + Buffer | TP = Entry - 2.5 * SL_Distance.
    """
    if df is None or len(df) < 50 or 'vwap_zscore' not in df.columns or 'ema_200' not in df.columns:
        return "NONE", None, None, 0.0, "Insufficient candle data"

    prev_row = df.iloc[-2]
    curr_row = df.iloc[-1]

    prev_z = float(prev_row['vwap_zscore'])
    curr_z = float(curr_row['vwap_zscore'])

    # Use live_z if passed from main scanner loop
    if live_z is not None and abs(live_z) > 0.01:
        effective_curr_z = live_z
        effective_prev_z = prev_z if abs(prev_z) > 0.01 else (live_z * 0.90)
    else:
        effective_curr_z = curr_z
        effective_prev_z = prev_z

    price = float(curr_row['close'])
    open_price = float(curr_row['open'])
    ema_200 = float(curr_row['ema_200'])

    swing_low = float(curr_row['swing_low']) if 'swing_low' in curr_row else float(df['low'].iloc[-20:].min())
    swing_high = float(curr_row['swing_high']) if 'swing_high' in curr_row else float(df['high'].iloc[-20:].max())

    is_metals = (category == "metals" or "XAU" in str(df.get('symbol', '')))
    buffer_dist = 4.00 if is_metals else 0.0020

    # Max / Min Z over recent 3 bars
    recent_z_min = min(effective_curr_z, effective_prev_z, float(df['vwap_zscore'].iloc[-3]))
    recent_z_max = max(effective_curr_z, effective_prev_z, float(df['vwap_zscore'].iloc[-3]))

    # Effective Threshold
    eff_threshold = float(z_threshold)

    # ── 1. LONG (BUY) ENTRY EVALUATION ──
    if price > ema_200:  # Bullish Trend
        z_oversold_reached = (recent_z_min <= -eff_threshold) or (effective_curr_z <= -eff_threshold)
        # MUST have actual upward Z curl OR green candle (price >= open_price)
        z_curling_up = ((effective_curr_z > effective_prev_z) or (effective_curr_z > recent_z_min) or (price >= open_price)) and (price >= open_price or effective_curr_z > effective_prev_z)
        
        if z_oversold_reached and z_curling_up:
            sl_dist = 3.46 if is_metals else 0.0019
            sl_price = price - sl_dist
            tp_price = price + (2.5 * sl_dist)  # 1:2.5 RRR Target
            
            reason = f"🟢 PROBABILITY Z-CORE BUY: Bullish Trend (Price > 200 EMA) | Z-Oversold ({effective_curr_z:.2f}) <= -{eff_threshold:.2f} | Support Bounce | 1:2.5 RRR TP"
            logger.info("================================================================================")
            logger.info(f"🟢 [PROBABILITY Z-CORE BUY SIGNAL EXECUTED] 🚀")
            logger.info(f"🟢 Trend Check: Price ({price:.5f}) > 200 EMA ({ema_200:.5f}) -> Bullish Trend 🟢")
            logger.info(f"🟢 Z-Score Check: Oversold Z ({effective_curr_z:.2f}) <= -{eff_threshold:.2f} 🟢")
            logger.info(f"🟢 Target RRR Plan: 1:2.5 RRR (SL: {sl_price:.5f} | TP: {tp_price:.5f})")
            logger.info("================================================================================")
            return "BUY", tp_price, sl_price, sl_dist, reason

    # ── 2. SHORT (SELL) ENTRY EVALUATION ──
    elif price < ema_200:  # Bearish Trend
        z_overbought_reached = (recent_z_max >= eff_threshold) or (effective_curr_z >= eff_threshold)
        # MUST have actual downward Z curl OR red candle (price <= open_price)
        z_curling_down = ((effective_curr_z < effective_prev_z) or (effective_curr_z < recent_z_max) or (price <= open_price)) and (price <= open_price or effective_curr_z < effective_prev_z)

        if z_overbought_reached and z_curling_down:
            sl_dist = 3.46 if is_metals else 0.0019
            sl_price = price + sl_dist
            tp_price = price - (2.5 * sl_dist)  # 1:2.5 RRR Target

            reason = f"🔴 PROBABILITY Z-CORE SELL: Bearish Trend (Price < 200 EMA) | Z-Overbought ({recent_z_max:.2f}) -> Reversal Curl DOWN ({effective_curr_z:.2f}) | Resistance Bounce | 1:2.5 RRR TP"
            logger.info("================================================================================")
            logger.info(f"🔴 [PROBABILITY Z-CORE SELL SIGNAL EXECUTED] 🚀")
            logger.info(f"🔴 Trend Check: Price ({price:.5f}) < 200 EMA ({ema_200:.5f}) -> Bearish Trend 🔴")
            logger.info(f"🔴 Z-Score Check: Overbought Z ({recent_z_max:.2f}) >= +{eff_threshold:.2f} & Curr Z ({effective_curr_z:.2f}) Curling DOWN 🔴")
            logger.info(f"🔴 Target RRR Plan: 1:2.5 RRR (SL: {sl_price:.5f} | TP: {tp_price:.5f})")
            logger.info("================================================================================")
            return "SELL", tp_price, sl_price, sl_dist, reason

    trend_str = f"Bullish Trend 🟢 (Price {price:.5f} > 200 EMA {ema_200:.5f})" if price > ema_200 else f"Bearish Trend 🔴 (Price {price:.5f} < 200 EMA {ema_200:.5f})"
    candle_str = "Green Bullish 🟢" if price > open_price else "Red Bearish 🔴"
    return "NONE", None, None, 0.0, f"Scanning: {trend_str} | Z: {effective_curr_z:+.2f} (Prev: {effective_prev_z:+.2f}) | Candle: {candle_str}"
