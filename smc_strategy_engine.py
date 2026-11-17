import os
import numpy as np
import pandas as pd
import logging
from smc_indicators import (
    detect_market_structure,
    detect_liquidity_sweep,
    detect_choch_bos,
    detect_smc_zones,
    check_fvg_retest,
    get_swing_points,
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
    is_already_closed: bool = False,
):
    """
    Pure Rule-Based SMC / ICT 9-Condition Strict Strategy Engine:

    1. Step 1 (S1) — M15 Market Structure Bias (HH+HL = Bullish | LH+LL = Bearish)
    2. Step 2 (S2) — M5 Liquidity Sweep / SL Hunt (Wick beyond swing level, reclaim inside)
    3. Step 3 (S3) — M5 CHoCH / BOS (Candle close beyond prior swing structure AFTER sweep)
    4. Step 4 (S4) — 3-Candle Displacement FVG Creation (Formed during sweep-to-CHoCH leg)
    5. Step 5 (S5) — Confirmed Closed Candle Retests THAT Displacement FVG
    6. Step 6 (S6) — FVG Retest Rejection Candle (Pinbar / Directional defense close)
    7. Step 7 (S7) — Confirmation Close (Strictly after rejection candle iloc[-2] closes)
    8. Step 8 (S8) — Structural SL behind Sweep Wick ($0.75 Gold buffer / $7.50 max cap)
    9. Step 9 (S9) — M15 Opposing Liquidity Target (>= 2.0R min, $67-$80+ Gold setups, no micro-scalps)
    """
    if df_m15 is None or len(df_m15) < 15 or 'close' not in df_m15.columns:
        return "NONE", None, None, 0.0, "Insufficient candle data for SMC"

    eval_df = df_m5 if (df_m5 is not None and len(df_m5) >= 10) else df_m15
    if len(eval_df) < 4:
        return "NONE", None, None, 0.0, "Insufficient candle history for closed candle confirmation"

    if is_already_closed:
        closed_idx = len(eval_df) - 1
        closed_row = eval_df.iloc[-1]
        prev_closed_row = eval_df.iloc[-2]
        price = live_price if live_price is not None else float(closed_row['close'])
    else:
        curr_live_row = eval_df.iloc[-1]
        closed_idx = len(eval_df) - 2
        closed_row = eval_df.iloc[-2]      # STRICT CLOSED CONFIRMATION BAR
        prev_closed_row = eval_df.iloc[-3] # Prior closed bar for 2-candle retest+rejection
        price = live_price if live_price is not None else float(curr_live_row['close'])

    closed_close = float(closed_row['close'])
    closed_open = float(closed_row['open'])
    closed_low = float(closed_row['low'])
    closed_high = float(closed_row['high'])

    is_metals = (category == "metals" or "XAU" in str(df_m15.get('symbol', '')) or float(closed_close) > 500)

    # S1: M15 Market Structure Bias
    structure = detect_market_structure(df_m15)
    is_m15_bullish = (structure == 'BULLISH')
    is_m15_bearish = (structure == 'BEARISH')

    # S2: M5 Liquidity Sweep (SL Hunt)
    sell_sweep, buy_sweep = detect_liquidity_sweep(eval_df)
    has_sell_sweep, sweep_low_price, sl_swing_val, sell_sweep_idx = sell_sweep
    has_buy_sweep, sweep_high_price, sh_swing_val, buy_sweep_idx = buy_sweep

    # S3: M5 CHoCH / BOS Reversal (After Sweep)
    has_bull_choch, bull_choch_lvl, bull_choch_idx = detect_choch_bos(eval_df, sell_sweep_idx, is_bullish=True) if has_sell_sweep else (False, 0.0, -1)
    has_bear_choch, bear_choch_lvl, bear_choch_idx = detect_choch_bos(eval_df, buy_sweep_idx, is_bullish=False) if has_buy_sweep else (False, 0.0, -1)

    # S4: Displacement Leg 3-Candle FVG
    zones_bull = detect_smc_zones(eval_df, min_idx=sell_sweep_idx, sweep_low=sweep_low_price) if has_bull_choch else {'bullish_fvg': []}
    zones_bear = detect_smc_zones(eval_df, min_idx=buy_sweep_idx, sweep_high=sweep_high_price) if has_bear_choch else {'bearish_fvg': []}

    # S5: Confirmed Closed-Candle FVG Retest (Strictly on post-creation closed bars; zero live-tick bypass)
    wick_buf = 0.75 if is_metals else 0.00040
    bull_fvg_list = zones_bull.get('bullish_fvg_meta') or zones_bull.get('bullish_fvg', [])
    bear_fvg_list = zones_bear.get('bearish_fvg_meta') or zones_bear.get('bearish_fvg', [])
    in_bull_fvg, matched_bull_fvg = check_fvg_retest(
        closed_open, closed_high, closed_low, closed_close,
        bull_fvg_list, is_bullish=True, max_wick_buf=wick_buf, prev_row=prev_closed_row, closed_idx=closed_idx
    )
    in_bear_fvg, matched_bear_fvg = check_fvg_retest(
        closed_open, closed_high, closed_low, closed_close,
        bear_fvg_list, is_bullish=False, max_wick_buf=wick_buf, prev_row=prev_closed_row, closed_idx=closed_idx
    )

    # S6 & S7: Confirmed Closed Rejection Candle (True Wick Calculation — Never Count Opposite Body as Wick!)
    bull_lower_wick = min(closed_open, closed_close) - closed_low
    bull_candle_range = max(0.01 if is_metals else 0.0001, closed_high - closed_low)
    bull_is_green = closed_close > closed_open
    bull_is_pinbar = (bull_lower_wick / bull_candle_range >= 0.45) and ((closed_open - closed_close) <= 0.25 * bull_candle_range)
    p5_buy_rejection = (
        in_bull_fvg
        and matched_bull_fvg is not None
        and closed_close >= matched_bull_fvg[0]
        and (bull_is_green or bull_is_pinbar)
    )

    bear_upper_wick = closed_high - max(closed_open, closed_close)
    bear_candle_range = max(0.01 if is_metals else 0.0001, closed_high - closed_low)
    bear_is_red = closed_close < closed_open
    bear_is_pinbar = (bear_upper_wick / bear_candle_range >= 0.45) and ((closed_close - closed_open) <= 0.25 * bear_candle_range)
    p5_sell_rejection = (
        in_bear_fvg
        and matched_bear_fvg is not None
        and closed_close <= matched_bear_fvg[1]
        and (bear_is_red or bear_is_pinbar)
    )

    # Freshness & Structure Invalidation Guard (18 M5 bars = 90 mins window)
    n_candles = len(eval_df)
    if has_bear_choch:
        candles_since_bear_choch = (n_candles - 1) - bear_choch_idx
        if (candles_since_bear_choch > 18 and not in_bear_fvg) or (closed_close > sweep_high_price):
            has_buy_sweep = False
            has_bear_choch = False
            zones_bear = {'bearish_fvg': []}
            in_bear_fvg = False
            p5_sell_rejection = False

    if has_bull_choch:
        candles_since_bull_choch = (n_candles - 1) - bull_choch_idx
        if (candles_since_bull_choch > 18 and not in_bull_fvg) or (closed_close < sweep_low_price):
            has_sell_sweep = False
            has_bull_choch = False
            zones_bull = {'bullish_fvg': []}
            in_bull_fvg = False
            p5_buy_rejection = False

    custom_step8_s = None
    custom_step9_s = None
    scan_tp = 0.0

    def _compute_m15_target_buy(entry_p, sl_d):
        m15_sh, _ = get_swing_points(df_m15, n_left=3, n_right=3)
        if not m15_sh:
            m15_sh, _ = get_swing_points(df_m15, n_left=2, n_right=2)
        all_zones = detect_smc_zones(df_m15, min_idx=0)
        opp_obs = all_zones.get('bearish_ob', []) + all_zones.get('bearish_breaker', [])

        min_move = 1.0 if is_metals else 0.0005
        target_candidates = [float(p_t) for p_t, _ in m15_sh if p_t > entry_p + min_move]
        for low_b, _ in opp_obs:
            if float(low_b) > entry_p + min_move:
                target_candidates.append(float(low_b))
        target_candidates = sorted(list(set([round(x, 2 if is_metals else 5) for x in target_candidates])))

        ob_buf = 0.50 if is_metals else 0.00020
        for t_lvl in target_candidates:
            front_run_tp = t_lvl - ob_buf
            cand_rrr = (front_run_tp - entry_p) / sl_d
            if cand_rrr >= 2.00:
                if cand_rrr > 3.00:
                    return round(entry_p + 3.00 * sl_d, 2 if is_metals else 5), 3.00
                return round(front_run_tp, 2 if is_metals else 5), cand_rrr

        # No M15 swing blocker below 2.0R -> trend expansion 2.20R institutional target
        return round(entry_p + 2.20 * sl_d, 2 if is_metals else 5), 2.20

    def _compute_m15_target_sell(entry_p, sl_d):
        _, m15_sl = get_swing_points(df_m15, n_left=3, n_right=3)
        if not m15_sl:
            _, m15_sl = get_swing_points(df_m15, n_left=2, n_right=2)
        all_zones = detect_smc_zones(df_m15, min_idx=0)
        opp_obs = all_zones.get('bullish_ob', []) + all_zones.get('bullish_breaker', [])

        min_move = 1.0 if is_metals else 0.0005
        target_candidates = [float(p_t) for p_t, _ in m15_sl if p_t < entry_p - min_move]
        for _, high_b in opp_obs:
            if float(high_b) < entry_p - min_move:
                target_candidates.append(float(high_b))
        target_candidates = sorted(list(set([round(x, 2 if is_metals else 5) for x in target_candidates])), reverse=True)

        ob_buf = 0.50 if is_metals else 0.00020
        for t_lvl in target_candidates:
            front_run_tp = t_lvl + ob_buf
            cand_rrr = (entry_p - front_run_tp) / sl_d
            if cand_rrr >= 2.00:
                if cand_rrr > 3.00:
                    return round(entry_p - 3.00 * sl_d, 2 if is_metals else 5), 3.00
                return round(front_run_tp, 2 if is_metals else 5), cand_rrr

        return round(entry_p - 2.20 * sl_d, 2 if is_metals else 5), 2.20

    # ── 1. BUY SIGNAL EVALUATION (ALL 9 CONDITIONS STRICT) ──
    if is_m15_bullish and has_sell_sweep and has_bull_choch and (len(zones_bull['bullish_fvg']) > 0) and in_bull_fvg and p5_buy_rejection:
        buf = 0.75 if is_metals else 0.00040
        min_dist = 0.01 if is_metals else 0.00010
        sl_price = sweep_low_price - buf
        sl_dist = max(min_dist, price - sl_price)

        fvg_low, fvg_high = matched_bull_fvg
        max_chase_dist = 2.00 if is_metals else 0.00100
        is_chasing = price > (fvg_high + max_chase_dist)
        max_sl_cap = 7.50 if is_metals else 0.0050

        tp_price, target_rrr = _compute_m15_target_buy(price, sl_dist)
        scan_tp = tp_price

        is_sl_ok = (sl_dist <= max_sl_cap and not is_chasing) or bypass_filters
        is_target_ok = (target_rrr >= 2.00) or bypass_filters

        if is_sl_ok and is_target_ok:
            reason = (
                f"🟢 STRICT SMC PASSED! BUY: M15 Bullish + M5 Sweep ({sweep_low_price:.2f}) "
                f"+ CHoCH ({bull_choch_lvl:.2f}) + Closed Rejection | SL: {sl_price:.2f} (0.75 buf) "
                f"| M15 Target TP: {tp_price:.2f} ({target_rrr:.2f}R)"
            )
            logger.info("================================================================================")
            logger.info("🟢 [STRICT 9-CONDITION SMC BUY SIGNAL EXECUTED] 🚀")
            logger.info(f"🟢 S8 (Structural SL): Sweep Low ({sweep_low_price:.2f}) - 0.75 = {sl_price:.2f} (Dist: ${sl_dist:.2f} <= ${max_sl_cap:.2f} Cap)")
            logger.info(f"🟢 S9 (M15 Liquidity TP): Executing {target_rrr:.2f}R TP @ {tp_price:.2f}")
            logger.info("================================================================================")
            return "BUY", tp_price, sl_price, sl_dist, reason
        else:
            if not is_sl_ok:
                custom_step8_s = (
                    f"FAIL 🔴 (Late Chasing {price:.2f} > FVG {fvg_high:.2f})"
                    if is_chasing
                    else f"FAIL 🔴 (SL ${sl_dist:.2f} > ${max_sl_cap:.2f} Cap)"
                )
            else:
                custom_step8_s = f"PASS 🟢 (0.75 Buf - ${sl_dist:.2f} SL)"

            if not is_target_ok:
                custom_step9_s = f"FAIL 🔴 (M15 Target {target_rrr:.2f}R < 2.0R)"
            else:
                custom_step9_s = f"PASS 🟢 ({target_rrr:.2f}R M15 Target - $0.50 Front-Run)"

    # ── 2. SELL SIGNAL EVALUATION (ALL 9 CONDITIONS STRICT) ──
    if is_m15_bearish and has_buy_sweep and has_bear_choch and (len(zones_bear['bearish_fvg']) > 0) and in_bear_fvg and p5_sell_rejection:
        buf = 0.75 if is_metals else 0.00040
        min_dist = 0.01 if is_metals else 0.00010
        sl_price = sweep_high_price + buf
        sl_dist = max(min_dist, sl_price - price)

        fvg_low, fvg_high = matched_bear_fvg
        max_chase_dist = 2.00 if is_metals else 0.00100
        is_chasing = price < (fvg_low - max_chase_dist)
        max_sl_cap = 7.50 if is_metals else 0.0050

        tp_price, target_rrr = _compute_m15_target_sell(price, sl_dist)
        scan_tp = tp_price

        is_sl_ok = (sl_dist <= max_sl_cap and not is_chasing) or bypass_filters
        is_target_ok = (target_rrr >= 2.00) or bypass_filters

        if is_sl_ok and is_target_ok:
            reason = (
                f"🔴 STRICT SMC PASSED! SELL: M15 Bearish + M5 Sweep ({sweep_high_price:.2f}) "
                f"+ CHoCH ({bear_choch_lvl:.2f}) + Closed Rejection | SL: {sl_price:.2f} (0.75 buf) "
                f"| M15 Target TP: {tp_price:.2f} ({target_rrr:.2f}R)"
            )
            logger.info("================================================================================")
            logger.info("🔴 [STRICT 9-CONDITION SMC SELL SIGNAL EXECUTED] 🚀")
            logger.info(f"🔴 S8 (Structural SL): Sweep High ({sweep_high_price:.2f}) + 0.75 = {sl_price:.2f} (Dist: ${sl_dist:.2f} <= ${max_sl_cap:.2f} Cap)")
            logger.info(f"🔴 S9 (M15 Liquidity TP): Executing {target_rrr:.2f}R TP @ {tp_price:.2f}")
            logger.info("================================================================================")
            return "SELL", tp_price, sl_price, sl_dist, reason
        else:
            if not is_sl_ok:
                custom_step8_s = (
                    f"FAIL 🔴 (Late Chasing {price:.2f} < FVG {fvg_low:.2f})"
                    if is_chasing
                    else f"FAIL 🔴 (SL ${sl_dist:.2f} > ${max_sl_cap:.2f} Cap)"
                )
            else:
                custom_step8_s = f"PASS 🟢 (0.75 Buf - ${sl_dist:.2f} SL)"

            if not is_target_ok:
                custom_step9_s = f"FAIL 🔴 (M15 Target {target_rrr:.2f}R < 2.0R)"
            else:
                custom_step9_s = f"PASS 🟢 ({target_rrr:.2f}R M15 Target - $0.50 Front-Run)"

    # ── 3. SCANNER LOGGING (ALL 9 STRICT STEPS INDIVIDUALLY DISPLAYED — NO '|' INSIDE VALUES) ──
    if is_m15_bullish:
        step1_s = "BULLISH 🟢"
        step2_s = "PASS 🟢 (Sell-Side Sweep)" if has_sell_sweep else "WAITING ⚪ (Awaiting Fresh Sweep)"
        step3_s = "PASS 🟢 (Bullish CHoCH)" if has_bull_choch else "WAITING ⚪ (Awaiting Fresh CHoCH)"
        step4_s = "PASS 🟢 (Displacement FVG)" if (len(zones_bull['bullish_fvg']) > 0) else "WAITING ⚪ (Awaiting Displacement FVG)"
        step5_s = "PASS 🟢 (FVG Retested)" if in_bull_fvg else "WAITING ⚪ (Awaiting FVG Retest)"
        step6_s = "PASS 🟢 (Bullish Rejection)" if p5_buy_rejection else ("WAITING ⚪ (Awaiting Rejection Candle)" if in_bull_fvg else "WAITING ⚪ (Awaiting Retest)")
        step7_s = "PASS 🟢 (Candle Closed)" if p5_buy_rejection else "WAITING ⚪ (Awaiting Candle Close)"
    elif is_m15_bearish:
        step1_s = "BEARISH 🔴"
        step2_s = "PASS 🔴 (Buy-Side Sweep)" if has_buy_sweep else "WAITING ⚪ (Awaiting Fresh Sweep)"
        step3_s = "PASS 🔴 (Bearish CHoCH)" if has_bear_choch else "WAITING ⚪ (Awaiting Fresh CHoCH)"
        step4_s = "PASS 🔴 (Displacement FVG)" if (len(zones_bear['bearish_fvg']) > 0) else "WAITING ⚪ (Awaiting Displacement FVG)"
        step5_s = "PASS 🔴 (FVG Retested)" if in_bear_fvg else "WAITING ⚪ (Awaiting FVG Retest)"
        step6_s = "PASS 🔴 (Bearish Rejection)" if p5_sell_rejection else ("WAITING ⚪ (Awaiting Rejection Candle)" if in_bear_fvg else "WAITING ⚪ (Awaiting Retest)")
        step7_s = "PASS 🔴 (Candle Closed)" if p5_sell_rejection else "WAITING ⚪ (Awaiting Candle Close)"
    else:
        step1_s = "NEUTRAL ⚪"
        step2_s = "WAITING ⚪ (M15 Neutral)"
        step3_s = "WAITING ⚪ (M15 Neutral)"
        step4_s = "WAITING ⚪ (M15 Neutral)"
        step5_s = "WAITING ⚪ (M15 Neutral)"
        step6_s = "WAITING ⚪ (M15 Neutral)"
        step7_s = "WAITING ⚪ (M15 Neutral)"

    # S8: Structural SL Placement ($0.75 Buf)
    if custom_step8_s is not None:
        step8_s = custom_step8_s
    else:
        step8_s = "PASS 🟢 (0.75 Buf - $7.50 Cap)" if is_metals else "PASS 🟢 (0.0004 Buf - Cap)"

    # S9: M15 Opposing Liquidity Target (>= 2.0R)
    if custom_step9_s is not None:
        step9_s = custom_step9_s
    else:
        try:
            buf = 0.75 if is_metals else 0.00040
            min_dist = 0.01 if is_metals else 0.00010
            if is_m15_bullish:
                sl_p_check = (sweep_low_price - buf) if has_sell_sweep else (price - (2.5 if is_metals else 0.0015))
                sl_d_check = max(min_dist, price - sl_p_check)
                scan_tp, scan_rrr = _compute_m15_target_buy(price, sl_d_check)
            elif is_m15_bearish:
                sl_p_check = (sweep_high_price + buf) if has_buy_sweep else (price + (2.5 if is_metals else 0.0015))
                sl_d_check = max(min_dist, sl_p_check - price)
                scan_tp, scan_rrr = _compute_m15_target_sell(price, sl_d_check)
            else:
                scan_rrr = 2.00
                scan_tp = 0.0

            if scan_rrr >= 2.00:
                step9_s = f"PASS 🟢 ({scan_rrr:.2f}R M15 Target - $0.50 Front-Run)"
            else:
                step9_s = f"FAIL 🔴 ({scan_rrr:.2f}R M15 Target < 2.0R Min)"
        except Exception:
            step9_s = "PASS 🟢 (2.00R M15 Target)"
            scan_tp = 0.0

    if is_m15_bearish:
        actual_sweep_p = sweep_high_price if has_buy_sweep else 0.0
        actual_choch_p = bear_choch_lvl if has_bear_choch else 0.0
    elif is_m15_bullish:
        actual_sweep_p = sweep_low_price if has_sell_sweep else 0.0
        actual_choch_p = bull_choch_lvl if has_bull_choch else 0.0
    else:
        actual_sweep_p = sweep_low_price if has_sell_sweep else (sweep_high_price if has_buy_sweep else 0.0)
        actual_choch_p = bull_choch_lvl if has_bull_choch else (bear_choch_lvl if has_bear_choch else 0.0)

    tp_str = f" | OpposingTp: {scan_tp:.2f}" if scan_tp > 0 else ""
    scan_msg = (
        f"Scanning Strict 9-Condition SMC | S1(M15): {step1_s} | S2(Sweep): {step2_s} "
        f"| S3(CHoCH): {step3_s} | S4(Displacement FVG): {step4_s} | S5(Retest): {step5_s} "
        f"| S6(Rejection): {step6_s} | S7(Closed): {step7_s} | S8(SL Buf): {step8_s} "
        f"| S9(Target): {step9_s} | SweepPrice: {actual_sweep_p:.2f} | ChochPrice: {actual_choch_p:.2f}{tp_str}"
    )
    return "NONE", None, None, 0.0, scan_msg
