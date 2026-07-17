import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from math_models import KalmanFilterRegression
from data_ingestion import initialize_mt5, shutdown_mt5, resolve_broker_symbol

def test_z_scores():
    mt5.initialize()
    s_a = resolve_broker_symbol("EURUSD")
    s_b = resolve_broker_symbol("GBPUSD")
    print(f"Resolved: {s_a}, {s_b}")
    
    rates_a = mt5.copy_rates_from_pos(s_a, mt5.TIMEFRAME_M5, 0, 4000)
    rates_b = mt5.copy_rates_from_pos(s_b, mt5.TIMEFRAME_M5, 0, 4000)
    
    df_a = pd.DataFrame(rates_a)
    df_a['time'] = pd.to_datetime(df_a['time'], unit='s')
    df_a.set_index('time', inplace=True)
    
    df_b = pd.DataFrame(rates_b)
    df_b['time'] = pd.to_datetime(df_b['time'], unit='s')
    df_b.set_index('time', inplace=True)
    
    common_idx = df_a.index.intersection(df_b.index)
    df_a = df_a.loc[common_idx]
    df_b = df_b.loc[common_idx]
    
    kf = KalmanFilterRegression(transition_covariance=1e-4, observation_covariance=1e-4)
    z_scores = []
    
    prices_a = df_a['close'].values
    prices_b = df_b['close'].values
    
    for i in range(len(common_idx)):
        beta, alpha, spread, z = kf.update(prices_b[i], prices_a[i])
        z_scores.append(z)
        
    z_scores = np.array(z_scores)
    print(f"Min Z-Score: {z_scores.min():.4f}")
    print(f"Max Z-Score: {z_scores.max():.4f}")
    print(f"Mean Z-Score: {z_scores.mean():.4f}")
    print(f"Std Dev of Z-Scores: {z_scores.std():.4f}")
    
    # Count how many are outside [-2.0, 2.0]
    out_of_bounds = np.sum((z_scores < -2.0) | (z_scores > 2.0))
    print(f"Count outside [-2.0, 2.0]: {out_of_bounds}")
    
    mt5.shutdown()

if __name__ == "__main__":
    test_z_scores()
