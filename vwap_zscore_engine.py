import datetime
import logging
import numpy as np

logger = logging.getLogger("VWAP_ZScore_Engine")

def calculate_vwap_and_zscore(prices, volumes, period=14):
    """
    Calculates Volume-Weighted Average Price (VWAP) and VWAP Z-Score.
    
    VWAP = sum(Price * Volume) / sum(Volume)
    Z-Score = (Current Price - VWAP) / Standard Deviation of (Price - VWAP)
    """
    if len(prices) < period or len(volumes) < period:
        return None, None
        
    prices = np.array(prices[-period:], dtype=float)
    volumes = np.array(volumes[-period:], dtype=float)
    
    total_volume = np.sum(volumes)
    if total_volume <= 0:
        return None, None
        
    vwap = np.sum(prices * volumes) / total_volume
    deviations = prices - vwap
    std_dev = np.std(deviations)
    
    if std_dev <= 0:
        z_score = 0.0
    else:
        z_score = (prices[-1] - vwap) / std_dev
        
    return float(vwap), float(z_score)

def evaluate_vwap_zscore_signal(z_history, upper_thresh=2.0, lower_thresh=-2.0):
    """
    Evaluates VWAP Z-Score signals based on Video 1 reversal rules:
    - BUY Signal: Z-Score drops below lower_thresh (-2.0) and curls back UP across lower_thresh.
    - SELL Signal: Z-Score rises above upper_thresh (+2.0) and curls back DOWN across upper_thresh.
    - MEAN REVERSION EXIT: Z-Score reaches 0.0 (VWAP line).
    """
    if len(z_history) < 2:
        return "NONE", "Insufficient history"
        
    prev_z = z_history[-2]
    curr_z = z_history[-1]
    
    # Buy Signal: Crossover back above oversold threshold (-2.0)
    if prev_z <= lower_thresh and curr_z > lower_thresh:
        return "BUY", f"VWAP Z-Score oversold reversal crossover: {prev_z:.2f} -> {curr_z:.2f}"
        
    # Sell Signal: Crossunder back below overbought threshold (+2.0)
    if prev_z >= upper_thresh and curr_z < upper_thresh:
        return "SELL", f"VWAP Z-Score overbought reversal crossunder: {prev_z:.2f} -> {curr_z:.2f}"
        
    return "NONE", f"Z-Score within normal band: {curr_z:.2f}"
