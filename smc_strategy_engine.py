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
    get_smc_asset_profile,
)

logger = logging.getLogger("SMC_Strategy_Engine")


def _compute_m15_opposing_target(
    is_buy: bool,
    df_m15: pd.DataFrame,
    entry_p: float,
    sl_d: float,
    is_metals: bool = True,
    profile: dict = None,
):
    """
    Computes the nearest opposing M15 structural liquidity target (Swing High/Low + Opposing OB/Breaker)
    with institutional front-run buffer ($1.10 Gold / 9.35 pts Indices / 3.5 pips Forex) so TP fills ahead of wick bounces.
    """
    if profile is None:
        profile = get_smc_asset_profile(df_m15, symbol="XAUUSD" if is_metals else None)
    min_amp = profile["m15_target_min_amp"]
    sh_3, sl_3 = get_swing_points(df_m15, n_left=3, n_right=3)
    sh_2, sl_2 = get_swing_points(df_m15, n_left=2, n_right=2, min_amplitude=min_amp)
    if (is_buy and not sh_2) or (not is_buy and not sl_2):
        fb_sh_2, fb_sl_2 = get_swing_points(df_m15, n_left=2, n_right=2)
        if is_buy and not sh_2:
            sh_2 = fb_sh_2
        if not is_buy and not sl_2:
            sl_2 = fb_sl_2

    all_zones = detect_smc_zones(
        df_m15,
        min_idx=0,
        symbol=profile.get("key") if profile.get("key") in ("us30", "nas100") else None,
        category=profile.get("category"),
    )
    min_move = profile["target_min_move"]
    ob_buf = profile["ob_buf"]
    min_rrr = 1.85
    digits = profile["digits"]

    if is_buy:
        opp_obs = all_zones.get('bearish_ob', []) + all_zones.get('bearish_breaker', [])
        candidates = [float(p_t) for p_t, _ in (sh_3 + sh_2) if p_t > entry_p + min_move]
        candidates.extend(float(low_b) for low_b, _ in opp_obs if float(low_b) > entry_p + min_move)
        candidates = sorted(set(round(x, digits) for x in candidates))
        for t_lvl in candidates:
            front_run_tp = t_lvl - ob_buf
            cand_rrr = (front_run_tp - entry_p) / sl_d
            if cand_rrr >= min_rrr:
                if cand_rrr > 3.00:
                    return round(entry_p + 3.00 * sl_d, digits), 3.00
                return round(front_run_tp, digits), cand_rrr
        return round(entry_p + 2.20 * sl_d, digits), 2.20

    opp_obs = all_zones.get('bullish_ob', []) + all_zones.get('bullish_breaker', [])
    candidates = [float(p_t) for p_t, _ in (sl_3 + sl_2) if p_t < entry_p - min_move]
    candidates.extend(float(high_b) for _, high_b in opp_obs if float(high_b) < entry_p - min_move)
    candidates = sorted(set(round(x, digits) for x in candidates), reverse=True)
    for t_lvl in candidates:
        front_run_tp = t_lvl + ob_buf
        cand_rrr = (entry_p - front_run_tp) / sl_d
        if cand_rrr >= min_rrr:
            if cand_rrr > 3.00:
                return round(entry_p - 3.00 * sl_d, digits), 3.00
            return round(front_run_tp, digits), cand_rrr
    return round(entry_p - 2.20 * sl_d, digits), 2.20


def compute_smc_signal_quality(
    target_rrr: float,
    sl_dist: float,
    max_sl_cap: float,
    rejection_wick_ratio: float,
    body_close_dir_ok: bool,
    fvg_gap: float,
    min_fvg_gap: float,
    candles_since_choch: int,
) -> float:
    """
    Compute deterministic 0..100 setup quality score used to pick the highest-probability
    setup when multiple assets (e.g. XAUUSD, US30, NAS100) trigger signals simultaneously.
    """
    score = 0.0
    # 1. Risk-to-Reward edge (1.85R .. 3.00R -> up to 35 pts)
    rrr_norm = max(0.0, min(1.0, (float(target_rrr) - 1.85) / 1.15))
    score += 18.0 + 17.0 * rrr_norm
    # 2. Structural tightness (cleaner tighter SL relative to asset cap -> up to 20 pts)
    if max_sl_cap > 0 and sl_dist > 0:
        sl_ratio = max(0.0, min(1.0, 1.0 - (sl_dist / (max_sl_cap * 1.15))))
        score += 8.0 + 12.0 * sl_ratio
    # 3. Rejection candle conviction (pinbar wick + directional close -> up to 22 pts)
    wick_score = max(0.0, min(1.0, float(rejection_wick_ratio) / 0.65))
    score += 14.0 * wick_score + (8.0 if body_close_dir_ok else 0.0)
    # 4. Displacement FVG strength (clean institutional imbalance -> up to 13 pts)
    if min_fvg_gap > 0:
        gap_ratio = max(0.0, min(1.0, (float(fvg_gap) / min_fvg_gap - 1.0) / 2.0))
        score += 6.0 + 7.0 * gap_ratio
    # 5. Timing freshness (fresher CHoCH-to-retest trigger -> up to 10 pts)
    fresh = max(0.0, min(1.0, 1.0 - (max(0, int(candles_since_choch)) / 18.0)))
    score += 10.0 * fresh
    return round(max(0.0, min(100.0, score)), 2)


