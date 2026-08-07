import numpy as np
import pandas as pd

class KalmanFilterRegression:
    """
    Kalman Filter for dynamic linear regression tracking: y = beta * x + alpha.
    Dynamically estimates the hedge ratio (beta) and spread intercept (alpha) 
    at every tick, outputting the normalized z-score of the spread.
    """
    def __init__(self, transition_covariance=1e-5, observation_covariance=1e-3):
        # State mean vector: [beta, alpha]^T
        self.state_mean = np.zeros(2)
        # State covariance matrix (initial high uncertainty)
        self.state_covariance = np.identity(2) * 1.0
        
        # Process noise covariance (Q) - how fast beta/alpha are expected to drift
        self.Q = np.identity(2) * transition_covariance
        # Measurement noise covariance (R) - variance of spread around regression line
        self.R = observation_covariance
        
        self.spread_history = []
        self.z_history = []
        self.raw_spread_history = []
        self.ref_x = None
        self.ref_y = None

    def update(self, x, y):
        """
        Runs one step of the Kalman Filter prediction and update loop.
        x: Independent asset price (e.g. Asset B)
        y: Dependent asset price (e.g. Asset A)
        Returns: (beta, alpha, spread, z_score)
        """
        if self.ref_x is None:
            self.ref_x = x
            self.ref_y = y
        
        norm_x = x / self.ref_x
        norm_y = y / self.ref_y
        
        # Observation matrix H = [x, 1]
        H = np.array([[norm_x, 1.0]])
        
        # 1. PREDICT state
        state_covariance_pred = self.state_covariance + self.Q
        
        # 2. UPDATE state using measurement y
        y_pred = np.dot(H, self.state_mean)[0]
        raw_spread = norm_y - y_pred
        y_err = raw_spread
        
        # Innovation (residual) covariance
        S = np.dot(H, np.dot(state_covariance_pred, H.T))[0, 0] + self.R
        
        # Kalman Gain
        K = np.dot(state_covariance_pred, H.T) / S
        
        # Update state mean and covariance
        self.state_mean = self.state_mean + K.flatten() * y_err
        self.state_covariance = state_covariance_pred - np.dot(K, np.dot(H, state_covariance_pred))
        
        beta = self.state_mean[0]
        alpha = self.state_mean[1]
        
        # Standard deviation of the spread (residual)
        std_dev = np.sqrt(S)
        z_score = y_err / std_dev if std_dev > 0 else 0.0
        
        return beta, alpha, y_err, z_score

def calculate_atr_volatility_ratio(df):
    """
    Calculates the 14-bar ATR vs 50-bar baseline ATR ratio to detect market volatility spikes.
    Returns: (ratio: float, is_spike: bool) where is_spike is True if ratio >= 1.30.
    """
    if df is None or len(df) < 50:
        return 1.0, False
    try:
        highs = df['high'].values
        lows = df['low'].values
        closes = df['close'].values
        
        tr1 = highs[1:] - lows[1:]
        tr2 = np.abs(highs[1:] - closes[:-1])
        tr3 = np.abs(lows[1:] - closes[:-1])
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        
        atr14 = np.mean(tr[-14:])
        atr50 = np.mean(tr[-50:])
        
        if atr50 <= 0:
            return 1.0, False
            
        ratio = float(atr14 / atr50)
        return ratio, (ratio >= 1.30)
    except Exception:
        return 1.0, False


def calculate_metals_dynamic_beta(df_a, df_b):
    """
    Calculates dynamic ATR-adjusted Beta for Metals (XAUUSD/XAGUSD):
    Beta = (Covariance(Price_A, Price_B) / Variance(Price_B)) * (ATR14_A / ATR14_B)
    """
    if df_a is None or df_b is None or len(df_a) < 20 or len(df_b) < 20:
        return 1.0
    try:
        closes_a = df_a['close'].values[-30:]
        closes_b = df_b['close'].values[-30:]
        min_len = min(len(closes_a), len(closes_b))
        ca = closes_a[-min_len:]
        cb = closes_b[-min_len:]
        
        cov_matrix = np.cov(ca, cb)
        var_b = cov_matrix[1, 1]
        cov_ab = cov_matrix[0, 1]
        
        if var_b <= 0:
            return 1.0
            
        raw_beta = cov_ab / var_b
        
        # Calculate ATR14 for A and B
        tr_a = np.maximum(df_a['high'].values[1:] - df_a['low'].values[1:], 
                          np.abs(df_a['high'].values[1:] - df_a['close'].values[:-1]))
        tr_b = np.maximum(df_b['high'].values[1:] - df_b['low'].values[1:], 
                          np.abs(df_b['high'].values[1:] - df_b['close'].values[:-1]))
        
        atr_a = float(np.mean(tr_a[-14:]))
        atr_b = float(np.mean(tr_b[-14:]))
        
        atr_ratio = (atr_a / atr_b) if atr_b > 0 else 1.0
        
        adjusted_beta = float(abs(raw_beta) * atr_ratio)
        return adjusted_beta
    except Exception:
        return 1.0

def test_cointegration(y, x):
    """
    Calculates the correlation coefficient between y and x as a robust check.
    Returns: 1.0 - correlation (lower value = stronger correlation)
    """
    if len(y) < 20 or len(x) < 20:
        return 1.0
    try:
        corr = np.corrcoef(x, y)[0, 1]
        return float(1.0 - abs(corr))
    except Exception:
        return 1.0


def calculate_obi(bids, asks, depth=5):
    """
    Calculates L2 Order Book Imbalance (OBI) to evaluate short-term buy/sell volume pressure.
    bids: list of tuples (price, volume)
    asks: list of tuples (price, volume)
    depth: number of book levels to analyze (max 5)
    Returns: OBI value in range [-1.0, 1.0] (positive = buy pressure, negative = sell pressure)
    """
    if not bids or not asks:
        return 0.0
        
    weighted_bid = 0.0
    weighted_ask = 0.0
    levels = min(depth, len(bids), len(asks))
    
    for i in range(levels):
        # Level weight decays with distance from spread (Level 1: 1.0, Level 2: 0.5, etc.)
        weight = 1.0 / (i + 1)
        weighted_bid += bids[i][1] * weight
        weighted_ask += asks[i][1] * weight
        
    denom = weighted_bid + weighted_ask
    if denom == 0:
        return 0.0
        
    obi = (weighted_bid - weighted_ask) / denom
    return float(obi)
