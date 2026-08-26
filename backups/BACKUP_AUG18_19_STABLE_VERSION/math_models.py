import numpy as np
import pandas as pd

class KalmanFilterRegression:
    """
    Kalman Filter for dynamic linear regression tracking: y = beta * x + alpha.
    Dynamically estimates the hedge ratio (beta) and spread intercept (alpha) 
    at every tick, outputting the normalized z-score of the spread.
    """
    def __init__(self, transition_covariance=1e-9, observation_covariance=1e-6, initial_beta=1.0):
        # Reference prices for normalization
        self.ref_x = None
        self.ref_y = None
        self.initial_beta = float(initial_beta)
        
        # State mean vector: [beta_norm, alpha_norm]^T
        self.state_mean = np.array([1.0, 0.0]) # Will be re-scaled on first update
        # State covariance matrix
        self.state_covariance = np.identity(2) * 1.0
        
        # Process noise covariance (Q)
        self.Q = np.identity(2) * transition_covariance
        # Measurement noise covariance (R)
        self.R = observation_covariance
        
        # History lists for velocity and volatility calculations
        self.z_history = []
        self.spread_history = []      # Normalized spread history
        self.raw_spread_history = []  # Raw spread history

    def update(self, x, y):
        """
        Runs one step of the Kalman Filter prediction and update loop.
        x: Independent asset price (e.g. Asset B)
        y: Dependent asset price (e.g. Asset A)
        Returns: (beta_actual, alpha_actual, raw_spread, z_score)
        """
        if self.ref_x is None:
            self.ref_x = float(x) if x > 0 else 1.0
            self.ref_y = float(y) if y > 0 else 1.0
            # Initialize beta_norm to align with initial_beta on raw price scales
            beta_norm_init = self.initial_beta * (self.ref_x / self.ref_y)
            self.state_mean = np.array([beta_norm_init, 0.0])
            
        norm_x = x / self.ref_x
        norm_y = y / self.ref_y
        
        # Observation matrix H = [norm_x, 1]
        H = np.array([[norm_x, 1.0]])
        
        # 1. PREDICT state
        state_covariance_pred = self.state_covariance + self.Q
        
        # 2. UPDATE state using normalized measurement
        y_pred = np.dot(H, self.state_mean)[0]
        y_err = norm_y - y_pred  # Normalized spread (residual error)
        
        # Innovation (residual) covariance
        S = np.dot(H, np.dot(state_covariance_pred, H.T))[0, 0] + self.R
        
        # Kalman Gain
        K = np.dot(state_covariance_pred, H.T) / S
        
        # Update state mean and covariance
        self.state_mean = self.state_mean + K.flatten() * y_err
        self.state_covariance = state_covariance_pred - np.dot(K, np.dot(H, state_covariance_pred))
        
        beta_norm = self.state_mean[0]
        alpha_norm = self.state_mean[1]
        
        # Scale parameters back to actual price scale
        beta_actual = beta_norm * (self.ref_y / self.ref_x)
        alpha_actual = alpha_norm * self.ref_y
        raw_spread = y - (beta_actual * x + alpha_actual)
        
        # Standard deviation of the spread using rolling 50-bar history for robust scale invariant z-score
        if len(self.spread_history) >= 10:
            rolling_std = float(np.std(self.spread_history[-50:]))
            std_dev = max(rolling_std, 1e-5)
        else:
            std_dev = np.sqrt(S)
            
        z_score = y_err / std_dev if std_dev > 0 else 0.0
        # Clip Z-score to [-4.5, +4.5] to prevent runaway outliers
        z_score = float(np.clip(z_score, -4.5, 4.5))
        
        # Track histories
        self.z_history.append(z_score)
        self.spread_history.append(y_err)
        self.raw_spread_history.append(raw_spread)
        if len(self.z_history) > 1000:
            self.z_history.pop(0)
            self.spread_history.pop(0)
            self.raw_spread_history.pop(0)
            
        return beta_actual, alpha_actual, raw_spread, z_score

    def get_current_z(self, x, y) -> float:
        """Calculates the current z-score of the spread without updating filter state."""
        if self.ref_x is None:
            return 0.0
        norm_x = x / self.ref_x
        norm_y = y / self.ref_y
        H = np.array([[norm_x, 1.0]])
        y_pred = np.dot(H, self.state_mean)[0]
        y_err = norm_y - y_pred
        if len(self.spread_history) >= 10:
            rolling_std = float(np.std(self.spread_history[-50:]))
            std_dev = max(rolling_std, 1e-5)
        else:
            state_covariance_pred = self.state_covariance + self.Q
            S = np.dot(H, np.dot(state_covariance_pred, H.T))[0, 0] + self.R
            std_dev = np.sqrt(S)
            
        z_val = float(y_err / std_dev) if std_dev > 0 else 0.0
        return float(np.clip(z_val, -4.5, 4.5))

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

