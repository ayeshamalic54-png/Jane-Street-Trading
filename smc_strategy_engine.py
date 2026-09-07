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

def evaluate_smc_strategy_signal(df_m15: pd.DataFrame, df_m5: pd.DataFrame = None, category: str = "forex", bypass_filters: bool = False, net_obi: float = 0.0, obi_enabled: bool = False):
    """
    Pure SMC/ICT Strategy Engine:
    
    1. 200 EMA MACRO TREND
    2. MARKET STRUCTURE (BOS/CHoCH)
    3. DYNAMIC ICT LIQUIDITY ZONE RETEST (OB / FVG / Breaker)
    4. CANDLE ACTION CONFIRMATION (Rejection Candle)
    5. ORDER BOOK IMBALANCE (OBI Liquidity Wall Guard)
    6. DYNAMIC ZONE-BASED SL & 1:3.0 RRR TP TARGET
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

    # Protection 1: 200 EMA Macro Trend
    p1_buy_pass = (price >= ema_200)
    p1_sell_pass = (price <= ema_200)

    # Protection 2: M15 Market Structure (BOS / CHoCH)
    p2_buy_pass = (structure == 'BULLISH')
    p2_sell_pass = (structure == 'BEARISH')

    # Protection 3: ICT Liquidity Zone Retest (OB / FVG / Breaker / iFVG)
    p3_buy_pass = in_bull_zone
    p3_sell_pass = in_bear_zone

    # Protection 4: Rejection Candle Confirmation
    p4_buy_pass = (price >= open_price)
    p4_sell_pass = (price <= open_price)

    # Protection 5: Order Book Imbalance (OBI Wall Protection)
    p5_buy_pass = (net_obi >= -0.20) if obi_enabled else True
    p5_sell_pass = (net_obi <= 0.20) if obi_enabled else True

    # ── 1. BUY SIGNAL EVALUATION (ALL 5 MUST PASS 🟢) ──
    if p1_buy_pass and p2_buy_pass and p3_buy_pass and p4_buy_pass and p5_buy_pass:
        # Dynamic ICT Order Block / FVG Zone-based SL & TP
        active_bull_zones = zones['bullish_ob'] + zones['bullish_fvg'] + zones['bullish_breaker'] + zones['bullish_ifvg']
        z_low, z_high = get_active_zone_bounds(price, active_bull_zones)
        
        if z_low is not None:
            buf = 0.75 if is_metals else 0.00040
            raw_sl_dist = max(0.0, price - (z_low - buf))
            max_cap = 3.46 if is_metals else 0.00194
            min_cap = 1.50 if is_metals else 0.00120  # Safe OB SL: $1.50 Gold / 12 pips Forex
            sl_dist = max(min_cap, min(raw_sl_dist, max_cap))
        else:
            sl_dist = 3.46 if is_metals else 0.00194

        sl_price = price - sl_dist
        tp_price = price + (3.0 * sl_dist)  # Dynamic 1:3.0 RRR Target

        zone_type = "ICT Order Block (OB)" if in_bull_ob else ("ICT Fair Value Gap (FVG)" if in_bull_fvg else ("ICT Breaker Block" if in_bull_brk else "ICT Inversion FVG (iFVG)"))
        reason = f"🟢 ALL 5 PROTECTIONS PASSED! DYNAMIC ICT BUY: 200 EMA + SMC BOS/CHoCH + {zone_type} Safe SL ({sl_dist:.2f} pips) | OBI: {net_obi:+.2f} | 1:3.0 RRR TP"
        logger.info("================================================================================")
        logger.info(f"🟢 [SAFE ICT OB/FVG BUY SIGNAL EXECUTED] 🚀")
        logger.info(f"🟢 Protection 1 (200 EMA): Price {price:.2f} >= 200 EMA {ema_200:.2f} 🟢")
        logger.info(f"🟢 Protection 2 (SMC Structure): M15 Bullish BOS/CHoCH 🟢")
        logger.info(f"🟢 Protection 3 (ICT Zone): Retesting active {zone_type} (Zone Low: {z_low}) 🟢")
        logger.info(f"🟢 Protection 4 (Rejection Candle): Green Candle 🟢")
        logger.info(f"🟢 Protection 5 (OBI Wall): Net OBI {net_obi:+.2f} >= -0.20 🟢")
        logger.info(f"🟢 Dynamic Safe SL @ {sl_price:.5f} ({sl_dist:.2f} pips below OB/FVG) | 1:3.0 RRR TP @ {tp_price:.5f} 🟢")
        logger.info("================================================================================")
        return "BUY", tp_price, sl_price, sl_dist, reason

    # ── 2. SELL SIGNAL EVALUATION (ALL 5 MUST PASS 🔴) ──
    if p1_sell_pass and p2_sell_pass and p3_sell_pass and p4_sell_pass and p5_sell_pass:
        # Dynamic ICT Order Block / FVG Zone-based SL & TP
        active_bear_zones = zones['bearish_ob'] + zones['bearish_fvg'] + zones['bearish_breaker'] + zones['bearish_ifvg']
        z_low, z_high = get_active_zone_bounds(price, active_bear_zones)
        
        if z_high is not None:
            buf = 0.75 if is_metals else 0.00040
            raw_sl_dist = max(0.0, (z_high + buf) - price)
            max_cap = 3.46 if is_metals else 0.00194
            min_cap = 1.50 if is_metals else 0.00120  # Safe OB SL: $1.50 Gold / 12 pips Forex
            sl_dist = max(min_cap, min(raw_sl_dist, max_cap))
        else:
            sl_dist = 3.46 if is_metals else 0.00194

        sl_price = price + sl_dist
        tp_price = price - (3.0 * sl_dist)  # Dynamic 1:3.0 RRR Target

        zone_type = "ICT Order Block (OB)" if in_bear_ob else ("ICT Fair Value Gap (FVG)" if in_bear_fvg else ("ICT Breaker Block" if in_bear_brk else "ICT Inversion FVG (iFVG)"))
        reason = f"🔴 ALL 5 PROTECTIONS PASSED! DYNAMIC ICT SELL: 200 EMA + SMC BOS/CHoCH + {zone_type} Safe SL ({sl_dist:.2f} pips) | OBI: {net_obi:+.2f} | 1:3.0 RRR TP"
        logger.info("================================================================================")
        logger.info(f"🔴 [SAFE ICT OB/FVG SELL SIGNAL EXECUTED] 🚀")
        logger.info(f"🔴 Protection 1 (200 EMA): Price {price:.2f} <= 200 EMA {ema_200:.2f} 🔴")
        logger.info(f"🔴 Protection 2 (SMC Structure): M15 Bearish BOS/CHoCH 🔴")
        logger.info(f"🔴 Protection 3 (ICT Zone): Retesting active {zone_type} (Zone High: {z_high}) 🔴")
        logger.info(f"🔴 Protection 4 (Rejection Candle): Red Candle 🔴")
        logger.info(f"🔴 Protection 5 (OBI Wall): Net OBI {net_obi:+.2f} <= +0.20 🔴")
        logger.info(f"🔴 Dynamic Safe SL @ {sl_price:.5f} ({sl_dist:.2f} pips above OB/FVG) | 1:3.0 RRR TP @ {tp_price:.5f} 🔴")
        logger.info("================================================================================")
        return "SELL", tp_price, sl_price, sl_dist, reason

    # ── 3. SCAN LOGIC & STATUS DISPLAY ──
    obi_str_buy = f"PASS 🟢 ({net_obi:+.2f})" if p5_buy_pass else f"FAIL 🔴 ({net_obi:+.2f} sell wall)"
    obi_str_sell = f"PASS 🔴 ({net_obi:+.2f})" if p5_sell_pass else f"FAIL 🟢 ({net_obi:+.2f} buy wall)"

    if p1_buy_pass or p2_buy_pass:
        p1_s = "PASS 🟢" if p1_buy_pass else "FAIL 🔴 (Price < 200 EMA)"
        p2_s = "PASS 🟢 (BULLISH)" if p2_buy_pass else "FAIL 🔴 (Structure BEARISH)"
        p3_s = "PASS 🟢" if p3_buy_pass else "FAIL 🔴 (No OB/FVG Retest)"
        p4_s = "PASS 🟢" if p4_buy_pass else "FAIL 🔴 (Waiting Green Candle)"
        scan_msg = f"Scanning BUY | P1(200 EMA): {p1_s} | P2(Structure): {p2_s} | P3(ICT Zone): {p3_s} | P4(Candle): {p4_s} | P5(OBI Wall): {obi_str_buy}"
    elif p1_sell_pass or p2_sell_pass:
        p1_s = "PASS 🔴" if p1_sell_pass else "FAIL 🟢 (Price > 200 EMA)"
        p2_s = "PASS 🔴 (BEARISH)" if p2_sell_pass else "FAIL 🟢 (Structure BULLISH)"
        p3_s = "PASS 🔴" if p3_sell_pass else "FAIL 🟢 (No OB/FVG Retest)"
        p4_s = "PASS 🔴" if p4_sell_pass else "FAIL 🟢 (Waiting Red Candle)"
        scan_msg = f"Scanning SELL | P1(200 EMA): {p1_s} | P2(Structure): {p2_s} | P3(ICT Zone): {p3_s} | P4(Candle): {p4_s} | P5(OBI Wall): {obi_str_sell}"
    else:
        scan_msg = f"Scanning SMC Structure: {structure} | Price: {price:.2f} | 200 EMA: {ema_200:.2f} | OBI: {net_obi:+.2f}"

    return "NONE", None, None, 0.0, scan_msg
