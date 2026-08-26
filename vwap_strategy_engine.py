import numpy as np
import pandas as pd
import logging

logger = logging.getLogger("VWAP_Strategy_Engine")

def calculate_vwap_and_zscore(df: pd.DataFrame, period: int = 14):
    """
    Calculates VWAP using Typical Price (High + Low + Close) / 3 and VWAP Z-Score.
    
    Typical Price = (High + Low + Close) / 3
    VWAP = sum(Typical Price * Volume) / sum(Volume)
    Z-Score = (Current Close Price - VWAP) / Standard Deviation of (Price - VWAP)
    """
    if df is None or len(df) < period:
        return None, None
        
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
    return df

def calculate_ema_filter(df: pd.DataFrame, period: int = 200):
    """
    Calculates 200 EMA for trend regime filtering.
    """
    if df is None or len(df) < period:
        df['ema_200'] = df['close'] if df is not None else None
        return df
    df['ema_200'] = df['close'].ewm(span=period, adjust=False).mean()
    return df

def calculate_prop_firm_lot_size(symbol: str, account_equity: float, free_margin: float, sl_pips: float, category: str = "forex") -> float:
    """
    Prop Firm Compliance Sizing:
    1. 1.0% Equity Risk per Trade: Lots = (Equity * 0.01) / (SL_Pips * Pip_Value)
    2. STRICT 80% Max Margin Guard: Required Margin <= 80% Free Margin
    """
    if sl_pips <= 0 or account_equity <= 0:
        return 0.01

    risk_usd = account_equity * 0.01  # 1.0% Risk
    
    if category == "metals" or "XAU" in symbol:
        pip_value_per_lot = 10.0
        margin_per_lot = 2000.0  # Approx $2000 per 1.0 lot Gold at 1:100 leverage
    else:  # Forex Majors
        pip_value_per_lot = 10.0
        margin_per_lot = 1000.0  # Approx $1000 per 1.0 lot Forex at 1:100 leverage
        
    risk_based_lots = risk_usd / (sl_pips * pip_value_per_lot)
    
    # ── 80% MARGIN GUARD CAP ──
    max_allowed_margin = free_margin * 0.80
    max_margin_lots = max_allowed_margin / margin_per_lot
    
    final_lots = min(risk_based_lots, max_margin_lots)
    final_lots = max(0.01, round(final_lots, 2))
    return final_lots

def evaluate_single_asset_vwap_signal(df: pd.DataFrame, z_threshold: float = 0.60, category: str = "forex"):
    """
    Single-Asset VWAP Z-Score Reversal Execution Logic (TESTING MODE Z=0.60):
    - BUY: Price > 200 EMA (Bullish Trend), Z-Score <= -0.60 then curls UP across -0.60.
      TP = VWAP Line (Z = 0.0), SL = Nearest M15 Swing Low - Buffer.
    - SELL: Price < 200 EMA (Bearish Trend), Z-Score >= +0.60 then curls DOWN across +0.60.
      TP = VWAP Line (Z = 0.0), SL = Nearest M15 Swing High + Buffer.
    """
    if df is None or len(df) < 200 or 'vwap_zscore' not in df.columns or 'ema_200' not in df.columns:
        return "NONE", None, None, "Insufficient data"
        
    prev_row = df.iloc[-2]
    curr_row = df.iloc[-1]
    
    prev_z = prev_row['vwap_zscore']
    curr_z = curr_row['vwap_zscore']
    price = curr_row['close']
    ema_200 = curr_row['ema_200']
    vwap_target = curr_row['vwap']
    
    buffer_pips = 2.5 if (category == "metals" or "XAU" in df.get('symbol', '')) else 0.0008
    
    # 1. BULLISH REGIME (Price > 200 EMA) -> Pullback BUY
    if price > ema_200:
        if prev_z <= -z_threshold and curr_z > -z_threshold:
            swing_low = df['low'].iloc[-20:].min()
            sl_price = min(price - buffer_pips, swing_low - 0.0002)
            return "BUY", vwap_target, sl_price, f"BUY Signal: Z-score oversold crossover {prev_z:.2f} -> {curr_z:.2f}"

    # 2. BEARISH REGIME (Price < 200 EMA) -> Pullback SELL
    elif price < ema_200:
        if prev_z >= z_threshold and curr_z < z_threshold:
            swing_high = df['high'].iloc[-20:].max()
            sl_price = max(price + buffer_pips, swing_high + 0.0002)
            return "SELL", vwap_target, sl_price, f"SELL Signal: Z-score overbought crossunder {prev_z:.2f} -> {curr_z:.2f}"

    return "NONE", None, None, f"No Signal (Z: {curr_z:.2f})"
