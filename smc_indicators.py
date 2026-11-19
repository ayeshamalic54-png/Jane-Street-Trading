import numpy as np
import pandas as pd

def get_swing_points(df, n_left=3, n_right=3, min_amplitude=0.0):
    """
    Returns lists of swing highs (price, index) and swing lows (price, index)
    using institutional fractal definitions with n_left and n_right candles.
    Optionally enforces min_amplitude to filter out tight consolidation noise.
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
            if min_amplitude > 0.0:
                base_low = min(lows[i - n_left:i + n_right + 1])
                if (highs[i] - base_low) < min_amplitude:
                    is_sh = False
            if is_sh:
                swing_highs.append((float(highs[i]), i))

        if is_sl:
            if min_amplitude > 0.0:
                base_high = max(highs[i - n_left:i + n_right + 1])
                if (base_high - lows[i]) < min_amplitude:
                    is_sl = False
            if is_sl:
                swing_lows.append((float(lows[i]), i))

    return swing_highs, swing_lows


def get_smc_asset_profile(df=None, symbol=None, category=None, ref_price=None):
    """
    Return symbol/price-calibrated SMC structural thresholds.
    Preserves XAUUSD (Gold) and Forex/JPY byte-for-byte while scaling US30 and NAS100
    cleanly (approx 8.5x Gold points with 105pt / 85pt SL caps) based on empirical M5/M15 volatility.
    """
    sym_str = ""
    if symbol is not None:
        sym_str = str(symbol).upper()
    elif df is not None:
        try:
            attrs = getattr(df, "attrs", {}) or {}
            if attrs.get("symbol"):
                sym_str = str(attrs.get("symbol")).upper()
            elif hasattr(df, "columns") and "symbol" in df.columns and len(df) > 0:
                sym_str = str(df["symbol"].iloc[-1]).upper()
        except Exception:
            sym_str = ""

    cat_str = str(category or "").lower()
    if not cat_str and df is not None:
        try:
            cat_str = str((getattr(df, "attrs", {}) or {}).get("category", "")).lower()
        except Exception:
            cat_str = ""

    px = 0.0
    if ref_price is not None:
        try:
            px = float(ref_price)
        except Exception:
            px = 0.0
    elif df is not None and len(df) > 0:
        try:
            px = float(df["close"].iloc[-1])
        except Exception:
            px = 0.0

    is_us30 = any(k in sym_str for k in ("US30", "DJ30", "WS30", "DOW"))
    is_nas100 = any(k in sym_str for k in ("NAS100", "USTEC", "US100", "NDX", "NQ="))
    if not is_us30 and not is_nas100 and cat_str == "indices":
        is_us30 = px >= 35000
        is_nas100 = not is_us30
    if not is_us30 and not is_nas100 and not any(k in sym_str for k in ("XAU", "GOLD", "XAG", "SILVER")):
        if px >= 30000:
            is_us30 = True
        elif px >= 12000:
            is_nas100 = True

    if is_us30:
        return {
            "key": "us30",
            "category": "indices",
            "is_high_point": True,
            "digits": 2,
            "m15_min_amp": 25.50,
            "m15_target_min_amp": 21.25,
            "m5_min_amp": 10.60,
            "min_structural_depth": 12.75,
            "min_penetration": 0.85,
            "reclaim_max_dip": 12.75,
            "min_fvg_gap": 3.40,
            "max_dist": 153.00,
            "min_ob_disp": 6.80,
            "mit_tol": 1.70,
            "wick_buf": 6.50,
            "close_tol": 2.15,
            "min_pen_gap": 6.80,
            "sweep_margin": 4.25,
            "max_chase_dist": 17.00,
            "max_sl_cap": 105.00,
            "target_min_move": 12.75,
            "ob_buf": 9.35,
            "min_dist": 0.10,
            "fallback_sl_dist": 21.25,
            "sweep_tol": 4.25,
            "be_buffer": 2.15,
        }

    if is_nas100:
        return {
            "key": "nas100",
            "category": "indices",
            "is_high_point": True,
            "digits": 2,
            "m15_min_amp": 25.50,
            "m15_target_min_amp": 21.25,
            "m5_min_amp": 10.60,
            "min_structural_depth": 12.75,
            "min_penetration": 0.85,
            "reclaim_max_dip": 12.75,
            "min_fvg_gap": 3.40,
            "max_dist": 153.00,
            "min_ob_disp": 6.80,
            "mit_tol": 1.70,
            "wick_buf": 6.50,
            "close_tol": 2.15,
            "min_pen_gap": 6.80,
            "sweep_margin": 4.25,
            "max_chase_dist": 17.00,
            "max_sl_cap": 85.00,
            "target_min_move": 12.75,
            "ob_buf": 9.35,
            "min_dist": 0.10,
            "fallback_sl_dist": 21.25,
            "sweep_tol": 4.25,
            "be_buffer": 2.15,
        }

    is_metals = (
        cat_str == "metals"
        or any(k in sym_str for k in ("XAU", "GOLD", "XAG", "SILVER"))
        or px > 500
    )
    if is_metals:
        return {
            "key": "gold",
            "category": "metals",
            "is_high_point": True,
            "digits": 2,
            "m15_min_amp": 3.00,
            "m15_target_min_amp": 2.50,
            "m5_min_amp": 1.25,
            "min_structural_depth": 1.50,
            "min_penetration": 0.10,
            "reclaim_max_dip": 1.50,
            "min_fvg_gap": 0.40,
            "max_dist": 18.00,
            "min_ob_disp": 0.80,
            "mit_tol": 0.20,
            "wick_buf": 0.75,
            "close_tol": 0.25,
            "min_pen_gap": 0.80,
            "sweep_margin": 0.50,
            "max_chase_dist": 2.00,
            "max_sl_cap": 10.00,
            "target_min_move": 1.50,
            "ob_buf": 1.10,
            "min_dist": 0.01,
            "fallback_sl_dist": 2.50,
            "sweep_tol": 0.50,
            "be_buffer": 0.25,
        }

    is_mid_fx = px > 20
    return {
        "key": "forex",
        "category": "forex",
        "is_high_point": False,
        "digits": 5,
        "m15_min_amp": 0.0020,
        "m15_target_min_amp": 0.0012,
        "m5_min_amp": 0.00015,
        "min_structural_depth": 0.0010,
        "min_penetration": 0.00003,
        "reclaim_max_dip": 0.0008,
        "min_fvg_gap": 0.04 if is_mid_fx else 0.00015,
        "max_dist": 2.00 if is_mid_fx else 0.0080,
        "min_ob_disp": 0.12 if is_mid_fx else 0.0004,
        "mit_tol": 0.03 if is_mid_fx else 0.00010,
        "wick_buf": 0.00040,
        "close_tol": 0.00015,
        "min_pen_gap": 0.00040,
        "sweep_margin": 0.00020,
        "max_chase_dist": 0.00100,
        "max_sl_cap": 0.0050,
        "target_min_move": 0.0005,
        "ob_buf": 0.00035,
        "min_dist": 0.00010,
        "fallback_sl_dist": 0.0015,
        "sweep_tol": 0.00030,
        "be_buffer": 0.00005,
    }


def detect_market_structure(df, symbol=None, category=None):
    """
    Institutional M15 Market Structure Bias with Structural Trend Memory:
    - BULLISH: Higher Highs & Higher Lows (HH & HL), or continuing uptrend until HL breaks.
    - BEARISH: Lower Highs & Lower Lows (LH & LL), or continuing downtrend until LH breaks.
    - NEUTRAL: Only returned if historical swing data is flat or undefined.
    """
    if df is None or len(df) < 5:
        return 'NEUTRAL'

    profile = get_smc_asset_profile(df, symbol=symbol, category=category)
    min_amp = profile["m15_min_amp"]
    swing_highs, swing_lows = get_swing_points(df, n_left=3, n_right=3, min_amplitude=min_amp)
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        swing_highs, swing_lows = get_swing_points(df, n_left=2, n_right=2, min_amplitude=min_amp * 0.65)
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        swing_highs, swing_lows = get_swing_points(df, n_left=2, n_right=2)

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return 'NEUTRAL'

    has_hh = swing_highs[-1][0] > swing_highs[-2][0]
    has_hl = swing_lows[-1][0] > swing_lows[-2][0]
    has_lh = swing_highs[-1][0] < swing_highs[-2][0]
    has_ll = swing_lows[-1][0] < swing_lows[-2][0]

    curr_close = float(df['close'].iloc[-1])
    closes_arr = df['close'].values
    last_sh_val, last_sh_idx = swing_highs[-1]
    last_sl_val, last_sl_idx = swing_lows[-1]
    last_bull_bos_idx = max(
        [last_sh_idx + 1 + k for k, c in enumerate(closes_arr[last_sh_idx + 1:]) if float(c) > last_sh_val],
        default=-1,
    )
    last_bear_bos_idx = max(
        [last_sl_idx + 1 + k for k, c in enumerate(closes_arr[last_sl_idx + 1:]) if float(c) < last_sl_val],
        default=-1,
    )
    recent_sh_levels = [p for p, idx in swing_highs]
    recent_sl_levels = [p for p, idx in swing_lows]
    key_resistance = max(recent_sh_levels[-2:]) if len(recent_sh_levels) >= 2 else (recent_sh_levels[-1] if recent_sh_levels else None)
    key_support = min(recent_sl_levels[-2:]) if len(recent_sl_levels) >= 2 else (recent_sl_levels[-1] if recent_sl_levels else None)

    if has_hh and has_hl:
        if last_bear_bos_idx > last_bull_bos_idx and curr_close < last_sl_val:
            return 'BEARISH'
        return 'BULLISH'
    elif has_lh and has_ll:
        if last_bull_bos_idx > last_bear_bos_idx and curr_close > last_sh_val:
            return 'BULLISH'
        return 'BEARISH'
    elif has_ll:
        if key_resistance is not None and curr_close > key_resistance:
            return 'BULLISH'
        return 'BEARISH'
    elif has_hh:
        if key_support is not None and curr_close < key_support:
            return 'BEARISH'
        return 'BULLISH'
    elif has_lh and has_hl:
        # Inside contracting range (Lower High + Higher Low): follow the most recent confirmed M15 BOS close
        if last_bear_bos_idx > last_bull_bos_idx:
            return 'BEARISH'
        if last_bull_bos_idx > last_bear_bos_idx:
            return 'BULLISH'
        return 'NEUTRAL'
    elif has_hl and not has_ll:
        return 'BULLISH'
    elif has_lh and not has_hh:
        return 'BEARISH'
    return 'NEUTRAL'


def detect_liquidity_sweep(df_m5, symbol=None, category=None):
    """
    Step 2: M5 Liquidity Sweep (Stop Loss Hunt) Detection.
    Captures genuine 1-candle wick sweeps AND 2-candle reclaim sweeps beyond confirmed M5 Swing Highs/Lows
    over an 18-candle (90 min) session window.

    Returns:
    - (is_swept_sell_side, sweep_lowest_price, swing_level, sweep_idx)
    - (is_swept_buy_side, sweep_highest_price, swing_level, sweep_idx)
    """
    if df_m5 is None or len(df_m5) < 10:
        return (False, 0.0, 0.0, -1), (False, 0.0, 0.0, -1)

    profile = get_smc_asset_profile(df_m5, symbol=symbol, category=category)
    min_amp = profile["m5_min_amp"]
    swing_highs, swing_lows = get_swing_points(df_m5, n_left=3, n_right=3, min_amplitude=min_amp)
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        swing_highs, swing_lows = get_swing_points(df_m5, n_left=2, n_right=2, min_amplitude=min_amp)
    if not swing_highs or not swing_lows:
        swing_highs, swing_lows = get_swing_points(df_m5, n_left=2, n_right=2)
    if not swing_highs or not swing_lows:
        return (False, 0.0, 0.0, -1), (False, 0.0, 0.0, -1)

    highs = df_m5['high'].values
    lows = df_m5['low'].values
    closes = df_m5['close'].values
    n = len(df_m5)

    sell_sweep = (False, 0.0, 0.0, -1)
    buy_sweep = (False, 0.0, 0.0, -1)

    min_structural_depth = profile["min_structural_depth"]
    min_penetration = profile["min_penetration"]
    reclaim_max_dip = profile["reclaim_max_dip"]

    # Evaluate up to newest bars over an 18-candle (90-min) institutional session window
    lookback_start = max(0, n - 18)
    for i in range(n - 1, lookback_start - 1, -1):
        # 1. Sell-side sweep (BUY setup): Price wicks below structural swing low and reclaims above
        for sl_val, sl_idx in reversed(swing_lows):
            if i > sl_idx + 1:
                prior_peak = max(highs[max(0, sl_idx - 6):sl_idx + 1])
                if (prior_peak - sl_val) < min_structural_depth:
                    continue

                if i - 1 < 0 or closes[i - 1] < sl_val:
                    continue  # Genuine sweep must originate from above swing low just prior to bar i

                is_one_bar_sweep = (sl_val - lows[i]) >= min_penetration and closes[i] >= sl_val
                is_two_bar_reclaim = (
                    (i + 1 < n - 1)
                    and (sl_val - lows[i]) >= min_penetration
                    and closes[i] >= (sl_val - reclaim_max_dip)
                    and closes[i + 1] >= sl_val
                )
                if is_one_bar_sweep or is_two_bar_reclaim:
                    sweep_low = float(min(lows[i], lows[i + 1])) if is_two_bar_reclaim else float(lows[i])
                    sweep_end_idx = (i + 1) if is_two_bar_reclaim else i
                    # Ensure adjacent prior candle didn't already dip lower than sweep_low (avoids late bounce mislabeling)
                    prior_lower = any(lows[k] < sweep_low for k in range(max(sl_idx + 1, i - 3), i))
                    # Check confirmed closed bars after reclaim so a single forming tick doesn't erase active setup
                    subsequent_break = any(closes[k] < sweep_low for k in range(sweep_end_idx + 1, max(sweep_end_idx + 1, n - 1)))
                    if not prior_lower and not subsequent_break:
                        sell_sweep = (True, sweep_low, float(sl_val), i)
                        break
        if sell_sweep[0]:
            break

    for i in range(n - 1, lookback_start - 1, -1):
        # 2. Buy-side sweep (SELL setup): Price wicks above structural swing high and reclaims below
        for sh_val, sh_idx in reversed(swing_highs):
            if i > sh_idx + 1:
                prior_trough = min(lows[max(0, sh_idx - 6):sh_idx + 1])
                if (sh_val - prior_trough) < min_structural_depth:
                    continue

                if i - 1 < 0 or closes[i - 1] > sh_val:
                    continue  # Genuine sweep must originate from below swing high just prior to bar i

                is_one_bar_sweep = (highs[i] - sh_val) >= min_penetration and closes[i] <= sh_val
                is_two_bar_reclaim = (
                    (i + 1 < n - 1)
                    and (highs[i] - sh_val) >= min_penetration
                    and closes[i] <= (sh_val + reclaim_max_dip)
                    and closes[i + 1] <= sh_val
                )
                if is_one_bar_sweep or is_two_bar_reclaim:
                    sweep_high = float(max(highs[i], highs[i + 1])) if is_two_bar_reclaim else float(highs[i])
                    sweep_end_idx = (i + 1) if is_two_bar_reclaim else i
                    prior_higher = any(highs[k] > sweep_high for k in range(max(sh_idx + 1, i - 3), i))
                    subsequent_break = any(closes[k] > sweep_high for k in range(sweep_end_idx + 1, max(sweep_end_idx + 1, n - 1)))
                    if not prior_higher and not subsequent_break:
                        buy_sweep = (True, sweep_high, float(sh_val), i)
                        break
        if buy_sweep[0]:
            break

    return sell_sweep, buy_sweep


def detect_choch_bos(df_m5, sweep_idx, is_bullish=True):
    """
    Step 3: Bullish / Bearish CHoCH (Change of Character) & BOS.
    - Bullish CHoCH: After sell-side sweep, M5 candle CLOSES above the last confirmed swing high formed PRIOR to the sweep.
    - Bearish CHoCH: After buy-side sweep, M5 candle CLOSES below the last confirmed swing low formed PRIOR to the sweep.
    """
    if df_m5 is None or sweep_idx < 0 or sweep_idx >= len(df_m5):
        return False, 0.0, -1

    highs = df_m5['high'].values
    lows = df_m5['low'].values
    closes = df_m5['close'].values
    n = len(df_m5)

    swing_highs, swing_lows = get_swing_points(df_m5, n_left=2, n_right=2)

    if is_bullish:
        prior_sh = [p for p, idx in swing_highs if idx < sweep_idx]
        if prior_sh:
            choch_lvl = prior_sh[-1]
        else:
            choch_lvl = max(highs[max(0, sweep_idx - 6):sweep_idx])

        for j in range(sweep_idx + 1, n):
            if closes[j] > choch_lvl:
                return True, float(choch_lvl), j
    else:
        prior_sl = [p for p, idx in swing_lows if idx < sweep_idx]
        if prior_sl:
            choch_lvl = prior_sl[-1]
        else:
            choch_lvl = min(lows[max(0, sweep_idx - 6):sweep_idx])

        for j in range(sweep_idx + 1, n):
            if closes[j] < choch_lvl:
                return True, float(choch_lvl), j

    return False, 0.0, -1


def detect_order_blocks(df, min_disp=0.80, max_dist=18.0):
    """Detects Order Blocks (OB) and Breaker Blocks."""
    if df is None or len(df) < 5:
        return [], [], [], []

    highs = df['high'].values
    lows = df['low'].values
    opens = df['open'].values
    closes = df['close'].values
    n = len(df)
    last_price = closes[-1]

    raw_bull_obs = []
    raw_bear_obs = []

    for i in range(2, n - 1):
        disp = abs(closes[i] - opens[i])
        if disp < min_disp:
            continue

        if closes[i - 1] < opens[i - 1] and closes[i] > highs[i - 2]:
            ob_low = float(lows[i - 1])
            ob_high = float(highs[i - 1])
            if abs(((ob_low + ob_high) / 2) - last_price) <= max_dist:
                raw_bull_obs.append((ob_low, ob_high, i))
        elif closes[i - 1] > opens[i - 1] and closes[i] < lows[i - 2]:
            ob_low = float(lows[i - 1])
            ob_high = float(highs[i - 1])
            if abs(((ob_low + ob_high) / 2) - last_price) <= max_dist:
                raw_bear_obs.append((ob_low, ob_high, i))

    active_bull_obs = []
    active_bear_obs = []
    breaker_bull_obs = []
    breaker_bear_obs = []

    for low_b, high_b, idx in raw_bull_obs:
        mitigated = False
        broken_as_breaker = False
        for j in range(idx + 1, n):
            if closes[j] < low_b:
                mitigated = True
                broken_as_breaker = True
                break
        if not mitigated:
            active_bull_obs.append((low_b, high_b))
        elif broken_as_breaker:
            if closes[-1] >= low_b and abs(last_price - low_b) <= max_dist:
                breaker_bear_obs.append((low_b, high_b))

    for low_b, high_b, idx in raw_bear_obs:
        mitigated = False
        broken_as_breaker = False
        for j in range(idx + 1, n):
            if closes[j] > high_b:
                mitigated = True
                broken_as_breaker = True
                break
        if not mitigated:
            active_bear_obs.append((low_b, high_b))
        elif broken_as_breaker:
            if closes[-1] <= high_b and abs(last_price - high_b) <= max_dist:
                breaker_bull_obs.append((low_b, high_b))

    return active_bull_obs[-2:], active_bear_obs[-2:], breaker_bull_obs[-2:], breaker_bear_obs[-2:]


def detect_smc_zones(df, min_idx=0, sweep_low=None, sweep_high=None, symbol=None, category=None):
    """
    Step 4: Fair Value Gaps (3-Candle FVG), Order Blocks (OB), and Breaker Blocks.
    Uses balanced institutional M5 displacement thresholds scaled per asset profile (Gold, US30, NAS100, Forex)
    so legitimate M5 scalping FVGs are captured accurately without losing precision.
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
    last_price = closes[-1]

    profile = get_smc_asset_profile(df, symbol=symbol, category=category, ref_price=last_price)
    if profile["key"] in ("us30", "nas100", "gold"):
        min_gap = profile["min_fvg_gap"]
        max_dist = profile["max_dist"]
        min_ob_disp = profile["min_ob_disp"]
        mit_tol = profile["mit_tol"]
        sweep_margin = profile["sweep_margin"]
    elif last_price > 20:
        min_gap = 0.04       # Silver / Platinum / JPY
        max_dist = 2.00
        min_ob_disp = 0.06
        mit_tol = 0.02
        sweep_margin = 0.50
    else:
        min_gap = 0.00018    # Forex (1.8 pips)
        max_dist = 0.0080
        min_ob_disp = 0.00025
        mit_tol = 0.00010
        sweep_margin = 0.50

    raw_bull_fvgs = []
    raw_bear_fvgs = []

    start_scan = max(2, min_idx if min_idx >= 0 else 0)
    for i in range(start_scan, n):
        gap_up = lows[i] - highs[i - 2]
        gap_down = lows[i - 2] - highs[i]
        if gap_up >= min_gap:
            if sweep_low is None or highs[i - 2] >= (sweep_low - sweep_margin):
                raw_bull_fvgs.append((highs[i - 2], lows[i], i))
        elif gap_down >= min_gap:
            if sweep_high is None or lows[i - 2] <= (sweep_high + sweep_margin):
                raw_bear_fvgs.append((highs[i], lows[i - 2], i))

    active_bull = []
    active_bear = []
    active_bull_meta = []
    active_bear_meta = []
    mitigated_bull_fvgs = []
    mitigated_bear_fvgs = []

    for low_b, high_b, idx in raw_bull_fvgs:
        mitigated = False
        # Do not mitigate on the final still-forming bar n-1; wait for bar close
        for j in range(idx + 1, max(idx + 1, n - 1)):
            if closes[j] < (low_b - mit_tol):
                mitigated = True
                break
        if not mitigated:
            if abs(((low_b + high_b) / 2) - last_price) <= max_dist:
                active_bull.append((float(low_b), float(high_b)))
                active_bull_meta.append((float(low_b), float(high_b), int(idx)))
        else:
            mitigated_bull_fvgs.append((float(low_b), float(high_b), idx))

    for low_b, high_b, idx in raw_bear_fvgs:
        mitigated = False
        for j in range(idx + 1, max(idx + 1, n - 1)):
            if closes[j] > (high_b + mit_tol):
                mitigated = True
                break
        if not mitigated:
            if abs(((low_b + high_b) / 2) - last_price) <= max_dist:
                active_bear.append((float(low_b), float(high_b)))
                active_bear_meta.append((float(low_b), float(high_b), int(idx)))
        else:
            mitigated_bear_fvgs.append((float(low_b), float(high_b), idx))

    bull_ob, bear_ob, bull_breaker, bear_breaker = detect_order_blocks(df, min_disp=min_ob_disp, max_dist=max_dist)

    bullish_ifvg = []
    bearish_ifvg = []
    for low_b, high_b, idx in mitigated_bear_fvgs[-3:]:
        if closes[-1] > high_b and (closes[-1] - high_b) <= (max_dist * 0.5):
            bullish_ifvg.append((low_b, high_b))
    for low_b, high_b, idx in mitigated_bull_fvgs[-3:]:
        if closes[-1] < low_b and (low_b - closes[-1]) <= (max_dist * 0.5):
            bearish_ifvg.append((low_b, high_b))

    return {
        'bullish_fvg': [(l, h) for l, h in active_bull[-2:]],
        'bearish_fvg': [(l, h) for l, h in active_bear[-2:]],
        'bullish_fvg_meta': active_bull_meta[-2:],
        'bearish_fvg_meta': active_bear_meta[-2:],
        'bullish_ob': bull_ob[-2:],
        'bearish_ob': bear_ob[-2:],
        'bullish_breaker': bull_breaker[-2:],
        'bearish_breaker': bear_breaker[-2:],
        'bullish_ifvg': bullish_ifvg[-1:],
        'bearish_ifvg': bearish_ifvg[-1:]
    }


