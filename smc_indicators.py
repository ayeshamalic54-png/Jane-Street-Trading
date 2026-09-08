import numpy as np
import pandas as pd

def get_swing_points(df, n_left=2, n_right=2):
    """
    Returns lists of swing highs (price, index) and swing lows (price, index)
    using fractal definitions with n_left and n_right candles.
    """
    if df is None or len(df) < (n_left + n_right + 1):
        return [], []

    highs = df['high'].values
    lows = df['low'].values
    n = len(df)

    swing_highs = []
    swing_lows = []

    for i in range(n_left, n - n_right):
        is_sh = True
        is_sl = True

        for j in range(1, n_left + 1):
            if highs[i] <= highs[i - j]:
                is_sh = False
            if lows[i] >= lows[i - j]:
                is_sl = False

        for j in range(1, n_right + 1):
            if highs[i] <= highs[i + j]:
                is_sh = False
            if lows[i] >= lows[i + j]:
                is_sl = False

        if is_sh:
            swing_highs.append((float(highs[i]), i))
        if is_sl:
            swing_lows.append((float(lows[i]), i))

    return swing_highs, swing_lows


def detect_market_structure(df):
    """
    Pure M15 Market Structure Bias:
    - BULLISH: Higher Highs (HH) + Higher Lows (HL)
    - BEARISH: Lower Highs (LH) + Lower Lows (LL)
    - NEUTRAL: Mixed or insufficient swing data
    """
    swing_highs, swing_lows = get_swing_points(df, n_left=2, n_right=2)

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return 'NEUTRAL'

    has_hh = swing_highs[-1][0] > swing_highs[-2][0]
    has_hl = swing_lows[-1][0] > swing_lows[-2][0]

    has_lh = swing_highs[-1][0] < swing_highs[-2][0]
    has_ll = swing_lows[-1][0] < swing_lows[-2][0]

    if has_hh and has_hl:
        return 'BULLISH'
    elif has_lh and has_ll:
        return 'BEARISH'
    elif has_hh:
        return 'BULLISH'
    elif has_ll:
        return 'BEARISH'

    return 'NEUTRAL'


def detect_liquidity_sweep(df_m5):
    """
    Step 2: M5 Liquidity Sweep Detection.
    Checks if recent candles sweep a confirmed M5 swing low (sell-side) or swing high (buy-side).
    
    - Sell-side Sweep (for BUY): Candle low[i] < swing_low AND close[i] >= swing_low.
    - Buy-side Sweep (for SELL): Candle high[i] > swing_high AND close[i] <= swing_high.

    Returns:
    - (is_swept_sell_side, sweep_lowest_price, swing_level, sweep_idx)
    - (is_swept_buy_side, sweep_highest_price, swing_level, sweep_idx)
    """
    swing_highs, swing_lows = get_swing_points(df_m5, n_left=2, n_right=2)
    if not swing_highs or not swing_lows:
        return (False, 0.0, 0.0, -1), (False, 0.0, 0.0, -1)

    highs = df_m5['high'].values
    lows = df_m5['low'].values
    closes = df_m5['close'].values
    n = len(df_m5)

    sell_sweep = (False, 0.0, 0.0, -1)
    buy_sweep = (False, 0.0, 0.0, -1)

    # Check recent candles for a liquidity sweep
    lookback_start = max(0, n - 15)
    for i in range(lookback_start, n):
        # 1. Sell-side sweep (BUY setup): Price wicks below recent swing low, but closes ABOVE it
        for sl_val, sl_idx in reversed(swing_lows):
            if i > sl_idx + 1:
                if lows[i] < sl_val and closes[i] >= sl_val:
                    sell_sweep = (True, float(lows[i]), float(sl_val), i)
                    break
        if sell_sweep[0]:
            break

    for i in range(lookback_start, n):
        # 2. Buy-side sweep (SELL setup): Price wicks above recent swing high, but closes BELOW it
        for sh_val, sh_idx in reversed(swing_highs):
            if i > sh_idx + 1:
                if highs[i] > sh_val and closes[i] <= sh_val:
                    buy_sweep = (True, float(highs[i]), float(sh_val), i)
                    break
        if buy_sweep[0]:
            break

    return sell_sweep, buy_sweep


def detect_choch_bos(df_m5, sweep_idx, is_bullish=True):
    """
    Step 3: Bullish / Bearish CHoCH (Change of Character) & BOS.
    
    - Bullish CHoCH: After sell-side sweep, M5 candle CLOSES above the last minor lower high before/at the sweep.
    - Bearish CHoCH: After buy-side sweep, M5 candle CLOSES below the last minor higher low before/at the sweep.
    """
    if df_m5 is None or sweep_idx < 0 or sweep_idx >= len(df_m5):
        return False, 0.0

    highs = df_m5['high'].values
    lows = df_m5['low'].values
    closes = df_m5['close'].values
    n = len(df_m5)

    if is_bullish:
        # Minor lower high before or at sweep_idx
        minor_lh = max(highs[max(0, sweep_idx - 5):sweep_idx + 1])
        # Check if any candle from sweep_idx to current candle CLOSES above minor_lh
        for j in range(sweep_idx, n):
            if closes[j] > minor_lh:
                return True, float(minor_lh)
    else:
        # Minor higher low before or at sweep_idx
        minor_hl = min(lows[max(0, sweep_idx - 5):sweep_idx + 1])
        # Check if any candle from sweep_idx to current candle CLOSES below minor_hl
        for j in range(sweep_idx, n):
            if closes[j] < minor_hl:
                return True, float(minor_hl)

    return False, 0.0


def detect_smc_zones(df):
    """
    Step 4: Fair Value Gaps (3-Candle FVG).
    - Bullish FVG: low[i] > high[i-2]. Zone = (high[i-2], low[i]).
    - Bearish FVG: high[i] < low[i-2]. Zone = (high[i], low[i-2]).
    Returns active (unmitigated) FVGs.
    """
    if df is None or len(df) < 5:
        return {
            'bullish_fvg': [], 'bearish_fvg': [],
            'bullish_ob': [], 'bearish_ob': [],
            'bullish_breaker': [], 'bearish_breaker': [],
            'bullish_ifvg': [], 'bearish_ifvg': []
        }

    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    n = len(df)

    raw_bull_fvgs = []
    raw_bear_fvgs = []

    for i in range(2, n):
        if lows[i] > highs[i - 2]:
            raw_bull_fvgs.append((highs[i - 2], lows[i], i))
        elif highs[i] < lows[i - 2]:
            raw_bear_fvgs.append((highs[i], lows[i - 2], i))

    active_bull = []
    active_bear = []

    for low_b, high_b, idx in raw_bull_fvgs:
        mitigated = False
        for j in range(idx + 1, n):
            if closes[j] < low_b:
                mitigated = True
                break
        if not mitigated:
            active_bull.append((float(low_b), float(high_b)))

    for low_b, high_b, idx in raw_bear_fvgs:
        mitigated = False
        for j in range(idx + 1, n):
            if closes[j] > high_b:
                mitigated = True
                break
        if not mitigated:
            active_bear.append((float(low_b), float(high_b)))

    return {
        'bullish_fvg': active_bull,
        'bearish_fvg': active_bear,
        'bullish_ob': active_bull,
        'bearish_ob': active_bear,
        'bullish_breaker': active_bull,
        'bearish_breaker': active_bear,
        'bullish_ifvg': active_bull,
        'bearish_ifvg': active_bear
    }


def is_price_in_zones(price, zones):
    """Checks if current price is inside any active FVG zone."""
    for low, high in zones:
        if low <= price <= high:
            return True
    return False