def is_turning_point_confirmed(z_history, z_threshold=1.50, action="BUY_SPREAD"):
    """
    Checks if Z-score has reached extreme threshold AND confirms that the spread trajectory
    has inverted (turned back toward mean Z = 0.0).
    
    For BUY_SPREAD (Z <= -z_threshold):
      Requires: min(z_history[-5:]) <= -z_threshold AND z_history[-1] > z_history[-2] (turning upward)
      
    For SELL_SPREAD (Z >= +z_threshold):
      Requires: max(z_history[-5:]) >= z_threshold AND z_history[-1] < z_history[-2] (turning downward)
    """
    if len(z_history) < 3:
        return False
        
    recent_z = z_history[-5:]
    curr_z = z_history[-1]
    prev_z = z_history[-2]
    
    if action == "BUY_SPREAD":
        reached_extreme = min(recent_z) <= -z_threshold
        turning_up = curr_z > prev_z
        return reached_extreme and turning_up
        
    elif action == "SELL_SPREAD":
        reached_extreme = max(recent_z) >= z_threshold
        turning_down = curr_z < prev_z
        return reached_extreme and turning_down
        
    return False


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


def calculate_dynamic_atr_tp_pips(symbol, timeframe=None, period=14, multiplier=1.5, fallback_tp_pips=12.0):
    """
    Feature 3: Dynamic ATR (Average True Range) Based Targets
    Calculates the 14-period ATR for a symbol and derives dynamic Take Profit (TP) in pips based on 1.5x ATR multiplier.
    In high market volatility, TP expands for maximum profit; in low volatility, TP tightens to secure account.
    """

    import MetaTrader5 as mt5
    if timeframe is None:
        timeframe = mt5.TIMEFRAME_M15
        
    try:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, period + 10)
        if rates is None or len(rates) < period + 1:
            return fallback_tp_pips
            
        highs = rates['high']
        lows = rates['low']
        closes = rates['close']
        
        tr1 = highs[1:] - lows[1:]
        tr2 = np.abs(highs[1:] - closes[:-1])
        tr3 = np.abs(lows[1:] - closes[:-1])
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        
        atr_price = np.mean(tr[-period:])
        
        # Convert ATR to pips based on symbol point/digits
        symbol_info = mt5.symbol_info(symbol)
        point = symbol_info.point if symbol_info else 0.0001
        pip_size = (point * 10.0) if (symbol_info and symbol_info.digits in (3, 5)) else point
        if pip_size <= 0:
            pip_size = 0.0001
            
        atr_pips = float(atr_price / pip_size)
        dynamic_tp_pips = round(float(atr_pips * multiplier), 1)
        return max(dynamic_tp_pips, 5.0)
    except Exception as e:
        return fallback_tp_pips


def find_swing_high_low_tp(symbol, order_type="BUY", timeframe=None, lookback=30, fallback_pips=15.0):
    """
    Feature 4: Swing High / Swing Low (Structure Based) TP Targets
    Finds recent M15/H1 price action structure:
      - For BUY trades: Recent Swing High (Resistance level) target.
      - For SELL trades: Recent Swing Low (Support level) target.
    Returns: (target_tp_price, structure_type, target_pips)
    """
    import MetaTrader5 as mt5
    if timeframe is None:
        timeframe = mt5.TIMEFRAME_M15
        
    try:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, lookback)
        if rates is None or len(rates) < 5:
            tick = mt5.symbol_info_tick(symbol)
            curr = tick.ask if tick else 1.0
            return curr, "FALLBACK", fallback_pips
            
        symbol_info = mt5.symbol_info(symbol)
        point = symbol_info.point if symbol_info else 0.0001
        pip_size = (point * 10.0) if (symbol_info and symbol_info.digits in (3, 5)) else point
        tick = mt5.symbol_info_tick(symbol)
        curr_price = tick.ask if (tick and order_type == "BUY") else (tick.bid if tick else 1.0)
        
        if order_type == "BUY":
            # Target is recent Swing High (highest high in lookback)
            swing_high = float(np.max(rates['high']))
            target_pips = (swing_high - curr_price) / pip_size if pip_size > 0 else fallback_pips
            return swing_high, "SWING_HIGH_RESISTANCE", round(target_pips, 1)
        else:
            # Target is recent Swing Low (lowest low in lookback)
            swing_low = float(np.min(rates['low']))
            target_pips = (curr_price - swing_low) / pip_size if pip_size > 0 else fallback_pips
            return swing_low, "SWING_LOW_SUPPORT", round(target_pips, 1)
    except Exception as e:
        return 0.0, "ERROR", fallback_pips

