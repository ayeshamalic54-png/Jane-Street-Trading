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
        
        # History lists for velocity and volatility calculations
        self.z_history = []
        self.spread_history = []

    def update(self, x, y):
        """
        Runs one step of the Kalman Filter prediction and update loop.
        x: Independent asset price (e.g. Asset B)
        y: Dependent asset price (e.g. Asset A)
        Returns: (beta, alpha, spread, z_score)
        """
        # Observation matrix H = [x, 1]
        H = np.array([[x, 1.0]])
        
        # 1. PREDICT state
        state_covariance_pred = self.state_covariance + self.Q
        
        # 2. UPDATE state using measurement y
        y_pred = np.dot(H, self.state_mean)[0]
        y_err = y - y_pred  # Spread (residual error)
        
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
        
        # Track histories
        self.z_history.append(z_score)
        self.spread_history.append(y_err)
        if len(self.z_history) > 1000:
            self.z_history.pop(0)
            self.spread_history.pop(0)
            
        return beta, alpha, y_err, z_score

    def get_velocity(self, k=3) -> float:
        """Calculates the change in z-score over the last k periods."""
        if len(self.z_history) <= k:
            return 0.0
        return float(self.z_history[-1] - self.z_history[-1 - k])

    def get_dynamic_z_entry(self, base_z_entry: float, gamma=0.3, short_w=20, long_w=200) -> float:
        """Dynamically increases the entry threshold if short-term volatility exceeds long-term trend."""
        if len(self.spread_history) < long_w:
            return base_z_entry
        spreads_short = self.spread_history[-short_w:]
        spreads_long = self.spread_history[-long_w:]
        std_short = np.std(spreads_short)
        std_long = np.std(spreads_long)
        
        ratio = std_short / std_long if std_long > 0 else 1.0
        # If short-term volatility spikes, we scale up the required z-score threshold
        return float(base_z_entry * (1.0 + gamma * max(0.0, ratio - 1.0)))

def calculate_half_life(spread_history) -> float:
    """
    Fits the spread history to an AR(1) process and returns the half-life of mean reversion.
    y_t = alpha + beta * y_{t-1} + e_t
    reversion_speed theta = -ln(beta)
    half_life H = ln(2) / theta
    """
    if len(spread_history) < 50:
        return 45.0  # Default fallback half-life (45 bars = ~3.75 hours on M5)
    
    y = np.array(spread_history[1:])
    x = np.array(spread_history[:-1])
    
    try:
        # Run linear regression: y = beta * x + alpha
        X = np.vstack([x, np.ones(len(x))]).T
        beta, alpha = np.linalg.lstsq(X, y, rcond=None)[0]
        
        if 0 < beta < 1:
            theta = -np.log(beta)
            half_life = np.log(2) / theta
            return float(np.clip(half_life, 5, 200))
    except Exception:
        pass
    return 45.0

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
