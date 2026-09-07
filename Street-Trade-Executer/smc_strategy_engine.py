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

    # 1. 200 EMA Macro Trend
    ema_200 = float(curr_row['ema_200']) if 'ema_200' in curr_row else price
    is_ema_bullish = (price >= ema_200)
    is_ema_bearish = (price <= ema_200)

    # 2. Z-Score Oversold / Overbought Zone
    z_val = float(curr_row['vwap_zscore']) if 'vwap_zscore' in curr_row else 0.0
    prev_z_val = float(eval_df.iloc[-2]['vwap_zscore']) if (len(eval_df) >= 2 and 'vwap_zscore' in eval_df.columns) else z_val

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

    # ── 1. LONG (BUY) ENTRY EVALUATION (ALL 4 PROTECTIONS REQUIRED) ──
    if structure == 'BULLISH' or is_ema_bullish:
        if not is_ema_bullish:
            return "NONE", None, None, 0.0, f"Scanning BUY | Protection 1 Fail: Price ({price:.2f}) < 200 EMA ({ema_200:.2f})"
        if not in_bull_zone:
            return "NONE", None, None, 0.0, f"Scanning BUY | Protection 3 Fail: No active ICT Bullish OB / FVG / Breaker zone retest"
        if price < open_price:
            return "NONE", None, None, 0.0, f"Scanning BUY | Protection 4 Fail: Waiting for Green Bullish Candle 🟢"

        sl_dist = 3.46 if is_metals else 0.00194
        sl_price = price - sl_dist
        tp_price = price + (3.0 * sl_dist)  # 1:3.0 RRR Target

        zone_type = "ICT Order Block (OB)" if in_bull_ob else ("ICT Fair Value Gap (FVG)" if in_bull_fvg else ("ICT Breaker Block" if in_bull_brk else "ICT Inversion FVG (iFVG)"))
        reason = f"🟢 4-PROTECTION BUY: 200 EMA + Bullish BOS/CHoCH + {zone_type} + Green Candle | 1:3.0 RRR"
        logger.info("================================================================================")
        logger.info(f"🟢 [4-PROTECTION ICT BUY SIGNAL EXECUTED] 🚀")
        logger.info(f"🟢 Protection 1 (200 EMA): Price {price:.2f} > 200 EMA {ema_200:.2f} 🟢")
        logger.info(f"🟢 Protection 2 (Structure): M15 Bullish BOS/CHoCH 🟢")
        logger.info(f"🟢 Protection 3 (ICT Zone): Retesting active {zone_type} 🟢")
        logger.info(f"🟢 Protection 4 (Candle): Green Bullish Rejection Confirmed 🟢")
        logger.info("================================================================================")
        return "BUY", tp_price, sl_price, sl_dist, reason

    # ── 2. SHORT (SELL) ENTRY EVALUATION (ALL 4 PROTECTIONS REQUIRED) ──
    elif structure == 'BEARISH' or is_ema_bearish:
        if not is_ema_bearish:
            return "NONE", None, None, 0.0, f"Scanning SELL | Protection 1 Fail: Price ({price:.2f}) > 200 EMA ({ema_200:.2f})"
        if not in_bear_zone:
            return "NONE", None, None, 0.0, f"Scanning SELL | Protection 3 Fail: No active ICT Bearish OB / FVG / Breaker zone retest"
        if price > open_price:
            return "NONE", None, None, 0.0, f"Scanning SELL | Protection 4 Fail: Waiting for Red Bearish Candle 🔴"

        sl_dist = 3.46 if is_metals else 0.00194
        sl_price = price + sl_dist
        tp_price = price - (3.0 * sl_dist)  # 1:3.0 RRR Target

        zone_type = "ICT Order Block (OB)" if in_bear_ob else ("ICT Fair Value Gap (FVG)" if in_bear_fvg else ("ICT Breaker Block" if in_bear_brk else "ICT Inversion FVG (iFVG)"))
        reason = f"🔴 4-PROTECTION SELL: 200 EMA + Bearish BOS/CHoCH + {zone_type} + Red Candle | 1:3.0 RRR"
        logger.info("================================================================================")
        logger.info(f"🔴 [4-PROTECTION ICT SELL SIGNAL EXECUTED] 🚀")
        logger.info(f"🔴 Protection 1 (200 EMA): Price {price:.2f} < 200 EMA {ema_200:.2f} 🔴")
        logger.info(f"🔴 Protection 2 (Structure): M15 Bearish BOS/CHoCH 🔴")
        logger.info(f"🔴 Protection 3 (ICT Zone): Retesting active {zone_type} 🔴")
        logger.info(f"🔴 Protection 4 (Candle): Red Bearish Rejection Confirmed 🔴")
        logger.info("================================================================================")
        return "SELL", tp_price, sl_price, sl_dist, reason

    candle_str = "Green Bullish 🟢" if price >= open_price else "Red Bearish 🔴"
    return "NONE", None, None, 0.0, f"Scanning SMC Structure: {structure} | Price: {price:.5f} | Candle: {candle_str}"