def is_price_in_zones(price, zones):
    """Checks if current price is inside any active zone."""
    for low, high in zones:
        if low <= price <= high:
            return True
    return False


def check_fvg_retest(closed_open, closed_high, closed_low, closed_close, fvg_zones, is_bullish=True, max_wick_buf=0.75, prev_row=None, closed_idx=None, close_tol=None, min_pen_gap=None):
    """
    Step 5: Institutional Closed-Candle FVG Retest Verification.
    Ensures ONLY candles strictly AFTER FVG creation (candle_idx > fvg_creation_idx)
    can qualify as a pullback/retest, preventing false triggers on the displacement bar itself.
    fvg_zones can contain (low_b, high_b) or (low_b, high_b, creation_idx) tuples.
    """
    if close_tol is None:
        close_tol = 0.25 if max_wick_buf >= 0.1 else 0.00015
    if min_pen_gap is None:
        min_pen_gap = 0.80 if max_wick_buf >= 0.1 else 0.00040

    prev_low = float(prev_row['low']) if prev_row is not None else None
    prev_high = float(prev_row['high']) if prev_row is not None else None
    prev_close = float(prev_row['close']) if prev_row is not None else None
    prev_idx = (closed_idx - 1) if closed_idx is not None else None

    for item in reversed(fvg_zones):
        low_b, high_b = float(item[0]), float(item[1])
        creation_idx = int(item[2]) if len(item) >= 3 else -1

        if closed_idx is not None and creation_idx >= 0 and closed_idx <= creation_idx:
            continue  # Cannot retest an FVG on the exact candle that created it

        can_use_prev = (
            prev_row is not None
            and (prev_idx is None or creation_idx < 0 or prev_idx > creation_idx)
        )

        # Avoid shallow outer-lip touches on wide FVGs: require >=35% pullback into zone equilibrium
        gap = max(0.0, high_b - low_b)
        pen_depth = (0.35 * gap) if gap >= min_pen_gap else 0.0

        if is_bullish:
            entry_ceil = high_b - pen_depth
            direct_touch = (
                closed_low <= entry_ceil
                and closed_low >= (low_b - max_wick_buf)
                and closed_close >= (low_b - close_tol)
            )
            two_bar_retest = (
                can_use_prev
                and prev_low <= entry_ceil
                and prev_low >= (low_b - max_wick_buf)
                and prev_close >= (low_b - close_tol)
                and closed_close >= low_b
                and closed_close >= closed_open
            )
            if direct_touch or two_bar_retest:
                return True, (low_b, high_b)
        else:
            entry_floor = low_b + pen_depth
            direct_touch = (
                closed_high >= entry_floor
                and closed_high <= (high_b + max_wick_buf)
                and closed_close <= (high_b + close_tol)
            )
            two_bar_retest = (
                can_use_prev
                and prev_high >= entry_floor
                and prev_high <= (high_b + max_wick_buf)
                and prev_close <= (high_b + close_tol)
                and closed_close <= high_b
                and closed_close <= closed_open
            )
            if direct_touch or two_bar_retest:
                return True, (low_b, high_b)
    return False, None
