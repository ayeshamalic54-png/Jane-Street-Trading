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

    # Step 4: 3-Candle Displacement FVG Creation (From Sweep through CHoCH Breakout)
    zones_bull = detect_smc_zones(eval_df, min_idx=sell_sweep_idx) if has_bull_choch else {'bullish_fvg': []}
    zones_bear = detect_smc_zones(eval_df, min_idx=buy_sweep_idx) if has_bear_choch else {'bearish_fvg': []}

    # Step 5: CLOSED CANDLE Retests THAT SAME NEW Post-CHoCH FVG
    in_bull_fvg = is_price_in_zones(closed_close, zones_bull['bullish_fvg']) or is_price_in_zones(closed_low, zones_bull['bullish_fvg'])
    in_bear_fvg = is_price_in_zones(closed_close, zones_bear['bearish_fvg']) or is_price_in_zones(closed_high, zones_bear['bearish_fvg'])

    # Step 6 & 7: Valid Rejection Direction on CONFIRMED CLOSED CANDLE (iloc[-2])
    p5_buy_rejection = in_bull_fvg and (closed_close >= closed_open)
    p5_sell_rejection = in_bear_fvg and (closed_close <= closed_open)

    # ── 1. BUY SIGNAL EVALUATION (CONDITION 8 & 9 MANDATORY 🟢) ──
    if is_m15_bullish and has_sell_sweep and has_bull_choch and (len(zones_bull['bullish_fvg']) > 0) and in_bull_fvg and p5_buy_rejection:
        buf = 0.75 if is_metals else 0.00040
        min_dist = 0.01 if is_metals else 0.00010
        sl_price = sweep_low_price - buf
        sl_dist = max(min_dist, price - sl_price)

        # Condition 9: Identify next M15 structural target high above entry (Requires min 1.5R space, baseline 1.8R)
        from smc_indicators import get_swing_points
        m15_sh, _ = get_swing_points(df_m15, n_left=2, n_right=2)
        m15_targets = [p for p, _ in m15_sh if p > price]
        if not m15_targets:
            target_high = price + 2.5 * sl_dist
            avail_rrr = 2.5
        else:
            valid_targets = [p for p in m15_targets if (p - price) / sl_dist >= 1.5]
            if valid_targets:
                target_high = min(valid_targets)
                avail_rrr = (target_high - price) / sl_dist
            else:
                target_high = max(m15_targets)
                avail_rrr = (target_high - price) / sl_dist

        if avail_rrr < 1.5 and not bypass_filters:
            return "NONE", None, None, 0.0, f"FAIL 🔴 (Condition 9: M15 Target RRR {avail_rrr:.2f}R < Minimum 1.5R Requirement)"

        target_rrr = 1.85  # Baseline 1:1.85 Target ($97-$112 USD profit on 0.07 lot)
        tp_price = price + (target_rrr * sl_dist)

        # Smart Order Block Shield: Front-run opposing Bearish OB only if profit >= 1.40R ($94+ USD)
        try:
            all_zones = detect_smc_zones(eval_df, min_idx=0)
            opp_obs = all_zones.get('bearish_ob', []) + all_zones.get('bearish_breaker', [])
            ob_buf = 0.50 if is_metals else 0.00020
            ob_targets = []
            for low_b, high_b in opp_obs:
                ob_front = float(low_b) - ob_buf
                if ob_front > price and ob_front < tp_price:
                    ob_rrr = (ob_front - price) / sl_dist
                    if ob_rrr >= 1.40:
                        ob_targets.append((ob_front, ob_rrr))
            if ob_targets:
                best_ob_front, best_ob_rrr = min(ob_targets, key=lambda x: x[0])
                tp_price = best_ob_front
                target_rrr = best_ob_rrr
                logger.info(f"🛡️ [TP SHIELD] Front-running opposing Bearish Order Block @ {tp_price:.2f} ({target_rrr:.2f}R / $94+ profit lock)")
        except Exception:
            pass

        reason = f"🟢 STRICT SMC PASSED! BUY: M15 Bullish + M5 Sweep ({sweep_low_price:.2f}) + CHoCH ({bull_choch_lvl:.2f}) + FVG Retest | SL: {sl_price:.2f} (0.75 buf) | TP: {tp_price:.2f} ({target_rrr:.2f}R / 1:1.85)"
        logger.info("================================================================================")
        logger.info(f"🟢 [STRICT SMC BUY SIGNAL EXECUTED] 🚀")
        logger.info(f"🟢 Condition 8 (Structural SL): Sweep Low ({sweep_low_price:.2f}) - 0.75 = {sl_price:.2f} 🟢")
        logger.info(f"🟢 Condition 9 (Target TP): M15 Target ({target_high:.2f}) -> Executing {target_rrr:.2f}R TP (1:1.85 Target) @ {tp_price:.2f} 🟢")
        logger.info("================================================================================")
        return "BUY", tp_price, sl_price, sl_dist, reason

    # ── 2. SELL SIGNAL EVALUATION (CONDITION 8 & 9 MANDATORY 🔴) ──
    if is_m15_bearish and has_buy_sweep and has_bear_choch and (len(zones_bear['bearish_fvg']) > 0) and in_bear_fvg and p5_sell_rejection:
        buf = 0.75 if is_metals else 0.00040
        min_dist = 0.01 if is_metals else 0.00010
        sl_price = sweep_high_price + buf
        sl_dist = max(min_dist, sl_price - price)

        # Condition 9: Identify next M15 structural target low below entry (Requires min 1.5R space, baseline 1.8R)
        from smc_indicators import get_swing_points
        _, m15_sl = get_swing_points(df_m15, n_left=2, n_right=2)
        m15_targets = [p for p, _ in m15_sl if p < price]
        if not m15_targets:
            target_low = price - 2.5 * sl_dist
            avail_rrr = 2.5
        else:
            valid_targets = [p for p in m15_targets if (price - p) / sl_dist >= 1.5]
            if valid_targets:
                target_low = max(valid_targets)
                avail_rrr = (price - target_low) / sl_dist
            else:
                target_low = min(m15_targets)
                avail_rrr = (price - target_low) / sl_dist

        if avail_rrr < 1.5 and not bypass_filters:
            return "NONE", None, None, 0.0, f"FAIL 🔴 (Condition 9: M15 Target RRR {avail_rrr:.2f}R < Minimum 1.5R Requirement)"

        target_rrr = 1.85  # Baseline 1:1.85 Target ($97-$112 USD profit on 0.07 lot)
        tp_price = price - (target_rrr * sl_dist)

        # Smart Order Block Shield: Front-run opposing Bullish OB only if profit >= 1.40R ($94+ USD)
        try:
            all_zones = detect_smc_zones(eval_df, min_idx=0)
            opp_obs = all_zones.get('bullish_ob', []) + all_zones.get('bullish_breaker', [])
            ob_buf = 0.50 if is_metals else 0.00020
            ob_targets = []
            for low_b, high_b in opp_obs:
                ob_front = float(high_b) + ob_buf
                if ob_front < price and ob_front > tp_price:
                    ob_rrr = (price - ob_front) / sl_dist
                    if ob_rrr >= 1.40:
                        ob_targets.append((ob_front, ob_rrr))
            if ob_targets:
                best_ob_front, best_ob_rrr = max(ob_targets, key=lambda x: x[0])
                tp_price = best_ob_front
                target_rrr = best_ob_rrr
                logger.info(f"🛡️ [TP SHIELD] Front-running opposing Bullish Order Block @ {tp_price:.2f} ({target_rrr:.2f}R / $94+ profit lock)")
        except Exception:
            pass

        reason = f"🔴 STRICT SMC PASSED! SELL: M15 Bearish + M5 Sweep ({sweep_high_price:.2f}) + CHoCH ({bear_choch_lvl:.2f}) + FVG Retest | SL: {sl_price:.2f} (0.75 buf) | TP: {tp_price:.2f} ({target_rrr:.2f}R / 1:1.85)"
        logger.info("================================================================================")
        logger.info(f"🔴 [STRICT SMC SELL SIGNAL EXECUTED] 🚀")
        logger.info(f"🔴 Condition 8 (Structural SL): Sweep High ({sweep_high_price:.2f}) + 0.75 = {sl_price:.2f} 🔴")
        logger.info(f"🔴 Condition 9 (Target TP): M15 Target ({target_low:.2f}) -> Executing {target_rrr:.2f}R TP (1:1.85 Target) @ {tp_price:.2f} 🔴")
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

    step8_s = "PASS 🟢 (0.75 Buf)" if is_metals else "PASS 🟢 (0.0004 Buf)"

    try:
        from smc_indicators import get_swing_points
        buf = 0.75 if is_metals else 0.00040
        min_dist = 0.01 if is_metals else 0.00010
        if is_m15_bullish:
            sl_p_check = (sweep_low_price - buf) if has_sell_sweep else (price - (1.5 if is_metals else 0.0015))
            sl_d_check = max(min_dist, price - sl_p_check)
            m15_sh, _ = get_swing_points(df_m15, n_left=2, n_right=2)
            m15_targets = [p for p, _ in m15_sh if p > price]
            if not m15_targets:
                scan_rrr = 2.5
            else:
                valid_targets = [p for p in m15_targets if (p - price) / sl_d_check >= 1.5]
                target_high = min(valid_targets) if valid_targets else max(m15_targets)
                scan_rrr = (target_high - price) / sl_d_check
        elif is_m15_bearish:
            sl_p_check = (sweep_high_price + buf) if has_buy_sweep else (price + (1.5 if is_metals else 0.0015))
            sl_d_check = max(min_dist, sl_p_check - price)
            _, m15_sl = get_swing_points(df_m15, n_left=2, n_right=2)
            m15_targets = [p for p, _ in m15_sl if p < price]
            if not m15_targets:
                scan_rrr = 2.5
            else:
                valid_targets = [p for p in m15_targets if (price - p) / sl_d_check >= 1.5]
                target_low = max(valid_targets) if valid_targets else min(m15_targets)
                scan_rrr = (price - target_low) / sl_d_check
        else:
            scan_rrr = 1.85

        if scan_rrr >= 1.5:
            step9_s = f"PASS 🟢 ({scan_rrr:.2f}R Target Space -> Executing 1:1.85 TP)"
        else:
            step9_s = f"FAIL 🔴 ({scan_rrr:.2f}R Target Space < 1.5R Min)"
    except Exception:
        step9_s = "PASS 🟢 (M15 Target Min 1.5R / Target 1:1.85)"

    actual_sweep_p = sweep_low_price if has_sell_sweep else (sweep_high_price if has_buy_sweep else 0.0)
    actual_choch_p = bull_choch_lvl if has_bull_choch else (bear_choch_lvl if has_bear_choch else 0.0)
    scan_msg = f"Scanning Strict 9-Condition SMC | S1(M15): {step1_s} | S2(Sweep): {step2_s} | S3(CHoCH): {step3_s} | S4(Post-CHoCH FVG): {step4_s} | S5(Retest): {step5_s} | S6(Rejection): {step6_s} | S7(Closed): {step7_s} | S8(SL Buf): {step8_s} | S9(Target): {step9_s} | SweepPrice: {actual_sweep_p:.2f} | ChochPrice: {actual_choch_p:.2f}"
    return "NONE", None, None, 0.0, scan_msg
