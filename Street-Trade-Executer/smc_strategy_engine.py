import os
import numpy as np
import pandas as pd
import logging
from smc_indicators import detect_smc_zones, detect_market_structure, is_price_in_zones

logger = logging.getLogger("SMC_Strategy_Engine")

def evaluate_smc_strategy_signal(df_m15: pd.DataFrame, df_m5: pd.DataFrame = None, category: str = "forex", bypass_filters: bool = False):
    """
    Pure SMC/ICT Strategy Engine:
    
    1. MARKET STRUCTURE (BOS/CHoCH):
       - BUY: M15 Structure is BULLISH (Higher Highs / Higher Lows).
       - SELL: M15 Structure is BEARISH (Lower Highs / Lower Lows).

    2. UNMITIGATED LIQUIDITY ZONE RETEST:
       - BUY: Price is retesting an active Bullish Order Block (OB), FVG, or iFVG zone.
       - SELL: Price is retesting an active Bearish Order Block (OB), FVG, or iFVG zone.

    3. CANDLE ACTION CONFIRMATION:
       - BUY: Candle is Bullish (Close >= Open).
       - SELL: Candle is Bearish (Close <= Open).

    4. RISK-TO-REWARD RATIO (1:3.0 RRR):
       - Gold (XAUUSD): SL = $3.46 Cap ($97 Risk) | TP = 3.0 * SL_Distance ($10.38 Gold move).
       - Forex: SL = 19.4 pips | TP = 58.2 pips (1:3.0 RRR Target).
    """
    if df_m15 is None or len(df_m15) < 20 or 'close' not in df_m15.columns:
        return "NONE", None, None, 0.0, "Insufficient candle data for SMC"

    eval_df = df_m5 if (df_m5 is not None and len(df_m5) >= 10) else df_m15
    curr_row = eval_df.iloc[-1]

    price = float(curr_row['close'])
    open_price = float(curr_row['open'])

    # 1. Market Structure Detection (BOS / CHoCH)
    structure = detect_market_structure(df_m15)

    # 2. SMC Zone Detection (Unmitigated Order Blocks, FVGs, Breakers, iFVGs)
    zones = detect_smc_zones(df_m15)

    is_metals = (category == "metals" or "XAU" in str(df_m15.get('symbol', '')))

    # Check temporary test mode flag
    test_mode = bypass_filters or (os.getenv("TEMP_TEST_MODE", "False").lower() in ("true", "1", "yes"))

    # ── 1. LONG (BUY) ENTRY EVALUATION ──
    if structure == 'BULLISH' or (test_mode and structure != 'BEARISH'):
        in_bull_ob = is_price_in_zones(price, zones['bullish_ob'])
        in_bull_fvg = is_price_in_zones(price, zones['bullish_fvg'])
        in_bull_brk = is_price_in_zones(price, zones['bullish_breaker'])
        in_bull_ifvg = is_price_in_zones(price, zones['bullish_ifvg'])

        if test_mode or ((in_bull_ob or in_bull_fvg or in_bull_brk or in_bull_ifvg) and (price >= open_price)):
            sl_dist = 3.46 if is_metals else 0.00194
            sl_price = price - sl_dist
            tp_price = price + (3.0 * sl_dist)  # 1:3.0 RRR Target

            zone_type = "TEST_BYPASS" if test_mode else ("Order Block" if in_bull_ob else ("FVG" if in_bull_fvg else "Breaker/iFVG"))
            reason = f"🟢 SMC STRUCTURE BUY: Bullish BOS/CHoCH | Retest in {zone_type} Zone | 1:3.0 RRR TP"
            logger.info("================================================================================")
            logger.info(f"🟢 [PURE SMC BUY SIGNAL EXECUTED] 🚀")
            logger.info(f"🟢 Structure: M15 Bullish BOS/CHoCH 🟢")
            logger.info(f"🟢 Zone Retest: Active {zone_type} Zone @ Price {price:.5f} 🟢")
            logger.info(f"🟢 Target RRR Plan: 1:3.0 RRR (SL: {sl_price:.5f} | TP: {tp_price:.5f})")
            logger.info("================================================================================")
            return "BUY", tp_price, sl_price, sl_dist, reason

    # ── 2. SHORT (SELL) ENTRY EVALUATION ──
    elif structure == 'BEARISH' or (test_mode and structure == 'BEARISH'):
        in_bear_ob = is_price_in_zones(price, zones['bearish_ob'])
        in_bear_fvg = is_price_in_zones(price, zones['bearish_fvg'])
        in_bear_brk = is_price_in_zones(price, zones['bearish_breaker'])
        in_bear_ifvg = is_price_in_zones(price, zones['bearish_ifvg'])

        if test_mode or ((in_bear_ob or in_bear_fvg or in_bear_brk or in_bear_ifvg) and (price <= open_price)):
            sl_dist = 3.46 if is_metals else 0.00194
            sl_price = price + sl_dist
            tp_price = price - (3.0 * sl_dist)  # 1:3.0 RRR Target

            zone_type = "TEST_BYPASS" if test_mode else ("Order Block" if in_bear_ob else ("FVG" if in_bear_fvg else "Breaker/iFVG"))
            reason = f"🔴 SMC STRUCTURE SELL: Bearish BOS/CHoCH | Retest in {zone_type} Zone | 1:3.0 RRR TP"
            logger.info("================================================================================")
            logger.info(f"🔴 [PURE SMC SELL SIGNAL EXECUTED] 🚀")
            logger.info(f"🔴 Structure: M15 Bearish BOS/CHoCH 🔴")
            logger.info(f"🔴 Zone Retest: Active {zone_type} Zone @ Price {price:.5f} 🔴")
            logger.info(f"🔴 Target RRR Plan: 1:3.0 RRR (SL: {sl_price:.5f} | TP: {tp_price:.5f})")
            logger.info("================================================================================")
            return "SELL", tp_price, sl_price, sl_dist, reason

    candle_str = "Green Bullish 🟢" if price >= open_price else "Red Bearish 🔴"
    return "NONE", None, None, 0.0, f"Scanning SMC Structure: {structure} | Price: {price:.5f} | Candle: {candle_str}"
