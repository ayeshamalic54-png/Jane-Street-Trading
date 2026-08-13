import numpy as np
import pandas as pd

def detect_smc_zones(df):
    """
    Detects active (unmitigated) SMC zones from a pandas DataFrame of rates.
    df must have columns: ['open', 'high', 'low', 'close']
    Returns a dictionary of lists of (low_price, high_price) tuples.
    Zone types: bullish_ob, bearish_ob, bullish_fvg, bearish_fvg,
                bullish_breaker, bearish_breaker, bullish_ifvg, bearish_ifvg
    """
    if df is None or len(df) < 5:
        return {
            'bullish_ob': [], 'bearish_ob': [],
            'bullish_fvg': [], 'bearish_fvg': [],
            'bullish_breaker': [], 'bearish_breaker': [],
            'bullish_ifvg': [], 'bearish_ifvg': []
        }

    highs = df['high'].values
    lows = df['low'].values
    opens = df['open'].values
    closes = df['close'].values
    n = len(df)

    raw_bullish_obs = []
    raw_bearish_obs = []
    raw_bullish_fvgs = []
    raw_bearish_fvgs = []

    bullish_breakers = []
    bearish_breakers = []
    bullish_ifvgs = []
    bearish_ifvgs = []

    # 1. First Pass: Detect FVGs and potential Order Blocks
    for i in range(2, n):
        # --- Fair Value Gaps (FVG) ---
        # Bullish FVG: Gap between candle i-2 High and candle i Low
        if lows[i] > highs[i-2]:
            raw_bullish_fvgs.append([highs[i-2], lows[i], i])

        # Bearish FVG: Gap between candle i-2 Low and candle i High
        elif highs[i] < lows[i-2]:
            raw_bearish_fvgs.append([highs[i], lows[i-2], i])

        # --- Order Blocks (OB) ---
        # Bullish OB: last down candle before a strong up move
        if closes[i] > highs[i-1] and closes[i-1] < opens[i-1]:
            raw_bullish_obs.append([lows[i-1], highs[i-1], i-1])

        # Bearish OB: last up candle before a strong down move
        elif closes[i] < lows[i-1] and closes[i-1] > opens[i-1]:
            raw_bearish_obs.append([lows[i-1], highs[i-1], i-1])

    # 2. Check OB mitigation & Breaker conversion
    active_bullish_obs = []
    active_bearish_obs = []

    for ob in raw_bullish_obs:
        ob_low, ob_high, ob_idx = ob
        mitigated = False
        for j in range(ob_idx + 2, n):
            if closes[j] < ob_low:
                mitigated = True
                bearish_breakers.append([ob_low, ob_high, j])
                break
            elif lows[j] <= ob_low:
                mitigated = True
                break
        if not mitigated:
            active_bullish_obs.append((ob_low, ob_high))

    for ob in raw_bearish_obs:
        ob_low, ob_high, ob_idx = ob
        mitigated = False
        for j in range(ob_idx + 2, n):
            if closes[j] > ob_high:
                mitigated = True
                bullish_breakers.append([ob_low, ob_high, j])
                break
            elif highs[j] >= ob_high:
                mitigated = True
                break
        if not mitigated:
            active_bearish_obs.append((ob_low, ob_high))

    # 3. Check FVG mitigation & iFVG conversion
    active_bullish_fvgs = []
    active_bearish_fvgs = []

    for fvg in raw_bullish_fvgs:
        fvg_low, fvg_high, fvg_idx = fvg
        mitigated = False
        for j in range(fvg_idx + 1, n):
            if closes[j] < fvg_low:
                mitigated = True
                bearish_ifvgs.append([fvg_low, fvg_high, j])
                break
            elif lows[j] <= fvg_low:
                mitigated = True
                break
        if not mitigated:
            active_bullish_fvgs.append((fvg_low, fvg_high))

    for fvg in raw_bearish_fvgs:
        fvg_low, fvg_high, fvg_idx = fvg
        mitigated = False
        for j in range(fvg_idx + 1, n):
            if closes[j] > fvg_high:
                mitigated = True
                bullish_ifvgs.append([fvg_low, fvg_high, j])
                break
            elif highs[j] >= fvg_high:
                mitigated = True
                break
        if not mitigated:
            active_bearish_fvgs.append((fvg_low, fvg_high))

    # 4. Check Breakers for mitigation
    active_bullish_breakers = []
    active_bearish_breakers = []

    for brk in bullish_breakers:
        brk_low, brk_high, brk_idx = brk
        mitigated = False
        for j in range(brk_idx + 1, n):
            if lows[j] <= brk_low:
                mitigated = True
                break
        if not mitigated:
            active_bullish_breakers.append((brk_low, brk_high))

    for brk in bearish_breakers:
        brk_low, brk_high, brk_idx = brk
        mitigated = False
        for j in range(brk_idx + 1, n):
            if highs[j] >= brk_high:
                mitigated = True
                break
        if not mitigated:
            active_bearish_breakers.append((brk_low, brk_high))

    # 5. Check iFVGs for mitigation
    active_bullish_ifvgs = []
    active_bearish_ifvgs = []

    for ifvg in bullish_ifvgs:
        ifvg_low, ifvg_high, ifvg_idx = ifvg
        mitigated = False
        for j in range(ifvg_idx + 1, n):
            if lows[j] <= ifvg_low:
                mitigated = True
                break
        if not mitigated:
            active_bullish_ifvgs.append((ifvg_low, ifvg_high))

    for ifvg in bearish_ifvgs:
        ifvg_low, ifvg_high, ifvg_idx = ifvg
        mitigated = False
        for j in range(ifvg_idx + 1, n):
            if highs[j] >= ifvg_high:
                mitigated = True
                break
        if not mitigated:
            active_bearish_ifvgs.append((ifvg_low, ifvg_high))

    return {
        'bullish_ob': active_bullish_obs,
        'bearish_ob': active_bearish_obs,
        'bullish_fvg': active_bullish_fvgs,
        'bearish_fvg': active_bearish_fvgs,
        'bullish_breaker': active_bullish_breakers,
        'bearish_breaker': active_bearish_breakers,
        'bullish_ifvg': active_bullish_ifvgs,
        'bearish_ifvg': active_bearish_ifvgs
    }

def is_price_in_zones(price, zones):
    """
    Helper to check if a given price falls within any of the provided zones.
    zones: list of (low, high) tuples
    """
    for low, high in zones:
        if low <= price <= high:
            return True
    return False
