import os
import numpy as np
import pandas as pd
import logging
from smc_indicators import detect_smc_zones, detect_market_structure, is_price_in_zones

logger = logging.getLogger("SMC_Strategy_Engine")

def get_active_zone_bounds(price: float, zone_list: list):
    """Returns (z_low, z_high) of the active ICT OB/FVG zone price is currently retesting."""
    if not zone_list:
        return None, None
    for (z_low, z_high) in zone_list:
        if z_low <= price <= z_high:
            return z_low, z_high
    return None, None

def evaluate_smc_strategy_signal(df_m15: pd.DataFrame, df_m5: pd.DataFrame = None, category: str = "forex", bypass_filters: bool = False):
    """
    Pure SMC/ICT Strategy Engine:
    
    1. 200 EMA MACRO TREND
    2. MARKET STRUCTURE (BOS/CHoCH)
    3. DYNAMIC ICT LIQUIDITY ZONE RETEST (OB / FVG / Breaker)
    4. CANDLE ACTION CONFIRMATION (Rejection Candle)
    5. DYNAMIC ZONE-BASED SL & 1:3.0 RRR TP TARGET
    """
    if df_m15 is None or len(df_m15) < 20 or 'close' not in df_m15.columns:
        return "NONE", None, None, 0.0, "Insufficient candle data for SMC"

    eval_df = df_m5 if (df_m5 is not None and len(df_m5) >= 10) else df_m15
    curr_row = eval_df.iloc[-1]

    price = float(curr_row['close'])
    open_price = float(curr_row['open'])

    # 1. 200 EMA Macro Trend
    ema_200 = float(curr_row['ema_200']) if 'ema_200' in curr_row else price
    is_ema_bullish = (price >= ema_200)
    is_ema_bearish = (price <= ema_200)

    # 2. Z-Score Oversold / Overbought Zone
    z_val = float(curr_row['vwap_zscore']) if 'vwap_zscore' in curr_row else 0.0

    # 3. Market Structure (BOS / CHoCH) & ICT Zones
    structure = detect_market_structure(df_m15)
    zones = detect_smc_zones(df_m15)

    in_bull_ob = is_price_in_zones(price, zones['bullish_ob'])
    in_bull_fvg = is_price_in_zones(price, zones['bullish_fvg'])
    in_bull_brk = is_price_in_zones(price, zones['bullish_breaker'])
    in_bull_ifvg = is_price_in_zones(price, zones['bullish_ifvg'])
    in_bull_zone = (in_bull_ob or in_bull_fvg or in_bull_brk or in_bull_ifvg)

    in_bear_ob = is_price_in_zones(price, zones['bearish_ob'])
    in_bear_fvg = is_price_in_zones(price, zones['bearish_fvg'])
    in_bear_brk = is_price_in_zones(price, zones['bearish_breaker'])
    in_bear_ifvg = is_price_in_zones(price, zones['bearish_ifvg'])
    in_bear_zone = (in_bear_ob or in_bear_fvg or in_bear_brk or in_bear_ifvg)

    is_metals = (category == "metals" or "XAU" in str(df_m15.get('symbol', '')))

    # ── 1. LONG (BUY) ENTRY EVALUATION (OPTIMAL CONFLUENCE) ──
    if structure == 'BULLISH' or is_ema_bullish:
        if structure == 'BEARISH':
            return "NONE", None, None, 0.0, f"Scanning BUY | Protection 2 Fail: M15 Structure is BEARISH 🔴"
        if not in_bull_zone:
            return "NONE", None, None, 0.0, f"Scanning BUY | Protection 3 Fail: No active ICT Bullish OB / FVG / Breaker zone retest"
        if price < open_price:
            return "NONE", None, None, 0.0, f"Scanning BUY | Protection 4 Fail: Waiting for Green Bullish Candle 🟢"

        # Dynamic ICT Order Block / FVG Zone-based SL & TP
        active_bull_zones = zones['bullish_ob'] + zones['bullish_fvg'] + zones['bullish_breaker'] + zones['bullish_ifvg']
        z_low, z_high = get_active_zone_bounds(price, active_bull_zones)
        
        if z_low is not None:
            buf = 0.30 if is_metals else 0.00015
            raw_sl_dist = max(0.0, price - (z_low - buf))
            max_cap = 3.46 if is_metals else 0.00194
            min_cap = 0.80 if is_metals else 0.00060  # Tight OB SL: $0.80 Gold / 6 pips Forex
            sl_dist = max(min_cap, min(raw_sl_dist, max_cap))
        else:
            sl_dist = 3.46 if is_metals else 0.00194

        sl_price = price - sl_dist
        tp_price = price + (3.0 * sl_dist)  # Dynamic 1:3.0 RRR Target

        zone_type = "ICT Order Block (OB)" if in_bull_ob else ("ICT Fair Value Gap (FVG)" if in_bull_fvg else ("ICT Breaker Block" if in_bull_brk else "ICT Inversion FVG (iFVG)"))
        reason = f"🟢 DYNAMIC ICT BUY: 200 EMA + SMC BOS/CHoCH + {zone_type} Tight SL ({sl_dist:.2f} pips) | 1:3.0 RRR TP"
        logger.info("================================================================================")
        logger.info(f"🟢 [TIGHT ICT OB/FVG BUY SIGNAL EXECUTED] 🚀")
        logger.info(f"🟢 Protection 1 (200 EMA): Price {price:.2f} >= 200 EMA {ema_200:.2f} 🟢")
        logger.info(f"🟢 Protection 2 (SMC Structure): M15 Bullish BOS/CHoCH 🟢")
        logger.info(f"🟢 Protection 3 (ICT Zone): Retesting active {zone_type} (Zone Low: {z_low}) 🟢")
        logger.info(f"🟢 Protection 4 (Tight Zone SL/TP): Tight SL @ {sl_price:.5f} ({sl_dist:.2f} pips below OB/FVG) | 1:3.0 RRR TP @ {tp_price:.5f} 🟢")
        logger.info("================================================================================")
        return "BUY", tp_price, sl_price, sl_dist, reason

    # ── 2. SHORT (SELL) ENTRY EVALUATION (OPTIMAL CONFLUENCE) ──
    elif structure == 'BEARISH' or is_ema_bearish:
        if structure == 'BULLISH':
            return "NONE", None, None, 0.0, f"Scanning SELL | Protection 2 Fail: M15 Structure is BULLISH 🟢"
        if not in_bear_zone:
            return "NONE", None, None, 0.0, f"Scanning SELL | Protection 3 Fail: No active ICT Bearish OB / FVG / Breaker zone retest"
        if price > open_price:
            return "NONE", None, None, 0.0, f"Scanning SELL | Protection 4 Fail: Waiting for Red Bearish Candle 🔴"

        # Dynamic ICT Order Block / FVG Zone-based SL & TP
        active_bear_zones = zones['bearish_ob'] + zones['bearish_fvg'] + zones['bearish_breaker'] + zones['bearish_ifvg']
        z_low, z_high = get_active_zone_bounds(price, active_bear_zones)
        
        if z_high is not None:
            buf = 0.30 if is_metals else 0.00015
            raw_sl_dist = max(0.0, (z_high + buf) - price)
            max_cap = 3.46 if is_metals else 0.00194
            min_cap = 0.80 if is_metals else 0.00060  # Tight OB SL: $0.80 Gold / 6 pips Forex
            sl_dist = max(min_cap, min(raw_sl_dist, max_cap))
        else:
            sl_dist = 3.46 if is_metals else 0.00194

        sl_price = price + sl_dist
        tp_price = price - (3.0 * sl_dist)  # Dynamic 1:3.0 RRR Target

        zone_type = "ICT Order Block (OB)" if in_bear_ob else ("ICT Fair Value Gap (FVG)" if in_bear_fvg else ("ICT Breaker Block" if in_bear_brk else "ICT Inversion FVG (iFVG)"))
        reason = f"🔴 DYNAMIC ICT SELL: 200 EMA + SMC BOS/CHoCH + {zone_type} Tight SL ({sl_dist:.2f} pips) | 1:3.0 RRR TP"
        logger.info("================================================================================")
        logger.info(f"🔴 [TIGHT ICT OB/FVG SELL SIGNAL EXECUTED] 🚀")
        logger.info(f"🔴 Protection 1 (200 EMA): Price {price:.2f} <= 200 EMA {ema_200:.2f} 🔴")
        logger.info(f"🔴 Protection 2 (SMC Structure): M15 Bearish BOS/CHoCH 🔴")
        logger.info(f"🔴 Protection 3 (ICT Zone): Retesting active {zone_type} (Zone High: {z_high}) 🔴")
        logger.info(f"🔴 Protection 4 (Tight Zone SL/TP): Tight SL @ {sl_price:.5f} ({sl_dist:.2f} pips above OB/FVG) | 1:3.0 RRR TP @ {tp_price:.5f} 🔴")
        logger.info("================================================================================")
        return "SELL", tp_price, sl_price, sl_dist, reason

    candle_str = "Green Bullish 🟢" if price >= open_price else "Red Bearish 🔴"
    return "NONE", None, None, 0.0, f"Scanning SMC Structure: {structure} | Price: {price:.5f} | Candle: {candle_str}"
