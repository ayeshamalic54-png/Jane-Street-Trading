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
    Pure Rule-Based SMC / ICT 7-Step Strict Strategy Engine:
    
    1. Step 1 — M15 Market Structure Bias (HH+HL = Bullish | LH+LL = Bearish)
    2. Step 2 — M5 Liquidity Sweep (Wick beyond swing level, close back inside)
    3. Step 3 — M5 CHoCH / BOS (Candle close beyond minor swing structure AFTER sweep)
    4. Step 4 — NEW Bullish/Bearish 3-Candle FVG Creation AFTER CHoCH
    5. Step 5 — Price Retests THAT SAME NEW Post-CHoCH FVG
    6. Step 6 — FVG Retest Rejection Candle (Price touches FVG & closes in rejection direction)
    7. Step 7 — Execution occurs ONLY after rejection candle is CLOSED
    """
    if df_m15 is None or len(df_m15) < 15 or 'close' not in df_m15.columns:
        return "NONE", None, None, 0.0, "Insufficient candle data for SMC"

    eval_df = df_m5 if (df_m5 is not None and len(df_m5) >= 10) else df_m15
    
    # Strictly evaluate completed closed candle (iloc[-2]) to satisfy Step 7 (Closed Confirmation)
    if len(eval_df) < 3:
        return "NONE", None, None, 0.0, "Insufficient candle history for closed candle confirmation"

    curr_live_row = eval_df.iloc[-1]
    closed_row = eval_df.iloc[-2]  # LAST CONFIRMED CLOSED CANDLE

    price = float(curr_live_row['close'])
    closed_close = float(closed_row['close'])
    closed_open = float(closed_row['open'])
    closed_low = float(closed_row['low'])
    closed_high = float(closed_row['high'])

    is_metals = (category == "metals" or "XAU" in str(df_m15.get('symbol', '')))

    # Step 1: M15 Market Structure Bias
    structure = detect_market_structure(df_m15)
    is_m15_bullish = (structure == 'BULLISH')
    is_m15_bearish = (structure == 'BEARISH')

    # Step 2: M5 Liquidity Sweep
    sell_sweep, buy_sweep = detect_liquidity_sweep(eval_df)
    has_sell_sweep, sweep_low_price, sl_swing_val, sell_sweep_idx = sell_sweep
    has_buy_sweep, sweep_high_price, sh_swing_val, buy_sweep_idx = buy_sweep

    # Step 3: M5 CHoCH / BOS Reversal (MUST BE AFTER SWEEP)
    has_bull_choch, bull_choch_lvl, bull_choch_idx = detect_choch_bos(eval_df, sell_sweep_idx, is_bullish=True) if has_sell_sweep else (False, 0.0, -1)
    has_bear_choch, bear_choch_lvl, bear_choch_idx = detect_choch_bos(eval_df, buy_sweep_idx, is_bullish=False) if has_buy_sweep else (False, 0.0, -1)

    # Step 4: 3-Candle FVG Creation STRICTLY AFTER CHoCH
    zones_bull = detect_smc_zones(eval_df, min_idx=bull_choch_idx) if has_bull_choch else {'bullish_fvg': []}
    zones_bear = detect_smc_zones(eval_df, min_idx=bear_choch_idx) if has_bear_choch else {'bearish_fvg': []}

    # Step 5: CLOSED CANDLE Retests THAT SAME NEW Post-CHoCH FVG
    in_bull_fvg = is_price_in_zones(closed_close, zones_bull['bullish_fvg']) or is_price_in_zones(closed_low, zones_bull['bullish_fvg'])
    in_bear_fvg = is_price_in_zones(closed_close, zones_bear['bearish_fvg']) or is_price_in_zones(closed_high, zones_bear['bearish_fvg'])

    # Step 6 & 7: Valid Rejection Direction on CONFIRMED CLOSED CANDLE (iloc[-2])
    p5_buy_rejection = in_bull_fvg and (closed_close >= closed_open)
    p5_sell_rejection = in_bear_fvg and (closed_close <= closed_open)

    # ── 1. BUY SIGNAL EVALUATION (ALL 7 STEPS MANDATORY 🟢) ──
    if is_m15_bullish and has_sell_sweep and has_bull_choch and (len(zones_bull['bullish_fvg']) > 0) and in_bull_fvg and p5_buy_rejection:
        buf = 1.75 if is_metals else 0.00040
        raw_sl_dist = max(0.0, price - (sweep_low_price - buf))
        max_cap = 10.00 if is_metals else 0.00194
        min_cap = 2.00 if is_metals else 0.00120
        sl_dist = max(min_cap, min(raw_sl_dist, max_cap))

        sl_price = price - sl_dist
        tp_price = price + (1.8 * sl_dist)  # 1:1.8 RRR Target ($91.00 USD Profit Target)

        reason = f"🟢 STRICT 7-STEP SMC PASSED! BUY: M15 Bullish + M5 Sweep ({sweep_low_price:.2f}) + CHoCH ({bull_choch_lvl:.2f}) + Post-CHoCH FVG Retest Rejection | SL: {sl_price:.2f}"
        logger.info("================================================================================")
        logger.info(f"🟢 [STRICT SMC 7-STEP BUY SIGNAL EXECUTED] 🚀")
        logger.info(f"🟢 Step 1 (M15 Structure): Bullish HH+HL 🟢")
        logger.info(f"🟢 Step 2 (M5 Sweep): Sell-side Sweep @ {sweep_low_price:.2f} 🟢")
        logger.info(f"🟢 Step 3 (M5 CHoCH): Bullish Close > {bull_choch_lvl:.2f} 🟢")
        logger.info(f"🟢 Step 4 (Post-CHoCH FVG): New FVG Created 🟢")
        logger.info(f"🟢 Step 5 (FVG Retest): Price retested Post-CHoCH FVG 🟢")
        logger.info(f"🟢 Step 6 (Rejection Candle): Closed Green Rejection 🟢")
        logger.info(f"🟢 Step 7 (Closed Confirmation): Candle Closed -> BUY Order Sent 🟢")
        logger.info(f"🟢 Dynamic SL @ {sl_price:.5f} | TP @ {tp_price:.5f} 🟢")
        logger.info("================================================================================")
        return "BUY", tp_price, sl_price, sl_dist, reason

    # ── 2. SELL SIGNAL EVALUATION (ALL 7 STEPS MANDATORY 🔴) ──
    if is_m15_bearish and has_buy_sweep and has_bear_choch and (len(zones_bear['bearish_fvg']) > 0) and in_bear_fvg and p5_sell_rejection:
        buf = 1.75 if is_metals else 0.00040
        raw_sl_dist = max(0.0, (sweep_high_price + buf) - price)
        max_cap = 10.00 if is_metals else 0.00194
        min_cap = 2.00 if is_metals else 0.00120
        sl_dist = max(min_cap, min(raw_sl_dist, max_cap))

        sl_price = price + sl_dist
        tp_price = price - (1.8 * sl_dist)  # 1:1.8 RRR Target ($91.00 USD Profit Target)

        reason = f"🔴 STRICT 7-STEP SMC PASSED! SELL: M15 Bearish + M5 Sweep ({sweep_high_price:.2f}) + CHoCH ({bear_choch_lvl:.2f}) + Post-CHoCH FVG Retest Rejection | SL: {sl_price:.2f}"
        logger.info("================================================================================")
        logger.info(f"🔴 [STRICT SMC 7-STEP SELL SIGNAL EXECUTED] 🚀")
        logger.info(f"🔴 Step 1 (M15 Structure): Bearish LH+LL 🔴")
        logger.info(f"🔴 Step 2 (M5 Sweep): Buy-side Sweep @ {sweep_high_price:.2f} 🔴")
        logger.info(f"🔴 Step 3 (M5 CHoCH): Bearish Close < {bear_choch_lvl:.2f} 🔴")
        logger.info(f"🔴 Step 4 (Post-CHoCH FVG): New FVG Created 🔴")
        logger.info(f"🔴 Step 5 (FVG Retest): Price retested Post-CHoCH FVG 🔴")
        logger.info(f"🔴 Step 6 (Rejection Candle): Closed Red Rejection 🔴")
        logger.info(f"🔴 Step 7 (Closed Confirmation): Candle Closed -> SELL Order Sent 🔴")
        logger.info(f"🔴 Dynamic SL @ {sl_price:.5f} | TP @ {tp_price:.5f} 🔴")
        logger.info("================================================================================")
        return "SELL", tp_price, sl_price, sl_dist, reason

    # ── 3. SCANNER LOGGING (ALL 7 STEPS INDIVIDUALLY DISPLAYED) ──
    if is_m15_bullish:
        step1_s = "BULLISH 🟢"
        step2_s = "PASS 🟢 (Sell-Side Sweep)" if has_sell_sweep else "FAIL ⚪ (No Sell-Side Sweep)"
        step3_s = "PASS 🟢 (Bullish CHoCH)" if has_bull_choch else "FAIL ⚪ (No Bullish CHoCH)"
        step4_s = "PASS 🟢 (Post-CHoCH FVG)" if (len(zones_bull['bullish_fvg']) > 0) else "FAIL ⚪ (No Post-CHoCH FVG)"
        step5_s = "PASS 🟢 (Retested FVG)" if in_bull_fvg else "FAIL ⚪ (No Retest)"
        step6_s = "PASS 🟢 (Green Rejection)" if p5_buy_rejection else "FAIL ⚪ (No Rejection)"
        step7_s = "PASS 🟢 (Candle Closed)" if p5_buy_rejection else "FAIL ⚪ (Waiting Candle Close)"
    elif is_m15_bearish:
        step1_s = "BEARISH 🔴"
        step2_s = "PASS 🔴 (Buy-Side Sweep)" if has_buy_sweep else "FAIL ⚪ (No Buy-Side Sweep)"
        step3_s = "PASS 🔴 (Bearish CHoCH)" if has_bear_choch else "FAIL ⚪ (No Bearish CHoCH)"
        step4_s = "PASS 🔴 (Post-CHoCH FVG)" if (len(zones_bear['bearish_fvg']) > 0) else "FAIL ⚪ (No Post-CHoCH FVG)"
        step5_s = "PASS 🔴 (Retested FVG)" if in_bear_fvg else "FAIL ⚪ (No Retest)"
        step6_s = "PASS 🔴 (Red Rejection)" if p5_sell_rejection else "FAIL ⚪ (No Rejection)"
        step7_s = "PASS 🔴 (Candle Closed)" if p5_sell_rejection else "FAIL ⚪ (Waiting Candle Close)"
    else:
        step1_s = "NEUTRAL ⚪"
        step2_s = "FAIL ⚪ (M15 Structure Neutral)"
        step3_s = "FAIL ⚪ (M15 Structure Neutral)"
        step4_s = "FAIL ⚪ (M15 Structure Neutral)"
        step5_s = "FAIL ⚪ (M15 Structure Neutral)"
        step6_s = "FAIL ⚪ (M15 Structure Neutral)"
        step7_s = "FAIL ⚪ (M15 Structure Neutral)"

    scan_msg = f"Scanning Strict 7-Step SMC | S1(M15): {step1_s} | S2(Sweep): {step2_s} | S3(CHoCH): {step3_s} | S4(Post-CHoCH FVG): {step4_s} | S5(Retest): {step5_s} | S6(Rejection): {step6_s} | S7(Closed): {step7_s}"
    return "NONE", None, None, 0.0, scan_msg
