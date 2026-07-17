import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import datetime
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from math_models import KalmanFilterRegression
from data_ingestion import resolve_broker_symbol

def get_symbol_category(symbol: str) -> str:
    s = symbol.upper()
    if any(x in s for x in ["XAU", "XAG"]):
        return "metals"
    return "forex"

def get_pip_size(symbol: str) -> float:
    s = symbol.upper()
    if "JPY" in s:
        return 0.01
    if "XAU" in s:
        return 1.0
    if "XAG" in s:
        return 0.1
    return 0.0001

def get_sl_distance(symbol: str, price: float, sl_pips: float) -> float:
    return sl_pips * get_pip_size(symbol)

def get_kf_parameters(symbol: str):
    cat = get_symbol_category(symbol)
    if cat == "metals":
        return 1e-10, 1e3
    else:
        return 1e-10, 1e-7

def run_simulation(df_data, s_a, s_b, z_entry, z_exit=0.0, sl_pips=10.0):
    trades = []
    active_trade = None # None or {"action": "BUY"/"SELL", "entry_idx": int, "sl_a": float, "sl_b": float}

    q_cov, r_cov = get_kf_parameters(s_a)
    kf = KalmanFilterRegression(transition_covariance=q_cov, observation_covariance=r_cov)
    
    # Warm up filter first (first 100 bars)
    prices_a = df_data['price_a'].values
    prices_b = df_data['price_b'].values
    highs_a = df_data['high_a'].values
    lows_a = df_data['low_a'].values
    highs_b = df_data['high_b'].values
    lows_b = df_data['low_b'].values
    
    z_scores = []
    for i in range(len(df_data)):
        beta, alpha, spread, z = kf.update(prices_b[i], prices_a[i])
        z_scores.append(z)
        
    df_data['z_score'] = z_scores

    total_trades = 0
    winning_trades = 0
    losing_trades = 0

    i = 100
    while i < len(df_data) - 1:
        z = df_data['z_score'].iloc[i]
        price_a = prices_a[i]
        price_b = prices_b[i]
        
        if active_trade is None:
            # Entry condition
            action = "NONE"
            if z < -z_entry:
                action = "BUY"
            elif z > z_entry:
                action = "SELL"
                
            if action != "NONE":
                sl_dist_a = get_sl_distance(s_a, price_a, sl_pips)
                sl_dist_b = get_sl_distance(s_b, price_b, sl_pips)
                
                sl_price_a = price_a - sl_dist_a if action == "BUY" else price_a + sl_dist_a
                sl_price_b = price_b + sl_dist_b if action == "BUY" else price_b - sl_dist_b
                
                active_trade = {
                    "action": action,
                    "entry_idx": i,
                    "sl_a": sl_price_a,
                    "sl_b": sl_price_b
                }
        else:
            # Check exit conditions
            action = active_trade["action"]
            sl_price_a = active_trade["sl_a"]
            sl_price_b = active_trade["sl_b"]
            
            fut_z = df_data['z_score'].iloc[i]
            fut_high_a = highs_a[i]
            fut_low_a = lows_a[i]
            fut_high_b = highs_b[i]
            fut_low_b = lows_b[i]
            
            # Check mean reversion exit (TP)
            tp_hit = False
            if (action == "BUY" and fut_z >= z_exit) or (action == "SELL" and fut_z <= z_exit):
                tp_hit = True
                
            # Check SL hit
            sl_hit = False
            hit_sl_a = (action == "BUY" and fut_low_a <= sl_price_a) or (action == "SELL" and fut_high_a >= sl_price_a)
            hit_sl_b = (action == "BUY" and fut_high_b >= sl_price_b) or (action == "SELL" and fut_low_b <= sl_price_b)
            if hit_sl_a or hit_sl_b:
                sl_hit = True
                
            if tp_hit or sl_hit:
                total_trades += 1
                if tp_hit:
                    winning_trades += 1
                else:
                    losing_trades += 1
                active_trade = None # Reset trade
                
        i += 1
        
    win_rate = (winning_trades / total_trades) * 100.0 if total_trades > 0 else 0.0
    return total_trades, winning_trades, losing_trades, win_rate

def backtest_thresholds():
    print("=== Backtesting Z-Score Thresholds (1.5 vs 1.8 vs 2.0) ===")
    mt5.initialize()
    
    s_a = resolve_broker_symbol("EURUSD")
    s_b = resolve_broker_symbol("GBPUSD")
    print(f"Active pair symbols: {s_a} / {s_b}")
    
    # Download 8000 historical M5 candles (approx. 27 trading days)
    print("Downloading 8000 M5 candles...")
    rates_a = mt5.copy_rates_from_pos(s_a, mt5.TIMEFRAME_M5, 0, 8000)
    rates_b = mt5.copy_rates_from_pos(s_b, mt5.TIMEFRAME_M5, 0, 8000)
    
    df_a = pd.DataFrame(rates_a)
    df_a['time'] = pd.to_datetime(df_a['time'], unit='s')
    df_a.set_index('time', inplace=True)
    
    df_b = pd.DataFrame(rates_b)
    df_b['time'] = pd.to_datetime(df_b['time'], unit='s')
    df_b.set_index('time', inplace=True)
    
    common_idx = df_a.index.intersection(df_b.index)
    df_a = df_a.loc[common_idx]
    df_b = df_b.loc[common_idx]
    print(f"Aligned candles: {len(common_idx)}")
    
    df_data = pd.DataFrame(index=common_idx)
    df_data['price_a'] = df_a['close'].values
    df_data['price_b'] = df_b['close'].values
    df_data['high_a'] = df_a['high'].values
    df_data['low_a'] = df_a['low'].values
    df_data['high_b'] = df_b['high'].values
    df_data['low_b'] = df_b['low'].values
    
    results = {}
    for z_thresh in [1.5, 1.8, 2.0]:
        total, wins, losses, wr = run_simulation(df_data.copy(), s_a, s_b, z_thresh)
        results[z_thresh] = {"total": total, "wins": wins, "losses": losses, "win_rate": wr}
        
    print("\n=== Backtest Summary Table ===")
    print("| Z-Score Entry | Total Trades | Winning Trades | Losing Trades | Win Rate (Accuracy) |")
    print("|---------------|--------------|----------------|---------------|---------------------|")
    for z_thresh, res in results.items():
        print(f"| {z_thresh:.1f}           | {res['total']:<12} | {res['wins']:<14} | {res['losses']:<13} | {res['win_rate']:.2f}%             |")
        
    mt5.shutdown()

if __name__ == "__main__":
    backtest_thresholds()
