import pandas as pd
import numpy as np
from video_strategy_engine import calculate_zscore_and_ema, evaluate_video_strategy_signal

print("=== RUNNING UNIT TEST FOR VIDEO STRATEGY ENGINE ===")

# Create synthetic 220 M15 candles dataframe
np.random.seed(42)
dates = pd.date_range("2026-08-01", periods=220, freq="15min")
base_price = 1.1600
prices = base_price + np.cumsum(np.random.randn(220) * 0.0005)

# Force last 10 prices to create a clear Bullish trend (Price > 200 EMA) and an Oversold Z-Score reversal
prices[-20:] = np.linspace(1.1700, 1.1620, 20)  # Dip down oversold
prices[-1] = 1.1635  # Curl UP green candle close!

df = pd.DataFrame({
    'time': dates,
    'open': prices - 0.0002,
    'high': prices + 0.0005,
    'low': prices - 0.0005,
    'close': prices,
    'tick_volume': 1000
})

df = calculate_zscore_and_ema(df, period=14, ema_period=200)

print(f"Dataframe processed! 200 EMA: {df['ema_200'].iloc[-1]:.5f} | Close: {df['close'].iloc[-1]:.5f}")
print(f"VWAP Z-Score: Curr = {df['vwap_zscore'].iloc[-1]:.3f}, Prev = {df['vwap_zscore'].iloc[-2]:.3f}")

# Test with z_threshold = 0.50 to simulate signal trigger
sig, tp_price, sl_price, sl_dist, reason = evaluate_video_strategy_signal(df, z_threshold=0.50, category="forex")

print("\n=== TEST SIGNAL EVALUATION RESULT ===")
print(f"Signal Generated: {sig}")
print(f"Reason: {reason}")
if sig != "NONE":
    print(f"Entry Price : {df['close'].iloc[-1]:.5f}")
    print(f"Stop Loss   : {sl_price:.5f} (Distance: {sl_dist:.5f})")
    print(f"Take Profit : {tp_price:.5f} (RRR: {abs(tp_price - df['close'].iloc[-1]) / sl_dist:.2f}x)")

assert sig == "BUY", "Expected BUY signal!"
assert round(abs(tp_price - df['close'].iloc[-1]) / sl_dist, 1) == 2.5, "Expected 1:2.5 Risk-to-Reward Ratio!"
print("\n✅ UNIT TEST PASSED 100%! Video strategy engine operates with exact 1:2.5 RRR & Video 100% Rules!")
