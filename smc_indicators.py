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

def detect_market_structure(df):
    """
    Detects Market Structure (BOS - Break of Structure & CHoCH - Change of Character)
    Returns: 'BULLISH', 'BEARISH', or 'NEUTRAL'
    """
    if df is None or len(df) < 15:
        return 'NEUTRAL'

    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    n = len(df)

    swing_highs = []
    swing_lows = []

    for i in range(2, n - 2):
        if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
            swing_highs.append((highs[i], i))
        if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
            swing_lows.append((lows[i], i))

    if not swing_highs or not swing_lows:
        return 'NEUTRAL'

    last_close = closes[-1]
    recent_high = max(sh[0] for sh in swing_highs[-3:])
    recent_low = min(sl[0] for sl in swing_lows[-3:])

    # 1. Break of Structure (BOS) / CHoCH
    if last_close > recent_high:
        return 'BULLISH'
    if last_close < recent_low:
        return 'BEARISH'

    # 2. Trend direction evaluation based on Swing Highs & Swing Lows
    has_higher_highs = len(swing_highs) >= 2 and swing_highs[-1][0] > swing_highs[-2][0]
    has_higher_lows = len(swing_lows) >= 2 and swing_lows[-1][0] > swing_lows[-2][0]
    
    has_lower_highs = len(swing_highs) >= 2 and swing_highs[-1][0] < swing_highs[-2][0]
    has_lower_lows = len(swing_lows) >= 2 and swing_lows[-1][0] < swing_lows[-2][0]

    if has_lower_lows or has_lower_highs:
        if not (has_higher_highs and has_higher_lows):
            return 'BEARISH'

    if has_higher_highs and has_higher_lows:
        return 'BULLISH'

    # Compare position of peak high in window
    max_high_idx = max(range(len(highs[-30:])), key=lambda k: highs[-30:][k])
    if max_high_idx < 15:  # Peak high occurred in earlier half -> Downtrend
        return 'BEARISH'
    
    return 'NEUTRAL'

def detect_asian_range(df):
    """
    Calculates Asian Session High and Low range (00:00 - 08:00 UTC).
    Returns (asian_high, asian_low, asian_swept_high, asian_swept_low)
    """
    if df is None or len(df) < 10 or 'time' not in df.columns:
        return None, None, False, False

    df_copy = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df_copy['time']):
        df_copy['time'] = pd.to_datetime(df_copy['time'])

    today_date = df_copy['time'].iloc[-1].date()
    asian_bars = df_copy[(df_copy['time'].dt.date == today_date) & (df_copy['time'].dt.hour >= 0) & (df_copy['time'].dt.hour < 8)]

    if asian_bars.empty:
        return None, None, False, False

    asian_high = float(asian_bars['high'].max())
    asian_low = float(asian_bars['low'].min())

    post_asian_bars = df_copy[(df_copy['time'].dt.date == today_date) & (df_copy['time'].dt.hour >= 8)]
    if post_asian_bars.empty:
        return asian_high, asian_low, False, False

    latest_high = float(post_asian_bars['high'].max())
    latest_low = float(post_asian_bars['low'].min())

    swept_high = latest_high > asian_high
    swept_low = latest_low < asian_low

    return asian_high, asian_low, swept_high, swept_low

def is_price_in_zones(price, zones):
    """
    Helper to check if a given price falls within any of the provided zones.
    zones: list of (low, high) tuples
    """
    for low, high in zones:
        if low <= price <= high:
            return True
    return False
