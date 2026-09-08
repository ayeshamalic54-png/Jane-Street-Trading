import os
import numpy as np
import pandas as pd
import logging
from smc_indicators import (
    detect_market_structure,
    detect_liquidity_sweep,
    detect_choch_bos,
    detect_smc_zones,
    is_price_in_zones
)

logger = logging.getLogger("SMC_Strategy_Engine")

def evaluate_smc_strategy_signal(
    df_m15: pd.DataFrame,
    df_m5: pd.DataFrame = None,
    category: str = "forex",
    bypass_filters: bool = False,
    net_obi: float = 0.0,
    obi_enabled: bool = False
):
    """
    Pure Rule-Based SMC / ICT 5-Step Strategy Engine:
    
    1. Step 1 — M15 Market Structure Bias (HH+HL = Bullish | LH+LL = Bearish)
    2. Step 2 — M5 Liquidity Sweep (Wick beyond swing level, close back inside)
    3. Step 3 — M5 CHoCH / BOS (Candle close beyond minor swing structure)
    4. Step 4 — M5 3-Candle FVG Creation & Price Retest
    5. Step 5 — FVG Retest Rejection Candle Close -> Entry
    """
    if df_m15 is None or len(df_m15) < 15 or 'close' not in df_m15.columns:
        return "NONE", None, None, 0.0, "Insufficient candle data for SMC"

    eval_df = df_m5 if (df_m5 is not None and len(df_m5) >= 10) else df_m15
    curr_row = eval_df.iloc[-1]
    prev_row = eval_df.iloc[-2] if len(eval_df) >= 2 else curr_row

    price = float(curr_row['close'])
    open_price = float(curr_row['open'])
    prev_close = float(prev_row['close'])
    prev_open = float(prev_row['open'])

    is_metals = (category == "metals" or "XAU" in str(df_m15.get('symbol', '')))

    # Step 1: M15 Market Structure Bias
    structure = detect_market_structure(df_m15)
    is_m15_bullish = (structure == 'BULLISH')
    is_m15_bearish = (structure == 'BEARISH')

    # Step 2: M5 Liquidity Sweep
    sell_sweep, buy_sweep = detect_liquidity_sweep(eval_df)
    has_sell_sweep, sweep_low_price, sl_swing_val, sell_sweep_idx = sell_sweep
    has_buy_sweep, sweep_high_price, sh_swing_val, buy_sweep_idx = buy_sweep

    # Step 3: M5 CHoCH / BOS Reversal
    has_bull_choch, bull_choch_lvl = detect_choch_bos(eval_df, sell_sweep_idx, is_bullish=True) if has_sell_sweep else (False, 0.0)
    has_bear_choch, bear_choch_lvl = detect_choch_bos(eval_df, buy_sweep_idx, is_bullish=False) if has_buy_sweep else (False, 0.0)

    # Step 4: 3-Candle FVG Creation & Price Retest
    zones = detect_smc_zones(eval_df)
    in_bull_fvg = is_price_in_zones(price, zones['bullish_fvg'])
    in_bear_fvg = is_price_in_zones(price, zones['bearish_fvg'])

    # Step 5: FVG Retest Candle Rejection
    p5_buy_rejection = (prev_close >= prev_open) and (price >= open_price)
    p5_sell_rejection = (prev_close <= prev_open) and (price <= open_price)

    # ── 1. BUY SIGNAL EVALUATION (ALL 5 STEPS MANDATORY 🟢) ──
    if is_m15_bullish and has_sell_sweep and has_bull_choch and in_bull_fvg and p5_buy_rejection:
        buf = 0.75 if is_metals else 0.00040
        raw_sl_dist = max(0.0, price - (sweep_low_price - buf))
        max_cap = 3.46 if is_metals else 0.00194
        min_cap = 1.50 if is_metals else 0.00120
        sl_dist = max(min_cap, min(raw_sl_dist, max_cap))

        sl_price = price - sl_dist
        tp_price = price + (2.5 * sl_dist)  # Min 1:2.0 - 1:2.5 RRR Target

        reason = f"🟢 ALL 5 SMC STEPS PASSED! BUY: M15 Bullish + M5 Sweep ({sweep_low_price:.2f}) + CHoCH ({bull_choch_lvl:.2f}) + FVG Retest | SL: {sl_price:.2f}"
        logger.info("================================================================================")
        logger.info(f"🟢 [PURE SMC 5-STEP BUY SIGNAL EXECUTED] 🚀")
        logger.info(f"🟢 Step 1 (M15 Structure): Bullish HH+HL 🟢")
        logger.info(f"🟢 Step 2 (M5 Sweep): Sell-side Sweep @ {sweep_low_price:.2f} 🟢")
        logger.info(f"🟢 Step 3 (M5 CHoCH): Bullish Close > {bull_choch_lvl:.2f} 🟢")
        logger.info(f"🟢 Step 4 (FVG Retest): Price inside Bullish FVG 🟢")
        logger.info(f"🟢 Step 5 (Rejection): Green Candle Rejection 🟢")
        logger.info(f"🟢 Dynamic SL @ {sl_price:.5f} | TP @ {tp_price:.5f} 🟢")
        logger.info("================================================================================")
        return "BUY", tp_price, sl_price, sl_dist, reason

    # ── 2. SELL SIGNAL EVALUATION (ALL 5 STEPS MANDATORY 🔴) ──
    if is_m15_bearish and has_buy_sweep and has_bear_choch and in_bear_fvg and p5_sell_rejection:
        buf = 0.75 if is_metals else 0.00040
        raw_sl_dist = max(0.0, (sweep_high_price + buf) - price)
        max_cap = 3.46 if is_metals else 0.00194
        min_cap = 1.50 if is_metals else 0.00120
        sl_dist = max(min_cap, min(raw_sl_dist, max_cap))

        sl_price = price + sl_dist
        tp_price = price - (2.5 * sl_dist)  # Min 1:2.0 - 1:2.5 RRR Target

        reason = f"🔴 ALL 5 SMC STEPS PASSED! SELL: M15 Bearish + M5 Sweep ({sweep_high_price:.2f}) + CHoCH ({bear_choch_lvl:.2f}) + FVG Retest | SL: {sl_price:.2f}"
        logger.info("================================================================================")
        logger.info(f"🔴 [PURE SMC 5-STEP SELL SIGNAL EXECUTED] 🚀")
        logger.info(f"🔴 Step 1 (M15 Structure): Bearish LH+LL 🔴")
        logger.info(f"🔴 Step 2 (M5 Sweep): Buy-side Sweep @ {sweep_high_price:.2f} 🔴")
        logger.info(f"🔴 Step 3 (M5 CHoCH): Bearish Close < {bear_choch_lvl:.2f} 🔴")
        logger.info(f"🔴 Step 4 (FVG Retest): Price inside Bearish FVG 🔴")
        logger.info(f"🔴 Step 5 (Rejection): Red Candle Rejection 🔴")
        logger.info(f"🔴 Dynamic SL @ {sl_price:.5f} | TP @ {tp_price:.5f} 🔴")
        logger.info("================================================================================")
        return "SELL", tp_price, sl_price, sl_dist, reason

    # ── 3. SCANNER LOGGING (DIRECTIONALLY MATCHED TO M15 BIAS) ──
    if is_m15_bullish:
        step1_s = "BULLISH 🟢"
        step2_s = "PASS 🟢 (Sell-Side Sweep)" if has_sell_sweep else "FAIL ⚪ (No Sell-Side Sweep)"
        step3_s = "PASS 🟢 (Bullish CHoCH)" if has_bull_choch else "FAIL ⚪ (No Bullish CHoCH)"
        step4_s = "PASS 🟢 (In Bullish FVG)" if in_bull_fvg else "FAIL ⚪ (No Bullish FVG)"
        step5_s = "PASS 🟢 (Green Rejection)" if p5_buy_rejection else "FAIL ⚪ (No Green Rejection)"
    elif is_m15_bearish:
        step1_s = "BEARISH 🔴"
        step2_s = "PASS 🔴 (Buy-Side Sweep)" if has_buy_sweep else "FAIL ⚪ (No Buy-Side Sweep)"
        step3_s = "PASS 🔴 (Bearish CHoCH)" if has_bear_choch else "FAIL ⚪ (No Bearish CHoCH)"
        step4_s = "PASS 🔴 (In Bearish FVG)" if in_bear_fvg else "FAIL ⚪ (No Bearish FVG)"
        step5_s = "PASS 🔴 (Red Rejection)" if p5_sell_rejection else "FAIL ⚪ (No Red Rejection)"
    else:
        step1_s = "NEUTRAL ⚪"
        step2_s = "FAIL ⚪ (M15 Structure Neutral)"
        step3_s = "FAIL ⚪ (M15 Structure Neutral)"
        step4_s = "FAIL ⚪ (M15 Structure Neutral)"
        step5_s = "FAIL ⚪ (M15 Structure Neutral)"

    scan_msg = f"Scanning Pure SMC | S1(M15 Bias): {step1_s} | S2(Sweep): {step2_s} | S3(CHoCH): {step3_s} | S4(FVG): {step4_s} | S5(Candle): {step5_s}"
    return "NONE", None, None, 0.0, scan_msg
