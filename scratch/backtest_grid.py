import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from math_models import KalmanFilterRegression
from data_ingestion import resolve_broker_symbol

def get_symbol_category(symbol: str) -> str:
    return "forex"

def get_pip_size(symbol: str) -> float:
    return 0.0001

def get_sl_distance(symbol: str, price: float, sl_pips: float) -> float:
    return sl_pips * get_pip_size(symbol)

def get_kf_parameters(symbol: str):
    return 1e-10, 1e-7

def run_simulation(df_data, s_a, s_b, z_entry, sl_pips):
    total_trades = 0
    winning_trades = 0
    losing_trades = 0
    active_trade = None

    q_cov, r_cov = get_kf_parameters(s_a)
    kf = KalmanFilterRegression(transition_covariance=q_cov, observation_covariance=r_cov)
    
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

    i = 100
    while i < len(df_data) - 1:
        z = df_data['z_score'].iloc[i]
        price_a = prices_a[i]
        price_b = prices_b[i]
        
        if active_trade is None:
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
                    "sl_a": sl_price_a,
                    "sl_b": sl_price_b
                }
        else:
            action = active_trade["action"]
            sl_price_a = active_trade["sl_a"]
            sl_price_b = active_trade["sl_b"]
            
            fut_z = df_data['z_score'].iloc[i]
            fut_high_a = highs_a[i]
            fut_low_a = lows_a[i]
            fut_high_b = highs_b[i]
            fut_low_b = lows_b[i]
            
            tp_hit = False
            if (action == "BUY" and fut_z >= 0.0) or (action == "SELL" and fut_z <= 0.0):
                tp_hit = True
                
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
                active_trade = None
                
        i += 1
        
    win_rate = (winning_trades / total_trades) * 100.0 if total_trades > 0 else 0.0
    return total_trades, winning_trades, losing_trades, win_rate

def run_grid():
    mt5.initialize()
    s_a = resolve_broker_symbol("EURUSD")
    s_b = resolve_broker_symbol("GBPUSD")
    
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
    
    df_data = pd.DataFrame(index=common_idx)
    df_data['price_a'] = df_a['close'].values
    df_data['price_b'] = df_b['close'].values
    df_data['high_a'] = df_a['high'].values
    df_data['low_a'] = df_a['low'].values
    df_data['high_b'] = df_b['high'].values
    df_data['low_b'] = df_b['low'].values
    
    print("\n=== Grid Backtest: Z-Thresholds vs Stop Loss Pips (8000 Candles) ===")
    print("| Z-Score Entry | SL Pips | Total Trades | Win Rate (Accuracy) |")
    print("|---------------|---------|--------------|---------------------|")
    
    for z in [1.5, 1.8, 2.0]:
        for sl in [10.0, 20.0, 30.0, 40.0]:
            total, wins, losses, wr = run_simulation(df_data.copy(), s_a, s_b, z, sl)
            print(f"| {z:.1f}           | {sl:<7} | {total:<12} | {wr:.2f}%             |")
            
    mt5.shutdown()

if __name__ == "__main__":
    run_grid()
