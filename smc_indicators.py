import numpy as np
import pandas as pd

def get_swing_points(df, n_left=3, n_right=3, min_amplitude=0.0):
    """
    Returns lists of swing highs (price, index) and swing lows (price, index)
    using institutional fractal definitions with n_left and n_right candles (default 3x3 = 7 bars).
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


def detect_market_structure(df):
    """
    Institutional M15 Market Structure Bias with Structural Trend Memory:
    - In SMC/ICT, once a structure is established (Bullish: HH/HL or Bearish: LH/LL),
      the trend REMAINS ACTIVE until an opposite structural break occurs.
    - A temporary pullback or minor lower high inside an uptrend does NOT turn bias to 'NEUTRAL';
      it is a discount retracement for buy entries.
    - BULLISH: Trend remains Bullish until a candle closes below the confirmed structural Higher Low (Bearish MSS).
    - BEARISH: Trend remains Bearish until a candle closes above the confirmed structural Lower High (Bullish MSS).
    - NEUTRAL: Only returned if historical swing data is completely flat or undefined.
    """
    swing_highs, swing_lows = get_swing_points(df, n_left=2, n_right=2)

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return 'NEUTRAL'

    # Combine all confirmed swing events chronologically
    events = []
    for p, idx in swing_highs:
        events.append((idx, 'HIGH', p))
    for p, idx in swing_lows:
        events.append((idx, 'LOW', p))
    events.sort(key=lambda x: x[0])

    last_sh = None
    prev_sh = None
    last_sl = None
    prev_sl = None
    bias = 'NEUTRAL'

    for idx, kind, p in events:
        if kind == 'HIGH':
            prev_sh = last_sh
            last_sh = p
            if prev_sh is not None:
                if last_sh > prev_sh:
                    bias = 'BULLISH'
                elif last_sh < prev_sh and bias == 'BEARISH':
                    bias = 'BEARISH'
        elif kind == 'LOW':
            prev_sl = last_sl
            last_sl = p
            if prev_sl is not None:
                if last_sl < prev_sl:
                    bias = 'BEARISH'
                elif last_sl > prev_sl and bias == 'BULLISH':
                    bias = 'BULLISH'

    # Structural Invalidation Check against current closed candle
    curr_close = float(df['close'].iloc[-1])
    if bias == 'BULLISH' and last_sl is not None:
        if curr_close < last_sl:
            bias = 'BEARISH'
    elif bias == 'BEARISH' and last_sh is not None:
        if curr_close > last_sh:
            bias = 'BULLISH'

    # Fallback to direct swing comparison if chronological pass was inconclusive
    if bias == 'NEUTRAL':
        has_hh = swing_highs[-1][0] > swing_highs[-2][0]
        has_hl = swing_lows[-1][0] > swing_lows[-2][0]
        has_lh = swing_highs[-1][0] < swing_highs[-2][0]
        has_ll = swing_lows[-1][0] < swing_lows[-2][0]
        if has_hh or (has_hl and not has_ll):
            bias = 'BULLISH'
        elif has_ll or (has_lh and not has_hh):
            bias = 'BEARISH'

    return bias


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
    if df_m5 is None or len(df_m5) < 10:
        return (False, 0.0, 0.0, -1), (False, 0.0, 0.0, -1)

    # Detect if asset is Gold / Metals
    is_metals = False
    if 'symbol' in df_m5.columns and any(m in str(df_m5['symbol'].iloc[0]).upper() for m in ['XAU', 'GOLD', 'XAG', 'SILVER']):
        is_metals = True
    elif len(df_m5) > 0 and float(df_m5['close'].iloc[-1]) > 500:
        is_metals = True

    min_amp = 1.75 if is_metals else 0.00015
    swing_highs, swing_lows = get_swing_points(df_m5, n_left=3, n_right=3, min_amplitude=min_amp)
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        swing_highs, swing_lows = get_swing_points(df_m5, n_left=2, n_right=2, min_amplitude=min_amp)
    if not swing_highs or not swing_lows:
        return (False, 0.0, 0.0, -1), (False, 0.0, 0.0, -1)

    highs = df_m5['high'].values
    lows = df_m5['low'].values
    closes = df_m5['close'].values
    n = len(df_m5)

    sell_sweep = (False, 0.0, 0.0, -1)
    buy_sweep = (False, 0.0, 0.0, -1)

    min_structural_depth = 2.50 if is_metals else 0.0018
    min_penetration = 0.25 if is_metals else 0.00003

    # Check recent candles for a fresh liquidity sweep (last 14 candles / 70 mins window)
    # Search BACKWARDS (from newest candle to oldest) so we always capture the MOST RECENT active sweep
    lookback_start = max(0, n - 14)
    for i in range(n - 1, lookback_start - 1, -1):
        # 1. Sell-side sweep (BUY setup): Price wicks below recent structural swing low, but closes ABOVE it
        for sl_val, sl_idx in reversed(swing_lows):
            if i > sl_idx + 1:
                # Structural depth check: ensure the swing low was a real swing, not an internal micro-blip
                prior_peak = max(highs[max(0, sl_idx - 6):sl_idx + 1])
                if (prior_peak - sl_val) < min_structural_depth:
                    continue  # Ignore minor noise blip inside consolidation

                # Penetration check: must wick at least min_penetration beyond swing level
                if (sl_val - lows[i]) >= min_penetration and closes[i] >= sl_val:
                    # Breakdown guard: ensure price has NOT closed below this sweep low subsequently
                    subsequent_break = any(closes[k] < lows[i] for k in range(i + 1, n))
                    if not subsequent_break:
                        sell_sweep = (True, float(lows[i]), float(sl_val), i)
                        break
        if sell_sweep[0]:
            break

    for i in range(n - 1, lookback_start - 1, -1):
        # 2. Buy-side sweep (SELL setup): Price wicks above recent structural swing high, but closes BELOW it
        for sh_val, sh_idx in reversed(swing_highs):
            if i > sh_idx + 1:
                # Structural depth check: ensure the swing high was a real swing, not an internal micro-blip
                prior_trough = min(lows[max(0, sh_idx - 6):sh_idx + 1])
                if (sh_val - prior_trough) < min_structural_depth:
                    continue  # Ignore minor noise blip inside consolidation

                # Penetration check: must wick at least min_penetration beyond swing level
                if (highs[i] - sh_val) >= min_penetration and closes[i] <= sh_val:
                    # Breakout guard: ensure price has NOT closed above this sweep high subsequently
                    subsequent_break = any(closes[k] > highs[i] for k in range(i + 1, n))
                    if not subsequent_break:
                        buy_sweep = (True, float(highs[i]), float(sh_val), i)
                        break
        if buy_sweep[0]:
            break

    return sell_sweep, buy_sweep


def detect_choch_bos(df_m5, sweep_idx, is_bullish=True):
    """
    Step 3: Bullish / Bearish CHoCH (Change of Character) & BOS.
    
    - Bullish CHoCH: After sell-side sweep, M5 candle CLOSES above the last confirmed structural lower high formed PRIOR to the sweep.
    - Bearish CHoCH: After buy-side sweep, M5 candle CLOSES below the last confirmed structural higher low formed PRIOR to the sweep.
    Returns: (has_choch, choch_level, choch_candle_index)
    """
    if df_m5 is None or sweep_idx < 0 or sweep_idx >= len(df_m5):
        return False, 0.0, -1

    highs = df_m5['high'].values
    lows = df_m5['low'].values
    closes = df_m5['close'].values
    n = len(df_m5)

    swing_highs, swing_lows = get_swing_points(df_m5, n_left=2, n_right=2)

    if is_bullish:
        # Last confirmed swing high formed prior to sweep_idx
        prior_sh = [p for p, idx in swing_highs if idx < sweep_idx]
        if prior_sh:
            choch_lvl = prior_sh[-1]
        else:
            choch_lvl = max(highs[max(0, sweep_idx - 6):sweep_idx])
            
        # Check if any candle AFTER sweep_idx CLOSES above choch_lvl
        for j in range(sweep_idx + 1, n):
            if closes[j] > choch_lvl:
                return True, float(choch_lvl), j
    else:
        # Last confirmed swing low formed prior to sweep_idx
        prior_sl = [p for p, idx in swing_lows if idx < sweep_idx]
        if prior_sl:
            choch_lvl = prior_sl[-1]
        else:
            choch_lvl = min(lows[max(0, sweep_idx - 6):sweep_idx])
            
        # Check if any candle AFTER sweep_idx CLOSES below choch_lvl
        for j in range(sweep_idx + 1, n):
            if closes[j] < choch_lvl:
                return True, float(choch_lvl), j

    return False, 0.0, -1


def detect_order_blocks(df, min_disp=1.0, max_dist=18.0):
    """
    Detects Order Blocks (OB) and Breaker Blocks:
    - Bullish OB: Last down candle before strong upward displacement breaking structure.
    - Bearish OB: Last up candle before strong downward displacement breaking structure.
    - Breaker Blocks: Failed OBs swept and broken by price.
    Filters out micro-noise and limits to freshest structural zones.
    """
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


def detect_smc_zones(df, min_idx=0, sweep_low=None, sweep_high=None):
    """
    Step 4: Fair Value Gaps (3-Candle FVG), Order Blocks (OB), and Breaker Blocks.
    Captures the genuine Displacement Leg FVGs formed by the sweep-to-CHoCH impulse leg
    as well as post-CHoCH expansion FVGs.
    Filters micro-noise (< $1.00 on Gold) and distant dead zones (> $18.00).
    Properly detects true iFVGs instead of duplicating FVGs.
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

    # Institutional threshold to eliminate 20-30 cent spread/tick noise
    if last_price > 1000:
        min_gap = 1.00       # Gold / BTC: minimum $1.00 gap for real institutional imbalance
        max_dist = 18.00     # Reject dead zones > $18 away from current trading action
        min_ob_disp = 1.20
    elif last_price > 20:
        min_gap = 0.08       # Silver / Platinum
        max_dist = 2.00
        min_ob_disp = 0.10
    else:
        min_gap = 0.00035    # Forex (3.5 pips)
        max_dist = 0.0080
        min_ob_disp = 0.00040

    raw_bull_fvgs = []
    raw_bear_fvgs = []

    start_scan = max(2, min_idx if min_idx >= 0 else 0)
    for i in range(start_scan, n):
        gap_up = lows[i] - highs[i - 2]
        gap_down = lows[i - 2] - highs[i]
        if gap_up >= min_gap:
            # Anchor check: ensure bullish FVG is at or above sweep low if provided
            if sweep_low is None or highs[i - 2] >= (sweep_low - 0.50):
                raw_bull_fvgs.append((highs[i - 2], lows[i], i))
        elif gap_down >= min_gap:
            # Anchor check: ensure bearish FVG is at or below sweep high if provided
            if sweep_high is None or lows[i - 2] <= (sweep_high + 0.50):
                raw_bear_fvgs.append((highs[i], lows[i - 2], i))

    active_bull = []
    active_bear = []
    mitigated_bull_fvgs = []
    mitigated_bear_fvgs = []

    for low_b, high_b, idx in raw_bull_fvgs:
        mitigated = False
        for j in range(idx + 1, n):
            if closes[j] < low_b:
                mitigated = True
                break
        if not mitigated:
            if abs(((low_b + high_b) / 2) - last_price) <= max_dist:
                active_bull.append((float(low_b), float(high_b)))
        else:
            mitigated_bull_fvgs.append((float(low_b), float(high_b), idx))

    for low_b, high_b, idx in raw_bear_fvgs:
        mitigated = False
        for j in range(idx + 1, n):
            if closes[j] > high_b:
                mitigated = True
                break
        if not mitigated:
            if abs(((low_b + high_b) / 2) - last_price) <= max_dist:
                active_bear.append((float(low_b), float(high_b)))
        else:
            mitigated_bear_fvgs.append((float(low_b), float(high_b), idx))

    bull_ob, bear_ob, bull_breaker, bear_breaker = detect_order_blocks(df, min_disp=min_ob_disp, max_dist=max_dist)

    # Genuine Inversion FVG (iFVG) — NO DUPLICATION:
    # A prior mitigated FVG where price traded through and now flips support/resistance
    bullish_ifvg = []
    bearish_ifvg = []
    for low_b, high_b, idx in mitigated_bear_fvgs[-3:]:
        if closes[-1] > high_b and (closes[-1] - high_b) <= (max_dist * 0.5):
            bullish_ifvg.append((low_b, high_b))
    for low_b, high_b, idx in mitigated_bull_fvgs[-3:]:
        if closes[-1] < low_b and (low_b - closes[-1]) <= (max_dist * 0.5):
            bearish_ifvg.append((low_b, high_b))

    return {
        'bullish_fvg': active_bull[-2:],
        'bearish_fvg': active_bear[-2:],
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


def check_fvg_retest(closed_open, closed_high, closed_low, closed_close, fvg_zones, is_bullish=True, max_wick_buf=0.75):
    """
    Step 5: Rigorous FVG Retest Verification for SMC Scalping.
    Checks whether a confirmed closed candle validly retested an active FVG:
    - Bullish FVG [low_b, high_b]:
      1. Price reached down into the FVG (closed_low <= high_b)
      2. Price respected the structural support (closed_low >= low_b - max_wick_buf and closed_close >= low_b - 0.25)
    - Bearish FVG [low_b, high_b]:
      1. Price reached up into the FVG (closed_high >= low_b)
      2. Price respected the structural resistance (closed_high <= high_b + max_wick_buf and closed_close <= high_b + 0.25)
    Returns (is_retested, matched_fvg)
    """
    for low_b, high_b in fvg_zones:
        if is_bullish:
            if closed_low <= high_b and closed_low >= (low_b - max_wick_buf) and closed_close >= (low_b - 0.25):
                return True, (float(low_b), float(high_b))
        else:
            if closed_high >= low_b and closed_high <= (high_b + max_wick_buf) and closed_close <= (high_b + 0.25):
                return True, (float(low_b), float(high_b))
    return False, None
