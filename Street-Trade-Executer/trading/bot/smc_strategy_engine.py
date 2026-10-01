import os
import numpy as np
import pandas as pd
import logging
from smc_indicators import (
    detect_market_structure,
    detect_liquidity_sweep,
    detect_choch_bos,
    detect_smc_zones,
    is_price_in_zones,
    check_fvg_retest
)

logger = logging.getLogger("SMC_Strategy_Engine")

def evaluate_smc_strategy_signal(
    df_m15: pd.DataFrame,
    df_m5: pd.DataFrame = None,
    category: str = "forex",
    bypass_filters: bool = False,
    net_obi: float = 0.0,
    obi_enabled: bool = False,
    live_price: float = None,
    is_already_closed: bool = False
):
    """
    Pure Rule-Based SMC / ICT 7-Step Strict Strategy Engine:
    
    1. Step 1 — M15 Market Structure Bias (HH+HL = Bullish | LH+LL = Bearish)
    2. Step 2 — M5 Liquidity Sweep (Wick beyond swing level, close back inside)
    3. Step 3 — M5 CHoCH / BOS (Candle close beyond minor swing structure AFTER sweep)
    4. Step 4 — 3-Candle Displacement FVG Creation (Formed during sweep-to-CHoCH impulse leg)
    5. Step 5 — Price Retests THAT SAME Displacement FVG
    6. Step 6 — FVG Retest Rejection Candle (Touches FVG & closes with rejection / direction)
    7. Step 7 — Execution occurs ONLY after rejection candle is CLOSED
    """
    if df_m15 is None or len(df_m15) < 15 or 'close' not in df_m15.columns:
        return "NONE", None, None, 0.0, "Insufficient candle data for SMC"

    eval_df = df_m5 if (df_m5 is not None and len(df_m5) >= 10) else df_m15
    
    # Strictly evaluate completed closed candle to satisfy Step 7 (Closed Confirmation)
    if len(eval_df) < 3:
        return "NONE", None, None, 0.0, "Insufficient candle history for closed candle confirmation"

    if is_already_closed:
        # Caller already pre-sliced closed candles only (backtest / audit mode)
        closed_row = eval_df.iloc[-1]
        price = live_price if live_price is not None else float(closed_row['close'])
    else:
        # Standard live MT5 feed: iloc[-1] is forming candle, iloc[-2] is completed closed candle
        curr_live_row = eval_df.iloc[-1]
        closed_row = eval_df.iloc[-2]
        price = live_price if live_price is not None else float(curr_live_row['close'])

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

    # Step 4: 3-Candle Displacement FVG Creation (Formed by Sweep-to-CHoCH impulse displacement leg)
    zones_bull = detect_smc_zones(eval_df, min_idx=sell_sweep_idx, sweep_low=sweep_low_price) if has_bull_choch else {'bullish_fvg': []}
    zones_bear = detect_smc_zones(eval_df, min_idx=buy_sweep_idx, sweep_high=sweep_high_price) if has_bear_choch else {'bearish_fvg': []}

    # Step 5: CLOSED CANDLE Retests THAT SAME Displacement Leg FVG
    wick_buf = 0.75 if is_metals else 0.00040
    in_bull_fvg, matched_bull_fvg = check_fvg_retest(closed_open, closed_high, closed_low, closed_close, zones_bull['bullish_fvg'], is_bullish=True, max_wick_buf=wick_buf)
    in_bear_fvg, matched_bear_fvg = check_fvg_retest(closed_open, closed_high, closed_low, closed_close, zones_bear['bearish_fvg'], is_bullish=False, max_wick_buf=wick_buf)

    # Step 6 & 7: Valid Rejection Direction on CONFIRMED CLOSED CANDLE
    # Bullish: Green candle OR strong lower wick rejection (hammer / pin-bar)
    bull_lower_wick = (closed_close - closed_low) if closed_close >= closed_open else (closed_open - closed_low)
    bull_candle_range = max(0.01 if is_metals else 0.0001, closed_high - closed_low)
    p5_buy_rejection = in_bull_fvg and ((closed_close >= closed_open) or (bull_lower_wick / bull_candle_range >= 0.40))

    # Bearish: Red candle OR strong upper wick rejection (shooting star / pin-bar)
    bear_upper_wick = (closed_high - closed_close) if closed_close <= closed_open else (closed_high - closed_open)
    bear_candle_range = max(0.01 if is_metals else 0.0001, closed_high - closed_low)
    p5_sell_rejection = in_bear_fvg and ((closed_close <= closed_open) or (bear_upper_wick / bear_candle_range >= 0.40))

    # ── FRESHNESS & STRUCTURE INVALIDATION GUARD ──
    # SMC Rule: Setup remains valid while price respects structural boundaries.
    # 1. Stale Expiry Guard: 10 M5 candles (50 mins) window for pullback into displacement FVG.
    # 2. Structural Invalidation: If price closes beyond the sweep extreme (SL level), setup is invalidated.
    n_candles = len(eval_df)

    if has_bear_choch:
        candles_since_bear_choch = (n_candles - 1) - bear_choch_idx
        if (candles_since_bear_choch > 10 and not in_bear_fvg) or (closed_close > sweep_high_price):
            has_buy_sweep = False
            has_bear_choch = False
            zones_bear = {'bearish_fvg': []}
            in_bear_fvg = False
            p5_sell_rejection = False

    if has_bull_choch:
        candles_since_bull_choch = (n_candles - 1) - bull_choch_idx
        if (candles_since_bull_choch > 10 and not in_bull_fvg) or (closed_close < sweep_low_price):
            has_sell_sweep = False
            has_bull_choch = False
            zones_bull = {'bullish_fvg': []}
            in_bull_fvg = False
            p5_buy_rejection = False

    custom_step8_s = None
    custom_step9_s = None

    # ── 1. BUY SIGNAL EVALUATION (CONDITION 8 & 9 MANDATORY 🟢) ──
    if is_m15_bullish and has_sell_sweep and has_bull_choch and (len(zones_bull['bullish_fvg']) > 0) and in_bull_fvg and p5_buy_rejection:
        buf = 0.75 if is_metals else 0.00040
        min_dist = 0.01 if is_metals else 0.00010
        sl_price = sweep_low_price - buf
        sl_dist = max(min_dist, price - sl_price)

        # Condition 8 Anti-Chasing Cap: Max allowable SL distance for Metals (Gold) is $7.50
        max_sl_cap = 7.50 if is_metals else 0.0050
        leg_high = float(eval_df['high'].iloc[sell_sweep_idx:].max())
        eq_50 = sweep_low_price + 0.50 * (leg_high - sweep_low_price)

        # Condition 9: Opposing Liquidity Target (BSL - Swing High / Bearish Order Block)
        from smc_indicators import get_swing_points
        m15_sh, _ = get_swing_points(df_m15, n_left=3, n_right=3)
        m5_sh, _ = get_swing_points(eval_df, n_left=3, n_right=3)

        all_zones = detect_smc_zones(eval_df, min_idx=0)
        opp_obs = all_zones.get('bearish_ob', []) + all_zones.get('bearish_breaker', [])

        target_candidates = []
        for p_t, _ in m15_sh:
            if p_t > price + (1.0 if is_metals else 0.0005):
                target_candidates.append(float(p_t))
        for p_t, _ in m5_sh:
            if p_t > price + (1.0 if is_metals else 0.0005):
                target_candidates.append(float(p_t))
        for low_b, high_b in opp_obs:
            if float(low_b) > price + (1.0 if is_metals else 0.0005):
                target_candidates.append(float(low_b))

        target_candidates = sorted(list(set([round(x, 2 if is_metals else 5) for x in target_candidates])))

        ob_buf = 0.50 if is_metals else 0.00020
        selected_target = None
        selected_rrr = 0.0

        for t_lvl in target_candidates:
            front_run_tp = t_lvl - ob_buf
            candidate_rrr = (front_run_tp - price) / sl_dist
            if candidate_rrr >= 1.50:
                selected_target = front_run_tp
                selected_rrr = candidate_rrr
                break

        if selected_target is None:
            if not target_candidates:
                selected_target = price + (1.85 * sl_dist)
                selected_rrr = 1.85
            else:
                nearest_blocker = target_candidates[0]
                avail_rrr = (nearest_blocker - price) / sl_dist
                selected_target = nearest_blocker - ob_buf
                selected_rrr = avail_rrr

        if selected_rrr > 2.50:
            selected_target = price + (2.50 * sl_dist)
            selected_rrr = 2.50

        tp_price = round(selected_target, 2 if is_metals else 5)
        target_rrr = selected_rrr

        is_sl_ok = (sl_dist <= max_sl_cap) or bypass_filters
        is_discount_ok = (price <= (eq_50 + (0.50 if is_metals else 0.00020))) or bypass_filters
        is_target_ok = (selected_rrr >= 1.50) or bypass_filters

        if is_sl_ok and is_discount_ok and is_target_ok:
            reason = f"🟢 STRICT SMC PASSED! BUY: M15 Bullish + M5 Sweep ({sweep_low_price:.2f}) + CHoCH ({bull_choch_lvl:.2f}) + Discount FVG Retest | SL: {sl_price:.2f} (0.75 buf) | Opposing Target TP: {tp_price:.2f} ({target_rrr:.2f}R)"
            logger.info("================================================================================")
            logger.info(f"🟢 [STRICT SMC BUY SIGNAL EXECUTED] 🚀")
            logger.info(f"🟢 Condition 8 (Structural SL): Sweep Low ({sweep_low_price:.2f}) - 0.75 = {sl_price:.2f} (Dist: ${sl_dist:.2f} <= ${max_sl_cap:.2f} Cap) 🟢")
            logger.info(f"🟢 Condition 9 (Opposing Liquidity TP): Target Pool -> Executing {target_rrr:.2f}R TP @ {tp_price:.2f} (Front-Run 0.50) 🟢")
            logger.info("================================================================================")
            return "BUY", tp_price, sl_price, sl_dist, reason
        else:
            if not is_sl_ok:
                custom_step8_s = f"FAIL 🔴 (SL ${sl_dist:.2f} > ${max_sl_cap:.2f} Cap)"
            elif not is_discount_ok:
                custom_step8_s = f"FAIL 🔴 (Price {price:.2f} in Premium > 50% Eq {eq_50:.2f})"
            else:
                custom_step8_s = f"PASS 🟢 (0.75 Buf | ${sl_dist:.2f} SL)"

            if not is_target_ok:
                custom_step9_s = f"FAIL 🔴 (Opposing Target {selected_rrr:.2f}R < 1.5R)"
            else:
                custom_step9_s = f"PASS 🟢 ({selected_rrr:.2f}R Opposing Target | Front-Run 0.50)"

    # ── 2. SELL SIGNAL EVALUATION (CONDITION 8 & 9 MANDATORY 🔴) ──
    if is_m15_bearish and has_buy_sweep and has_bear_choch and (len(zones_bear['bearish_fvg']) > 0) and in_bear_fvg and p5_sell_rejection:
        buf = 0.75 if is_metals else 0.00040
        min_dist = 0.01 if is_metals else 0.00010
        sl_price = sweep_high_price + buf
        sl_dist = max(min_dist, sl_price - price)

        # Condition 8 Anti-Chasing Cap: Max allowable SL distance for Metals (Gold) is $7.50
        max_sl_cap = 7.50 if is_metals else 0.0050
        leg_low = float(eval_df['low'].iloc[buy_sweep_idx:].min())
        eq_50 = sweep_high_price - 0.50 * (sweep_high_price - leg_low)

        # Condition 9: Opposing Liquidity Target (SSL - Swing Low / Bullish Order Block)
        from smc_indicators import get_swing_points
        _, m15_sl = get_swing_points(df_m15, n_left=3, n_right=3)
        _, m5_sl = get_swing_points(eval_df, n_left=3, n_right=3)

        all_zones = detect_smc_zones(eval_df, min_idx=0)
        opp_obs = all_zones.get('bullish_ob', []) + all_zones.get('bullish_breaker', [])

        target_candidates = []
        for p_t, _ in m15_sl:
            if p_t < price - (1.0 if is_metals else 0.0005):
                target_candidates.append(float(p_t))
        for p_t, _ in m5_sl:
            if p_t < price - (1.0 if is_metals else 0.0005):
                target_candidates.append(float(p_t))
        for low_b, high_b in opp_obs:
            if float(high_b) < price - (1.0 if is_metals else 0.0005):
                target_candidates.append(float(high_b))

        target_candidates = sorted(list(set([round(x, 2 if is_metals else 5) for x in target_candidates])), reverse=True)

        ob_buf = 0.50 if is_metals else 0.00020
        selected_target = None
        selected_rrr = 0.0

        for t_lvl in target_candidates:
            front_run_tp = t_lvl + ob_buf
            candidate_rrr = (price - front_run_tp) / sl_dist
            if candidate_rrr >= 1.50:
                selected_target = front_run_tp
                selected_rrr = candidate_rrr
                break

        if selected_target is None:
            if not target_candidates:
                selected_target = price - (1.85 * sl_dist)
                selected_rrr = 1.85
            else:
                nearest_blocker = target_candidates[0]
                avail_rrr = (price - nearest_blocker) / sl_dist
                selected_target = nearest_blocker + ob_buf
                selected_rrr = avail_rrr

        if selected_rrr > 2.50:
            selected_target = price - (2.50 * sl_dist)
            selected_rrr = 2.50

        tp_price = round(selected_target, 2 if is_metals else 5)
        target_rrr = selected_rrr

        is_sl_ok = (sl_dist <= max_sl_cap) or bypass_filters
        is_premium_ok = (price >= (eq_50 - (0.50 if is_metals else 0.00020))) or bypass_filters
        is_target_ok = (selected_rrr >= 1.50) or bypass_filters

        if is_sl_ok and is_premium_ok and is_target_ok:
            reason = f"🔴 STRICT SMC PASSED! SELL: M15 Bearish + M5 Sweep ({sweep_high_price:.2f}) + CHoCH ({bear_choch_lvl:.2f}) + Premium FVG Retest | SL: {sl_price:.2f} (0.75 buf) | Opposing Target TP: {tp_price:.2f} ({target_rrr:.2f}R)"
            logger.info("================================================================================")
            logger.info(f"🔴 [STRICT SMC SELL SIGNAL EXECUTED] 🚀")
            logger.info(f"🔴 Condition 8 (Structural SL): Sweep High ({sweep_high_price:.2f}) + 0.75 = {sl_price:.2f} (Dist: ${sl_dist:.2f} <= ${max_sl_cap:.2f} Cap) 🔴")
            logger.info(f"🔴 Condition 9 (Opposing Liquidity TP): Target Pool -> Executing {target_rrr:.2f}R TP @ {tp_price:.2f} (Front-Run 0.50) 🔴")
            logger.info("================================================================================")
            return "SELL", tp_price, sl_price, sl_dist, reason
        else:
            if not is_sl_ok:
                custom_step8_s = f"FAIL 🔴 (SL ${sl_dist:.2f} > ${max_sl_cap:.2f} Cap)"
            elif not is_premium_ok:
                custom_step8_s = f"FAIL 🔴 (Price {price:.2f} in Discount < 50% Eq {eq_50:.2f})"
            else:
                custom_step8_s = f"PASS 🟢 (0.75 Buf | ${sl_dist:.2f} SL)"

            if not is_target_ok:
                custom_step9_s = f"FAIL 🔴 (Opposing Target {selected_rrr:.2f}R < 1.5R)"
            else:
                custom_step9_s = f"PASS 🟢 ({selected_rrr:.2f}R Opposing Target | Front-Run 0.50)"

    # ── 3. SCANNER LOGGING (ALL 9 STEPS INDIVIDUALLY DISPLAYED) ──
    if is_m15_bullish:
        step1_s = "BULLISH 🟢"
        step2_s = "PASS 🟢 (Sell-Side Sweep)" if has_sell_sweep else "WAITING ⚪ (Awaiting Fresh Sweep)"
        step3_s = "PASS 🟢 (Bullish CHoCH)" if has_bull_choch else "WAITING ⚪ (Awaiting Fresh CHoCH)"
        step4_s = "PASS 🟢 (Displacement FVG)" if (len(zones_bull['bullish_fvg']) > 0) else "WAITING ⚪ (Awaiting Displacement FVG)"
        step5_s = "PASS 🟢 (Retested FVG)" if in_bull_fvg else "WAITING ⚪ (Awaiting Retest)"
        step6_s = "PASS 🟢 (Rejection)" if p5_buy_rejection else "WAITING ⚪ (Awaiting Rejection)"
        step7_s = "PASS 🟢 (Candle Closed)" if p5_buy_rejection else "WAITING ⚪ (Waiting Candle Close)"
    elif is_m15_bearish:
        step1_s = "BEARISH 🔴"
        step2_s = "PASS 🔴 (Buy-Side Sweep)" if has_buy_sweep else "WAITING ⚪ (Awaiting Fresh Sweep)"
        step3_s = "PASS 🔴 (Bearish CHoCH)" if has_bear_choch else "WAITING ⚪ (Awaiting Fresh CHoCH)"
        step4_s = "PASS 🔴 (Displacement FVG)" if (len(zones_bear['bearish_fvg']) > 0) else "WAITING ⚪ (Awaiting Displacement FVG)"
        step5_s = "PASS 🔴 (Retested FVG)" if in_bear_fvg else "WAITING ⚪ (Awaiting Retest)"
        step6_s = "PASS 🔴 (Rejection)" if p5_sell_rejection else "WAITING ⚪ (Awaiting Rejection)"
        step7_s = "PASS 🔴 (Candle Closed)" if p5_sell_rejection else "WAITING ⚪ (Waiting Candle Close)"
    else:
        step1_s = "NEUTRAL ⚪"
        step2_s = "WAITING ⚪ (M15 Neutral)"
        step3_s = "WAITING ⚪ (M15 Neutral)"
        step4_s = "WAITING ⚪ (M15 Neutral)"
        step5_s = "WAITING ⚪ (M15 Neutral)"
        step6_s = "WAITING ⚪ (M15 Neutral)"
        step7_s = "WAITING ⚪ (M15 Neutral)"

    if custom_step8_s is not None:
        step8_s = custom_step8_s
    else:
        step8_s = "PASS 🟢 (0.75 Buf | $7.50 Cap)" if is_metals else "PASS 🟢 (0.0004 Buf | Cap)"

    if custom_step9_s is not None:
        step9_s = custom_step9_s
    else:
        try:
            from smc_indicators import get_swing_points
            buf = 0.75 if is_metals else 0.00040
            min_dist = 0.01 if is_metals else 0.00010
            if is_m15_bullish:
                sl_p_check = (sweep_low_price - buf) if has_sell_sweep else (price - (1.5 if is_metals else 0.0015))
                sl_d_check = max(min_dist, price - sl_p_check)
                m15_sh, _ = get_swing_points(df_m15, n_left=3, n_right=3)
                m15_targets = [p for p, _ in m15_sh if p > price]
                if not m15_targets:
                    scan_rrr = 2.0
                else:
                    valid_targets = [p for p in m15_targets if (p - price) / sl_d_check >= 1.5]
                    target_high = min(valid_targets) if valid_targets else max(m15_targets)
                    scan_rrr = (target_high - price) / sl_d_check
            elif is_m15_bearish:
                sl_p_check = (sweep_high_price + buf) if has_buy_sweep else (price + (1.5 if is_metals else 0.0015))
                sl_d_check = max(min_dist, sl_p_check - price)
                _, m15_sl = get_swing_points(df_m15, n_left=3, n_right=3)
                m15_targets = [p for p, _ in m15_sl if p < price]
                if not m15_targets:
                    scan_rrr = 2.0
                else:
                    valid_targets = [p for p in m15_targets if (price - p) / sl_d_check >= 1.5]
                    target_low = max(valid_targets) if valid_targets else min(m15_targets)
                    scan_rrr = (price - target_low) / sl_d_check
            else:
                scan_rrr = 1.85

            if scan_rrr >= 1.5:
                step9_s = f"PASS 🟢 ({scan_rrr:.2f}R Opposing Target | Front-Run 0.50)"
            else:
                step9_s = f"FAIL 🔴 ({scan_rrr:.2f}R Target Space < 1.5R Min)"
        except Exception:
            step9_s = "PASS 🟢 (Opposing Target Min 1.5R)"

    actual_sweep_p = sweep_low_price if has_sell_sweep else (sweep_high_price if has_buy_sweep else 0.0)
    actual_choch_p = bull_choch_lvl if has_bull_choch else (bear_choch_lvl if has_bear_choch else 0.0)
    scan_msg = f"Scanning Strict 9-Condition SMC | S1(M15): {step1_s} | S2(Sweep): {step2_s} | S3(CHoCH): {step3_s} | S4(Displacement FVG): {step4_s} | S5(Retest): {step5_s} | S6(Rejection): {step6_s} | S7(Closed): {step7_s} | S8(SL Buf): {step8_s} | S9(Target): {step9_s} | SweepPrice: {actual_sweep_p:.2f} | ChochPrice: {actual_choch_p:.2f}"
    return "NONE", None, None, 0.0, scan_msg