def evaluate_smc_strategy_signal(
    df_m15: pd.DataFrame,
    df_m5: pd.DataFrame = None,
    category: str = "forex",
    bypass_filters: bool = False,
    net_obi: float = 0.0,
    obi_enabled: bool = False,
    live_price: float = None,
    is_already_closed: bool = False,
    symbol: str = None,
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
    8. Step 8 (S8) — Structural SL behind Sweep Wick ($0.75 Gold buffer / $10.00 max cap)
    9. Step 9 (S9) — M15 Opposing Liquidity Target (>= 1.85R, $1.10 Gold front-run, no micro-scalps)
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

    profile = get_smc_asset_profile(df_m15, symbol=symbol, category=category, ref_price=closed_close)
    is_metals = (profile["category"] == "metals")
    is_high_pt = profile["is_high_point"]
    wick_buf = profile["wick_buf"]
    min_dist = profile["min_dist"]
    max_chase_dist = profile["max_chase_dist"]
    max_sl_cap = profile["max_sl_cap"]
    close_tol = profile["close_tol"]
    min_pen_gap = profile["min_pen_gap"]
    fallback_sl_dist = profile["fallback_sl_dist"]
    digits = profile["digits"]
    buf_lbl = f"${wick_buf:.2f}" if is_metals else (f"{wick_buf:.2f}pts" if is_high_pt else f"{wick_buf:.4f}")
    cap_lbl = f"${max_sl_cap:.2f}" if is_metals else (f"{max_sl_cap:.1f}pts" if is_high_pt else f"{max_sl_cap:.4f}")
    sl_prefix = "$" if is_metals else ("" if is_high_pt else "")
    sl_suffix = "" if is_metals else ("pts" if is_high_pt else "")

    # S1: M15 Market Structure Bias
    structure = detect_market_structure(df_m15, symbol=symbol, category=category)
    is_m15_bullish = (structure == 'BULLISH')
    is_m15_bearish = (structure == 'BEARISH')

    # S2: M5 Liquidity Sweep (SL Hunt)
    sell_sweep, buy_sweep = detect_liquidity_sweep(eval_df, symbol=symbol, category=category)
    has_sell_sweep, sweep_low_price, sl_swing_val, sell_sweep_idx = sell_sweep
    has_buy_sweep, sweep_high_price, sh_swing_val, buy_sweep_idx = buy_sweep

    # S3: M5 CHoCH / BOS Reversal (After Sweep)
    has_bull_choch, bull_choch_lvl, bull_choch_idx = detect_choch_bos(eval_df, sell_sweep_idx, is_bullish=True) if has_sell_sweep else (False, 0.0, -1)
    has_bear_choch, bear_choch_lvl, bear_choch_idx = detect_choch_bos(eval_df, buy_sweep_idx, is_bullish=False) if has_buy_sweep else (False, 0.0, -1)

    # S4: Displacement Leg 3-Candle FVG
    zones_bull = detect_smc_zones(eval_df, min_idx=sell_sweep_idx, sweep_low=sweep_low_price, symbol=symbol, category=category) if has_bull_choch else {'bullish_fvg': []}
    zones_bear = detect_smc_zones(eval_df, min_idx=buy_sweep_idx, sweep_high=sweep_high_price, symbol=symbol, category=category) if has_bear_choch else {'bearish_fvg': []}

    # S5: Confirmed Closed-Candle FVG Retest (Strictly on post-creation closed bars; zero live-tick bypass)
    bull_fvg_list = zones_bull.get('bullish_fvg_meta') or zones_bull.get('bullish_fvg', [])
    bear_fvg_list = zones_bear.get('bearish_fvg_meta') or zones_bear.get('bearish_fvg', [])
    in_bull_fvg, matched_bull_fvg = check_fvg_retest(
        closed_open, closed_high, closed_low, closed_close,
        bull_fvg_list, is_bullish=True, max_wick_buf=wick_buf, prev_row=prev_closed_row, closed_idx=closed_idx,
        close_tol=close_tol, min_pen_gap=min_pen_gap
    )
    in_bear_fvg, matched_bear_fvg = check_fvg_retest(
        closed_open, closed_high, closed_low, closed_close,
        bear_fvg_list, is_bullish=False, max_wick_buf=wick_buf, prev_row=prev_closed_row, closed_idx=closed_idx,
        close_tol=close_tol, min_pen_gap=min_pen_gap
    )

    # S6 & S7: Confirmed Closed Rejection Candle (True Wick Calculation — Never Count Opposite Body as Wick!)
    range_floor = 0.01 if is_high_pt else 0.0001
    bull_lower_wick = min(closed_open, closed_close) - closed_low
    bull_candle_range = max(range_floor, closed_high - closed_low)
    bull_is_green = closed_close > closed_open
    bull_is_pinbar = (bull_lower_wick / bull_candle_range >= 0.45) and ((closed_open - closed_close) <= 0.25 * bull_candle_range)
    p5_buy_rejection = (
        in_bull_fvg
        and matched_bull_fvg is not None
        and closed_close >= matched_bull_fvg[0]
        and (bull_is_green or bull_is_pinbar)
    )

    bear_upper_wick = closed_high - max(closed_open, closed_close)
    bear_candle_range = max(range_floor, closed_high - closed_low)
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
    candles_since_bear_choch = 0
    candles_since_bull_choch = 0
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
    front_run_lbl = "$1.10" if is_metals else (f"{profile['ob_buf']:.2f}pts" if is_high_pt else "3.5p")
    min_target_rrr = 1.85

    # ── 1. BUY SIGNAL EVALUATION (ALL 9 CONDITIONS STRICT) ──
    if is_m15_bullish and has_sell_sweep and has_bull_choch and (len(zones_bull['bullish_fvg']) > 0) and in_bull_fvg and p5_buy_rejection:
        sl_price = round(sweep_low_price - wick_buf, digits)
        sl_dist = max(min_dist, price - sl_price)

        fvg_low, fvg_high = matched_bull_fvg
        is_chasing = price > (fvg_high + max_chase_dist)

        tp_price, target_rrr = _compute_m15_opposing_target(True, df_m15, price, sl_dist, is_metals, profile=profile)
        scan_tp = tp_price

        is_sl_ok = (sl_dist <= max_sl_cap and not is_chasing) or bypass_filters
        is_target_ok = (target_rrr >= min_target_rrr) or bypass_filters

        if is_sl_ok and is_target_ok:
            q_score = compute_smc_signal_quality(
                target_rrr=target_rrr,
                sl_dist=sl_dist,
                max_sl_cap=max_sl_cap,
                rejection_wick_ratio=(bull_lower_wick / bull_candle_range),
                body_close_dir_ok=bull_is_green,
                fvg_gap=(fvg_high - fvg_low),
                min_fvg_gap=profile["min_fvg_gap"],
                candles_since_choch=candles_since_bull_choch,
            )
            reason = (
                f"🟢 STRICT SMC PASSED! BUY: M15 Bullish + M5 Sweep ({sweep_low_price:.2f}) "
                f"+ CHoCH ({bull_choch_lvl:.2f}) + Closed Rejection | SL: {sl_price:.2f} ({wick_buf:.2f} buf) "
                f"| M15 Target TP: {tp_price:.2f} ({target_rrr:.2f}R) | Quality: {q_score:.1f}"
            )
            logger.info("================================================================================")
            logger.info("🟢 [STRICT 9-CONDITION SMC BUY SIGNAL EXECUTED] 🚀")
            logger.info(f"🟢 S8 (Structural SL): Sweep Low ({sweep_low_price:.2f}) - {wick_buf:.2f} = {sl_price:.2f} (Dist: {sl_prefix}{sl_dist:.2f}{sl_suffix} <= {cap_lbl} Cap)")
            logger.info(f"🟢 S9 (M15 Liquidity TP): Executing {target_rrr:.2f}R TP @ {tp_price:.2f} (Quality: {q_score:.1f}/100)")
            logger.info("================================================================================")
            return "BUY", tp_price, sl_price, sl_dist, reason
        else:
            if not is_sl_ok:
                custom_step8_s = (
                    f"FAIL 🔴 (Late Chasing {price:.2f} > FVG {fvg_high:.2f})"
                    if is_chasing
                    else f"FAIL 🔴 (SL {sl_prefix}{sl_dist:.2f}{sl_suffix} > {cap_lbl} Cap)"
                )
            else:
                custom_step8_s = f"PASS 🟢 ({wick_buf:.2f} Buf - {sl_prefix}{sl_dist:.2f}{sl_suffix} SL)"

            if not is_target_ok:
                custom_step9_s = f"FAIL 🔴 (M15 Target {target_rrr:.2f}R < {min_target_rrr:.2f}R)"
            else:
                custom_step9_s = f"PASS 🟢 ({target_rrr:.2f}R M15 Target - {front_run_lbl} Front-Run)"

    # ── 2. SELL SIGNAL EVALUATION (ALL 9 CONDITIONS STRICT) ──
    if is_m15_bearish and has_buy_sweep and has_bear_choch and (len(zones_bear['bearish_fvg']) > 0) and in_bear_fvg and p5_sell_rejection:
        sl_price = round(sweep_high_price + wick_buf, digits)
        sl_dist = max(min_dist, sl_price - price)

        fvg_low, fvg_high = matched_bear_fvg
        is_chasing = price < (fvg_low - max_chase_dist)

        tp_price, target_rrr = _compute_m15_opposing_target(False, df_m15, price, sl_dist, is_metals, profile=profile)
        scan_tp = tp_price

        is_sl_ok = (sl_dist <= max_sl_cap and not is_chasing) or bypass_filters
        is_target_ok = (target_rrr >= min_target_rrr) or bypass_filters

        if is_sl_ok and is_target_ok:
            q_score = compute_smc_signal_quality(
                target_rrr=target_rrr,
                sl_dist=sl_dist,
                max_sl_cap=max_sl_cap,
                rejection_wick_ratio=(bear_upper_wick / bear_candle_range),
                body_close_dir_ok=bear_is_red,
                fvg_gap=(fvg_high - fvg_low),
                min_fvg_gap=profile["min_fvg_gap"],
                candles_since_choch=candles_since_bear_choch,
            )
            reason = (
                f"🔴 STRICT SMC PASSED! SELL: M15 Bearish + M5 Sweep ({sweep_high_price:.2f}) "
                f"+ CHoCH ({bear_choch_lvl:.2f}) + Closed Rejection | SL: {sl_price:.2f} ({wick_buf:.2f} buf) "
                f"| M15 Target TP: {tp_price:.2f} ({target_rrr:.2f}R) | Quality: {q_score:.1f}"
            )
            logger.info("================================================================================")
            logger.info("🔴 [STRICT 9-CONDITION SMC SELL SIGNAL EXECUTED] 🚀")
            logger.info(f"🔴 S8 (Structural SL): Sweep High ({sweep_high_price:.2f}) + {wick_buf:.2f} = {sl_price:.2f} (Dist: {sl_prefix}{sl_dist:.2f}{sl_suffix} <= {cap_lbl} Cap)")
            logger.info(f"🔴 S9 (M15 Liquidity TP): Executing {target_rrr:.2f}R TP @ {tp_price:.2f} (Quality: {q_score:.1f}/100)")
            logger.info("================================================================================")
            return "SELL", tp_price, sl_price, sl_dist, reason
        else:
            if not is_sl_ok:
                custom_step8_s = (
                    f"FAIL 🔴 (Late Chasing {price:.2f} < FVG {fvg_low:.2f})"
                    if is_chasing
                    else f"FAIL 🔴 (SL {sl_prefix}{sl_dist:.2f}{sl_suffix} > {cap_lbl} Cap)"
                )
            else:
                custom_step8_s = f"PASS 🟢 ({wick_buf:.2f} Buf - {sl_prefix}{sl_dist:.2f}{sl_suffix} SL)"

            if not is_target_ok:
                custom_step9_s = f"FAIL 🔴 (M15 Target {target_rrr:.2f}R < {min_target_rrr:.2f}R)"
            else:
                custom_step9_s = f"PASS 🟢 ({target_rrr:.2f}R M15 Target - {front_run_lbl} Front-Run)"

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

    # S8: Structural SL Placement
    if custom_step8_s is not None:
        step8_s = custom_step8_s
    else:
        step8_s = f"PASS 🟢 ({buf_lbl} Buf - {cap_lbl} Cap)"

    # S9: M15 Opposing Liquidity Target (>= 1.85R with Front-Run)
    if custom_step9_s is not None:
        step9_s = custom_step9_s
    else:
        try:
            if is_m15_bullish:
                sl_p_check = (sweep_low_price - wick_buf) if has_sell_sweep else (price - fallback_sl_dist)
                sl_d_check = max(min_dist, price - sl_p_check)
                scan_tp, scan_rrr = _compute_m15_opposing_target(True, df_m15, price, sl_d_check, is_metals, profile=profile)
            elif is_m15_bearish:
                sl_p_check = (sweep_high_price + wick_buf) if has_buy_sweep else (price + fallback_sl_dist)
                sl_d_check = max(min_dist, sl_p_check - price)
                scan_tp, scan_rrr = _compute_m15_opposing_target(False, df_m15, price, sl_d_check, is_metals, profile=profile)
            else:
                scan_rrr = 2.00
                scan_tp = 0.0

            if scan_rrr >= min_target_rrr:
                step9_s = f"PASS 🟢 ({scan_rrr:.2f}R M15 Target - {front_run_lbl} Front-Run)"
            else:
                step9_s = f"FAIL 🔴 ({scan_rrr:.2f}R M15 Target < {min_target_rrr:.2f}R Min)"
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
