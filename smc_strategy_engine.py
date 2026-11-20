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
    find_protected_sweep_extreme,
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


def _get_sweep_key(is_bull: bool, sweep_idx: int, sweep_price: float, eval_df: pd.DataFrame) -> str:
    """Build a deterministic identifier for an M5 liquidity sweep to block duplicate M1/M5 re-entries."""
    prefix = "B" if is_bull else "S"
    try:
        if eval_df is not None and 0 <= sweep_idx < len(eval_df) and "time" in eval_df.columns:
            t_val = eval_df.iloc[sweep_idx]["time"]
            if pd.notna(t_val):
                return f"{prefix}:{t_val}"
    except Exception:
        pass
    return f"{prefix}:{round(float(sweep_price), 4)}"


def _record_used_sweep(used_m5_sweeps, sweep_key: str) -> None:
    """Record a consumed M5 sweep key while bounding set size."""
    if used_m5_sweeps is None or not sweep_key:
        return
    try:
        if len(used_m5_sweeps) >= 100:
            for old_key in list(used_m5_sweeps)[:40]:
                used_m5_sweeps.discard(old_key)
        used_m5_sweeps.add(sweep_key)
    except Exception:
        pass


def _find_m1_sweep_anchor(eval_df: pd.DataFrame, m1_eval: pd.DataFrame, sweep_idx: int, is_bull: bool):
    """Locate the M1 sweep anchor bar index and extreme price corresponding to an M5 sweep."""
    n1 = len(m1_eval)
    if n1 < 12:
        return -1, 0.0

    in_win_indices = []
    if "time" in eval_df.columns and "time" in m1_eval.columns and 0 <= sweep_idx < len(eval_df):
        try:
            sw_time = pd.to_datetime(eval_df.iloc[sweep_idx]["time"], errors="coerce")
            m1_times = pd.to_datetime(m1_eval["time"], errors="coerce")
            if pd.notna(sw_time) and m1_times.notna().any():
                lo_t = sw_time - pd.Timedelta(seconds=60)
                hi_t = sw_time + pd.Timedelta(seconds=300)
                mask = (m1_times >= lo_t) & (m1_times <= hi_t)
                in_win_indices = [int(idx) for idx in m1_eval.index[mask] if 0 <= int(idx) < n1]
        except Exception:
            in_win_indices = []

    if not in_win_indices:
        bars_back_m5 = max(1, len(eval_df) - 1 - max(0, sweep_idx))
        w_start = max(2, n1 - (bars_back_m5 + 1) * 5 - 3)
        w_end = min(n1 - 4, n1 - max(0, bars_back_m5 - 1) * 5 + 3)
        if w_end >= w_start:
            in_win_indices = list(range(w_start, w_end + 1))

    if not in_win_indices:
        return -1, 0.0

    lows_m1 = m1_eval["low"].values
    highs_m1 = m1_eval["high"].values
    if is_bull:
        anchor_idx = min(in_win_indices, key=lambda idx: float(lows_m1[idx]))
        return anchor_idx, float(lows_m1[anchor_idx])
    anchor_idx = max(in_win_indices, key=lambda idx: float(highs_m1[idx]))
    return anchor_idx, float(highs_m1[anchor_idx])


def _detect_m1_fvgs(
    m1_slice: pd.DataFrame,
    min_idx: int,
    min_gap: float,
    mit_tol: float,
    is_bullish: bool,
    extreme_price: float,
    sweep_margin: float,
    max_dist: float,
):
    """Detect unmitigated M1 3-candle displacement FVGs anchored to the M5/M1 sweep extreme."""
    zones = []
    n = len(m1_slice)
    if n < 5:
        return zones

    highs = m1_slice["high"].values
    lows = m1_slice["low"].values
    closes = m1_slice["close"].values
    last_p = float(closes[-1])

    for i in range(max(2, min_idx), n):
        if is_bullish:
            gap = float(lows[i] - highs[i - 2])
            if gap >= min_gap and float(highs[i - 2]) >= (extreme_price - sweep_margin):
                mit = any(float(closes[j]) < (float(highs[i - 2]) - mit_tol) for j in range(i + 1, max(i + 1, n - 1)))
                low_b, high_b = float(highs[i - 2]), float(lows[i])
                if not mit and abs(((low_b + high_b) / 2.0) - last_p) <= max_dist:
                    zones.append((low_b, high_b, int(i)))
        else:
            gap = float(lows[i - 2] - highs[i])
            if gap >= min_gap and float(lows[i - 2]) <= (extreme_price + sweep_margin):
                mit = any(float(closes[j]) > (float(lows[i - 2]) + mit_tol) for j in range(i + 1, max(i + 1, n - 1)))
                low_b, high_b = float(highs[i]), float(lows[i - 2])
                if not mit and abs(((low_b + high_b) / 2.0) - last_p) <= max_dist:
                    zones.append((low_b, high_b, int(i)))
    return zones[-2:]


def _evaluate_m1_ltf_refinement(
    is_bull: bool,
    df_m15: pd.DataFrame,
    eval_df: pd.DataFrame,
    df_m1: pd.DataFrame,
    sweep_idx: int,
    sweep_extreme: float,
    price: float,
    is_already_closed: bool,
    profile: dict,
    bypass_filters: bool,
    sweep_already_used: bool = False,
):
    """
    Evaluate M1 LTF Execution Refinement following a confirmed M5 Liquidity Sweep:
    M15 Bias -> M5 Sweep -> M1 CHoCH -> M1 Displacement FVG -> M1 Closed Retest & Directional Rejection
    -> Tight Sweep SL (<= max_sl_cap) -> M15 Opposing Target (>= 1.85R).
    Returns (signal_tuple_or_None, telemetry_info_dict).
    """
    if not profile.get("m1_ltf_enabled") or df_m1 is None or len(df_m1) < 25:
        return None, {}

    m1_eval = df_m1 if is_already_closed else df_m1.iloc[:-1]
    m1_eval = m1_eval.reset_index(drop=True)
    anchor_idx, m1_ext = _find_m1_sweep_anchor(eval_df, m1_eval, sweep_idx, is_bull)
    if anchor_idx < 2 or anchor_idx >= len(m1_eval) - 3:
        return None, {}

    slice_start = max(0, anchor_idx - 25)
    m1_slice = m1_eval.iloc[slice_start:].reset_index(drop=True)
    anchor_in_slice = anchor_idx - slice_start
    n1 = len(m1_slice)
    if anchor_in_slice < 2 or (n1 - 1 - anchor_in_slice) > 60 or n1 < 6:
        return None, {}

    true_extreme = min(float(sweep_extreme), m1_ext) if is_bull else max(float(sweep_extreme), m1_ext)
    m1_closes = m1_slice["close"].values
    for k in range(anchor_in_slice + 1, n1):
        if (is_bull and float(m1_closes[k]) < true_extreme) or ((not is_bull) and float(m1_closes[k]) > true_extreme):
            return None, {}

    digits = int(profile["digits"])
    wick_buf = float(profile["wick_buf"])
    max_sl_cap = float(profile["max_sl_cap"])
    min_dist = float(profile["min_dist"])
    sl_p_m1 = round(true_extreme - wick_buf, digits) if is_bull else round(true_extreme + wick_buf, digits)

    # S3: M1 CHoCH after sweep anchor
    m1_min_amp = float(profile.get("m1_min_amp", 5.0))
    sh_m1, sl_m1 = get_swing_points(m1_slice, n_left=2, n_right=2, min_amplitude=m1_min_amp)
    prior_pts = [p for p, idx in (sh_m1 if is_bull else sl_m1) if idx < anchor_in_slice]
    if not prior_pts:
        sh_m1, sl_m1 = get_swing_points(m1_slice, n_left=2, n_right=2, min_amplitude=0.0)
        prior_pts = [p for p, idx in (sh_m1 if is_bull else sl_m1) if idx < anchor_in_slice]

    m1_highs = m1_slice["high"].values
    m1_lows = m1_slice["low"].values
    if prior_pts:
        choch_lvl = float(prior_pts[-1])
    elif is_bull:
        choch_lvl = float(max(m1_highs[max(0, anchor_in_slice - 6):anchor_in_slice]))
    else:
        choch_lvl = float(min(m1_lows[max(0, anchor_in_slice - 6):anchor_in_slice]))

    choch_idx = -1
    for j in range(anchor_in_slice + 1, n1):
        if (is_bull and float(m1_closes[j]) > choch_lvl) or ((not is_bull) and float(m1_closes[j]) < choch_lvl):
            choch_idx = j
            break

    has_m1_choch = choch_idx >= 0 and (n1 - 1 - choch_idx) <= 25
    if not has_m1_choch:
        return None, {"progress": 2, "sl_price": sl_p_m1}

    # S4: M1 3-Candle Displacement FVG
    m1_fvgs = _detect_m1_fvgs(
        m1_slice,
        min_idx=anchor_in_slice,
        min_gap=float(profile.get("m1_min_fvg_gap", 2.20)),
        mit_tol=float(profile.get("m1_mit_tol", 1.00)),
        is_bullish=is_bull,
        extreme_price=true_extreme,
        sweep_margin=float(profile["sweep_margin"]),
        max_dist=float(profile["max_dist"]),
    )
    dir_pass = "PASS 🟢" if is_bull else "PASS 🔴"
    info = {
        "progress": 3 if not m1_fvgs else 4,
        "s3": f"{dir_pass} (M1 LTF CHoCH)",
        "choch_lvl": choch_lvl,
        "s4": f"{dir_pass} (M1 FVG)" if m1_fvgs else "WAITING ⚪ (Awaiting M1 FVG)",
        "fvg_zone": m1_fvgs[-1] if m1_fvgs else None,
        "sl_price": sl_p_m1,
    }
    if not m1_fvgs:
        return None, info

    # S5: Closed M1 FVG Retest (strictly after FVG creation bar)
    closed_m1 = m1_slice.iloc[-1]
    c_open = float(closed_m1["open"])
    c_high = float(closed_m1["high"])
    c_low = float(closed_m1["low"])
    c_close = float(closed_m1["close"])
    closed_m1_idx = n1 - 1
    m1_min_pen = float(profile.get("m1_min_pen_gap", 4.50))
    m1_close_tol = float(profile.get("m1_close_tol", 1.50))

    matched_fvg = None
    for low_b, high_b, fvg_idx in reversed(m1_fvgs):
        if closed_m1_idx <= fvg_idx:
            continue
        gap = max(0.0, high_b - low_b)
        pen = (0.35 * gap) if gap >= m1_min_pen else 0.0
        if is_bull:
            if c_low <= (high_b - pen) and c_low >= (low_b - wick_buf) and c_close >= (low_b - m1_close_tol):
                matched_fvg = (low_b, high_b, fvg_idx)
                break
        else:
            if c_high >= (low_b + pen) and c_high <= (high_b + wick_buf) and c_close <= (high_b + m1_close_tol):
                matched_fvg = (low_b, high_b, fvg_idx)
                break

    if not matched_fvg:
        return None, info

    fvg_low, fvg_high, _ = matched_fvg
    info["progress"] = 5
    info["s5"] = f"{dir_pass} (M1 FVG Retested)"

    # S6 & S7: Closed M1 Directional Rejection Candle
    range_floor = 0.01 if profile.get("is_high_point") else 0.0001
    c_range = max(range_floor, c_high - c_low)
    min_body = float(profile.get("m1_min_body_ratio", 0.25))
    if is_bull:
        body_ratio = (c_close - c_open) / c_range
        rej_ok = c_close > c_open and body_ratio >= min_body and c_close >= fvg_low
    else:
        body_ratio = (c_open - c_close) / c_range
        rej_ok = c_close < c_open and body_ratio >= min_body and c_close <= fvg_high

    if not rej_ok:
        info["progress"] = 6
        info["s6"] = "FAIL 🔴 (M1 Weak Body)"
        info["s7"] = "WAITING ⚪ (Awaiting M1 Reject Close)"
        return None, info

    info["progress"] = 7
    info["s6"] = f"{dir_pass} (M1 {'Bullish' if is_bull else 'Bearish'} Rejection)"
    info["s7"] = f"{dir_pass} (M1 Closed)"

    # S8: Structural Tight M1/M5 Sweep SL
    sl_dist = max(min_dist, (price - sl_p_m1) if is_bull else (sl_p_m1 - price))
    m1_chase = float(profile.get("m1_max_chase_dist", 12.0))
    m1_min_sl = float(profile.get("m1_min_sl_dist", 15.0))
    is_chasing = (price > (fvg_high + m1_chase)) if is_bull else (price < (fvg_low - m1_chase))
    is_sl_ok = ((m1_min_sl <= sl_dist <= max_sl_cap) and not is_chasing) or bypass_filters

    # S9: M15 Opposing Liquidity Target (>= 1.85R)
    tp_price, target_rrr = _compute_m15_opposing_target(is_bull, df_m15, price, sl_dist, False, profile=profile)
    is_target_ok = (target_rrr >= 1.85) or bypass_filters

    if is_sl_ok and is_target_ok and not sweep_already_used:
        wick_val = (min(c_open, c_close) - c_low) if is_bull else (c_high - max(c_open, c_close))
        q_score = compute_smc_signal_quality(
            target_rrr=target_rrr,
            sl_dist=sl_dist,
            max_sl_cap=max_sl_cap,
            rejection_wick_ratio=(wick_val / c_range),
            body_close_dir_ok=True,
            fvg_gap=(fvg_high - fvg_low),
            min_fvg_gap=float(profile.get("m1_min_fvg_gap", 2.20)),
            candles_since_choch=(n1 - 1 - choch_idx),
        )
        side = "BUY" if is_bull else "SELL"
        bias_word = "Bullish" if is_bull else "Bearish"
        op_sign = "-" if is_bull else "+"
        icon = "🟢" if is_bull else "🔴"
        cap_lbl = f"{max_sl_cap:.1f}pts"
        reason = (
            f"{icon} STRICT SMC PASSED (M1 LTF)! {side}: M15 {bias_word} + M5 Sweep ({true_extreme:.2f}) "
            f"+ M1 CHoCH ({choch_lvl:.2f}) + M1 Closed Rejection | SL: {sl_p_m1:.2f} (M1 {wick_buf:.2f} buf) "
            f"| M15 Target TP: {tp_price:.2f} ({target_rrr:.2f}R) | Quality: {q_score:.1f}"
        )
        logger.info("================================================================================")
        logger.info(f"{icon} [STRICT 9-CONDITION SMC M1-LTF REFINED {side} SIGNAL EXECUTED] 🚀")
        logger.info(
            f"{icon} S8 (Structural SL): M1/M5 Sweep ({true_extreme:.2f}) {op_sign} {wick_buf:.2f} = {sl_p_m1:.2f} "
            f"(Dist: {sl_dist:.2f}pts Tight M1 SL <= {cap_lbl} Cap)"
        )
        logger.info(f"{icon} S9 (M15 Liquidity TP): Executing {target_rrr:.2f}R TP @ {tp_price:.2f} (Quality: {q_score:.1f}/100)")
        logger.info("================================================================================")
        return (side, tp_price, sl_p_m1, sl_dist, reason), info

    if sweep_already_used:
        info["s8"] = "WAITING ⚪ (M5 Sweep Already Traded)"
    elif is_chasing:
        info["s8"] = f"FAIL 🔴 (M1 Late Chasing {price:.2f})"
    elif not is_sl_ok:
        info["s8"] = f"FAIL 🔴 (M1 SL {sl_dist:.2f}pts vs {m1_min_sl:.0f}-{max_sl_cap:.0f}pts)"
    else:
        info["s8"] = f"PASS 🟢 ({wick_buf:.2f}pts Buf - {sl_dist:.2f}pts Tight M1 SL <= {max_sl_cap:.1f}pts Cap)"

    info["s9"] = (
        f"FAIL 🔴 (M15 Target {target_rrr:.2f}R < 1.85R)"
        if not is_target_ok
        else f"PASS 🟢 ({target_rrr:.2f}R M15 Target - {profile['ob_buf']:.2f}pts Front-Run)"
    )
    info["tp"] = tp_price
    return None, info


def _try_fvg_refined_sl_rescue(
    is_bull: bool,
    price: float,
    raw_sl_dist: float,
    max_sl_cap: float,
    min_dist: float,
    digits: int,
    matched_fvg: tuple,
    closed_open: float,
    closed_close: float,
    closed_low: float,
    closed_high: float,
    prev_closed_row,
    candle_range: float,
    is_dir_close: bool,
    candles_since_choch: int,
    profile: dict,
):
    """
    S8 FVG-Defense Refined SL Rescue:
    When M5 sweep SL exceeds tight asset cap, anchor SL behind the defended FVG extreme
    + calibrated buffer if setup conviction and R:R constraints pass.
    """
    if raw_sl_dist <= max_sl_cap or not profile.get("fvg_refined_sl_enabled"):
        return None, raw_sl_dist, None

    fvg_low, fvg_high = float(matched_fvg[0]), float(matched_fvg[1])
    raw_ok = raw_sl_dist <= max_sl_cap * float(profile.get("fvg_refined_max_raw_mult", 2.0))
    body_ratio = abs(closed_close - closed_open) / max(1e-9, candle_range)
    min_body = float(profile.get("fvg_refined_min_body", 0.0))
    dir_ok = is_dir_close if min_body > 0 else True
    choch_ok = candles_since_choch <= int(profile.get("fvg_refined_max_choch_bars", 18))
    gap_ok = (fvg_high - fvg_low) >= float(profile["min_fvg_gap"]) * float(profile.get("fvg_refined_min_gap_mult", 1.0))

    if not (raw_ok and dir_ok and body_ratio >= min_body and choch_ok and gap_ok):
        return None, raw_sl_dist, None

    ref_buf = float(profile.get("refined_wick_buf", profile["wick_buf"]))
    if is_bull:
        fvg_extreme = min(fvg_low, closed_low, float(prev_closed_row["low"]))
        ref_sl = round(fvg_extreme - ref_buf, digits)
        ref_dist = max(min_dist, price - ref_sl)
    else:
        fvg_extreme = max(fvg_high, closed_high, float(prev_closed_row["high"]))
        ref_sl = round(fvg_extreme + ref_buf, digits)
        ref_dist = max(min_dist, ref_sl - price)

    min_ref_sl = float(profile.get("min_refined_sl_dist", min_dist))
    if min_ref_sl <= ref_dist <= max_sl_cap:
        return ref_sl, ref_dist, f"FVG-Refined {ref_buf:.2f} buf"
    return None, raw_sl_dist, None


def _evaluate_m5_directional_entry(
    *,
    is_bull: bool,
    eval_df: pd.DataFrame,
    df_m15: pd.DataFrame,
    sweep_idx: int,
    sweep_extreme: float,
    choch_lvl: float,
    candles_since_choch: int,
    matched_fvg: tuple,
    closed_open: float,
    closed_close: float,
    closed_low: float,
    closed_high: float,
    prev_closed_row,
    candle_range: float,
    wick_val: float,
    is_dir_close: bool,
    price: float,
    profile: dict,
    is_metals: bool,
    bypass_filters: bool,
    sweep_already_used: bool,
    sweep_key: str,
    used_m5_sweeps: set,
    sl_prefix: str,
    sl_suffix: str,
    cap_lbl: str,
    front_run_lbl: str,
    min_target_rrr: float,
):
    """
    Unified BUY/SELL M5 structural SL sizing, protected sweep anchor check, FVG SL rescue,
    M15 target evaluation, and telemetry generation. Returns (signal_or_None, step8_s, step9_s, sl_price, scan_tp).
    """
    digits = int(profile["digits"])
    wick_buf = float(profile["wick_buf"])
    min_dist = float(profile["min_dist"])
    max_sl_cap = float(profile["max_sl_cap"])
    m5_min_sl = float(profile.get("m5_min_sl_dist", 0.0))
    max_chase_dist = float(profile["max_chase_dist"])

    sl_price = round(sweep_extreme - wick_buf, digits) if is_bull else round(sweep_extreme + wick_buf, digits)
    sl_dist = max(min_dist, (price - sl_price) if is_bull else (sl_price - price))
    sl_mode_lbl = f"{wick_buf:.2f} buf"
    is_fvg_refined_sl = False

    if profile.get("protected_anchor_enabled"):
        prot_ext = find_protected_sweep_extreme(eval_df, sweep_idx, sweep_extreme, is_bullish=is_bull, lookback=12)
        prot_sl = round(prot_ext - wick_buf, digits) if is_bull else round(prot_ext + wick_buf, digits)
        prot_dist = max(min_dist, (price - prot_sl) if is_bull else (prot_sl - price))
        if prot_dist > sl_dist and prot_dist <= max_sl_cap:
            sl_price = prot_sl
            sl_dist = prot_dist
            sl_mode_lbl = f"Protected {wick_buf:.2f} buf"

    fvg_low, fvg_high = matched_fvg
    is_chasing = (price > (fvg_high + max_chase_dist)) if is_bull else (price < (fvg_low - max_chase_dist))

    if not is_chasing and sl_dist > max_sl_cap:
        res_sl, res_dist, res_lbl = _try_fvg_refined_sl_rescue(
            is_bull=is_bull, price=price, raw_sl_dist=sl_dist, max_sl_cap=max_sl_cap, min_dist=min_dist, digits=digits,
            matched_fvg=matched_fvg, closed_open=closed_open, closed_close=closed_close,
            closed_low=closed_low, closed_high=closed_high, prev_closed_row=prev_closed_row,
            candle_range=candle_range, is_dir_close=is_dir_close,
            candles_since_choch=candles_since_choch, profile=profile,
        )
        if res_sl is not None:
            sl_price, sl_dist, sl_mode_lbl = res_sl, res_dist, res_lbl
            is_fvg_refined_sl = True

    tp_price, target_rrr = _compute_m15_opposing_target(is_bull, df_m15, price, sl_dist, is_metals, profile=profile)
    is_sl_ok = ((m5_min_sl <= sl_dist <= max_sl_cap) and not is_chasing) or bypass_filters
    is_target_ok = (target_rrr >= min_target_rrr) or bypass_filters

    if is_sl_ok and is_target_ok and not sweep_already_used:
        _record_used_sweep(used_m5_sweeps, sweep_key)
        q_score = compute_smc_signal_quality(
            target_rrr=target_rrr,
            sl_dist=sl_dist,
            max_sl_cap=max_sl_cap,
            rejection_wick_ratio=(wick_val / candle_range),
            body_close_dir_ok=is_dir_close,
            fvg_gap=(fvg_high - fvg_low),
            min_fvg_gap=profile["min_fvg_gap"],
            candles_since_choch=candles_since_choch,
        )
        side = "BUY" if is_bull else "SELL"
        icon = "🟢" if is_bull else "🔴"
        bias_word = "Bullish" if is_bull else "Bearish"
        op_sign = "-" if is_bull else "+"
        ext_lbl = "Low" if is_bull else "High"
        reason = (
            f"{icon} STRICT SMC PASSED! {side}: M15 {bias_word} + M5 Sweep ({sweep_extreme:.2f}) "
            f"+ CHoCH ({choch_lvl:.2f}) + Closed Rejection | SL: {sl_price:.2f} ({sl_mode_lbl}) "
            f"| M15 Target TP: {tp_price:.2f} ({target_rrr:.2f}R) | Quality: {q_score:.1f}"
        )
        logger.info("================================================================================")
        logger.info(f"{icon} [STRICT 9-CONDITION SMC {side} SIGNAL EXECUTED] 🚀")
        sl_desc = "FVG-Refined SL" if is_fvg_refined_sl else f"Sweep {ext_lbl} ({sweep_extreme:.2f}) {op_sign} {wick_buf:.2f}"
        logger.info(f"{icon} S8 (Structural SL): {sl_desc} = {sl_price:.2f} (Dist: {sl_prefix}{sl_dist:.2f}{sl_suffix} <= {cap_lbl} Cap)")
        logger.info(f"{icon} S9 (M15 Liquidity TP): Executing {target_rrr:.2f}R TP @ {tp_price:.2f} (Quality: {q_score:.1f}/100)")
        logger.info("================================================================================")
        return (side, tp_price, sl_price, sl_dist, reason), None, None, sl_price, tp_price

    if sweep_already_used:
        step8_s = "WAITING ⚪ (M5 Sweep Already Traded)"
    elif not is_sl_ok:
        if is_chasing:
            cmp_sym, ref_b = (">", fvg_high) if is_bull else ("<", fvg_low)
            step8_s = f"FAIL 🔴 (Late Chasing {price:.2f} {cmp_sym} FVG {ref_b:.2f})"
        elif sl_dist < m5_min_sl:
            step8_s = f"FAIL 🔴 (Noise SL {sl_prefix}{sl_dist:.2f}{sl_suffix} < Min {sl_prefix}{m5_min_sl:.2f}{sl_suffix})"
        else:
            step8_s = f"FAIL 🔴 (SL {sl_prefix}{sl_dist:.2f}{sl_suffix} > {cap_lbl} Cap)"
    elif is_fvg_refined_sl:
        step8_s = f"PASS 🟢 (FVG-Refined {sl_prefix}{sl_dist:.2f}{sl_suffix} <= {cap_lbl} Cap)"
    else:
        step8_s = f"PASS 🟢 ({wick_buf:.2f} Buf - {sl_prefix}{sl_dist:.2f}{sl_suffix} SL)"

    step9_s = (
        f"FAIL 🔴 (M15 Target {target_rrr:.2f}R < {min_target_rrr:.2f}R)"
        if not is_target_ok
        else f"PASS 🟢 ({target_rrr:.2f}R M15 Target - {front_run_lbl} Front-Run)"
    )
    return None, step8_s, step9_s, sl_price, tp_price


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
    df_m1: pd.DataFrame = None,
    used_m5_sweeps: set = None,
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
    m5_candidate_sl = 0.0
    front_run_lbl = "$1.10" if is_metals else (f"{profile['ob_buf']:.2f}pts" if is_high_pt else "3.5p")
    min_target_rrr = 1.85

    sell_sweep_key = _get_sweep_key(True, sell_sweep_idx, sweep_low_price, eval_df) if has_sell_sweep else None
    buy_sweep_key = _get_sweep_key(False, buy_sweep_idx, sweep_high_price, eval_df) if has_buy_sweep else None
    sell_sweep_used = bool(sell_sweep_key and used_m5_sweeps is not None and sell_sweep_key in used_m5_sweeps)
    buy_sweep_used = bool(buy_sweep_key and used_m5_sweeps is not None and buy_sweep_key in used_m5_sweeps)

    # ── 1. BUY SIGNAL EVALUATION (UNIFIED STRICT SMC + PROTECTED ANCHOR + RESCUE) ──
    if is_m15_bullish and has_sell_sweep and has_bull_choch and (len(zones_bull['bullish_fvg']) > 0) and in_bull_fvg and p5_buy_rejection:
        sig_out, custom_step8_s, custom_step9_s, m5_candidate_sl, scan_tp = _evaluate_m5_directional_entry(
            is_bull=True, eval_df=eval_df, df_m15=df_m15,
            sweep_idx=sell_sweep_idx, sweep_extreme=sweep_low_price, choch_lvl=bull_choch_lvl,
            candles_since_choch=candles_since_bull_choch, matched_fvg=matched_bull_fvg,
            closed_open=closed_open, closed_close=closed_close, closed_low=closed_low, closed_high=closed_high,
            prev_closed_row=prev_closed_row, candle_range=bull_candle_range, wick_val=bull_lower_wick,
            is_dir_close=bull_is_green, price=price, profile=profile, is_metals=is_metals,
            bypass_filters=bypass_filters, sweep_already_used=sell_sweep_used, sweep_key=sell_sweep_key,
            used_m5_sweeps=used_m5_sweeps, sl_prefix=sl_prefix, sl_suffix=sl_suffix,
            cap_lbl=cap_lbl, front_run_lbl=front_run_lbl, min_target_rrr=min_target_rrr,
        )
        if sig_out is not None:
            return sig_out

    # ── 2. SELL SIGNAL EVALUATION (UNIFIED STRICT SMC + PROTECTED ANCHOR + RESCUE) ──
    if is_m15_bearish and has_buy_sweep and has_bear_choch and (len(zones_bear['bearish_fvg']) > 0) and in_bear_fvg and p5_sell_rejection:
        sig_out, custom_step8_s, custom_step9_s, m5_candidate_sl, scan_tp = _evaluate_m5_directional_entry(
            is_bull=False, eval_df=eval_df, df_m15=df_m15,
            sweep_idx=buy_sweep_idx, sweep_extreme=sweep_high_price, choch_lvl=bear_choch_lvl,
            candles_since_choch=candles_since_bear_choch, matched_fvg=matched_bear_fvg,
            closed_open=closed_open, closed_close=closed_close, closed_low=closed_low, closed_high=closed_high,
            prev_closed_row=prev_closed_row, candle_range=bear_candle_range, wick_val=bear_upper_wick,
            is_dir_close=bear_is_red, price=price, profile=profile, is_metals=is_metals,
            bypass_filters=bypass_filters, sweep_already_used=buy_sweep_used, sweep_key=buy_sweep_key,
            used_m5_sweeps=used_m5_sweeps, sl_prefix=sl_prefix, sl_suffix=sl_suffix,
            cap_lbl=cap_lbl, front_run_lbl=front_run_lbl, min_target_rrr=min_target_rrr,
        )
        if sig_out is not None:
            return sig_out

    # ── 2B. INDICES M1 LTF EXECUTION REFINEMENT (M15 Bias -> M5 Sweep -> M1 CHoCH + FVG + Closed Rejection) ──
    m1_info = {}
    if profile.get("m1_ltf_enabled") and df_m1 is not None and len(df_m1) >= 25:
        if is_m15_bullish and has_sell_sweep:
            m1_sig, m1_info = _evaluate_m1_ltf_refinement(
                True, df_m15, eval_df, df_m1, sell_sweep_idx, sweep_low_price,
                price, is_already_closed, profile, bypass_filters, sweep_already_used=sell_sweep_used,
            )
            if m1_sig is not None:
                _record_used_sweep(used_m5_sweeps, sell_sweep_key)
                return m1_sig
        elif is_m15_bearish and has_buy_sweep:
            m1_sig, m1_info = _evaluate_m1_ltf_refinement(
                False, df_m15, eval_df, df_m1, buy_sweep_idx, sweep_high_price,
                price, is_already_closed, profile, bypass_filters, sweep_already_used=buy_sweep_used,
            )
            if m1_sig is not None:
                _record_used_sweep(used_m5_sweeps, buy_sweep_key)
                return m1_sig

    # ── 3. SCANNER LOGGING (ALL 9 STRICT STEPS INDIVIDUALLY DISPLAYED — NO '|' INSIDE VALUES) ──
    if is_m15_bullish:
        step1_s = "BULLISH 🟢"
        step2_s = "PASS 🟢 (Sell-Side Sweep)" if has_sell_sweep else "WAITING ⚪ (Awaiting Fresh Sweep)"
        step3_s = "PASS 🟢 (Bullish CHoCH)" if has_bull_choch else "WAITING ⚪ (Awaiting Fresh CHoCH)"
        step4_s = "PASS 🟢 (Displacement FVG)" if (len(zones_bull['bullish_fvg']) > 0) else "WAITING ⚪ (Awaiting Displacement FVG)"
        step5_s = "PASS 🟢 (FVG Retested)" if in_bull_fvg else "WAITING ⚪ (Awaiting FVG Retest)"
        step6_s = "PASS 🟢 (Bullish Rejection)" if p5_buy_rejection else ("WAITING ⚪ (Awaiting Rejection Candle)" if in_bull_fvg else "WAITING ⚪ (Awaiting Retest)")
        step7_s = "PASS 🟢 (Candle Closed)" if p5_buy_rejection else "WAITING ⚪ (Awaiting Candle Close)"
        m5_step = 7 if p5_buy_rejection else (5 if in_bull_fvg else (4 if len(zones_bull['bullish_fvg']) > 0 else (3 if has_bull_choch else (2 if has_sell_sweep else 1))))
    elif is_m15_bearish:
        step1_s = "BEARISH 🔴"
        step2_s = "PASS 🔴 (Buy-Side Sweep)" if has_buy_sweep else "WAITING ⚪ (Awaiting Fresh Sweep)"
        step3_s = "PASS 🔴 (Bearish CHoCH)" if has_bear_choch else "WAITING ⚪ (Awaiting Fresh CHoCH)"
        step4_s = "PASS 🔴 (Displacement FVG)" if (len(zones_bear['bearish_fvg']) > 0) else "WAITING ⚪ (Awaiting Displacement FVG)"
        step5_s = "PASS 🔴 (FVG Retested)" if in_bear_fvg else "WAITING ⚪ (Awaiting FVG Retest)"
        step6_s = "PASS 🔴 (Bearish Rejection)" if p5_sell_rejection else ("WAITING ⚪ (Awaiting Rejection Candle)" if in_bear_fvg else "WAITING ⚪ (Awaiting Retest)")
        step7_s = "PASS 🔴 (Candle Closed)" if p5_sell_rejection else "WAITING ⚪ (Awaiting Candle Close)"
        m5_step = 7 if p5_sell_rejection else (5 if in_bear_fvg else (4 if len(zones_bear['bearish_fvg']) > 0 else (3 if has_bear_choch else (2 if has_buy_sweep else 1))))
    else:
        step1_s = "NEUTRAL ⚪"
        step2_s = "WAITING ⚪ (M15 Neutral)"
        step3_s = "WAITING ⚪ (M15 Neutral)"
        step4_s = "WAITING ⚪ (M15 Neutral)"
        step5_s = "WAITING ⚪ (M15 Neutral)"
        step6_s = "WAITING ⚪ (M15 Neutral)"
        step7_s = "WAITING ⚪ (M15 Neutral)"
        m5_step = 0

    use_m1_tel = bool(
        m1_info
        and (
            m1_info.get("progress", 0) > m5_step
            or (custom_step8_s is not None and "FAIL" in custom_step8_s and m1_info.get("progress", 0) >= 3)
        )
    )
    if use_m1_tel:
        step3_s = m1_info.get("s3", step3_s)
        step4_s = m1_info.get("s4", step4_s)
        if "s5" in m1_info:
            step5_s = m1_info["s5"]
        elif m1_info.get("progress", 0) >= 4:
            step5_s = "WAITING ⚪ (Awaiting M1 FVG Retest)"
        if "s6" in m1_info:
            step6_s = m1_info["s6"]
        if "s7" in m1_info:
            step7_s = m1_info["s7"]
        if "s8" in m1_info:
            custom_step8_s = m1_info["s8"]
        if "s9" in m1_info:
            custom_step9_s = m1_info["s9"]
        if m1_info.get("tp", 0) > 0:
            scan_tp = float(m1_info["tp"])

    # S8: Structural SL Placement
    if custom_step8_s is not None:
        step8_s = custom_step8_s
    elif profile.get("m1_ltf_enabled") and m1_info and m1_info.get("sl_price", 0) > 0:
        m1_d = abs(price - float(m1_info["sl_price"]))
        if m1_d <= max_sl_cap:
            step8_s = f"PASS 🟢 ({buf_lbl} Buf - {m1_d:.2f}pts Tight M1 SL <= {cap_lbl} Cap)"
        else:
            step8_s = f"PASS 🟢 ({buf_lbl} Buf - {cap_lbl} Cap)"
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
        actual_choch_p = (
            float(m1_info["choch_lvl"]) if (use_m1_tel and m1_info.get("choch_lvl", 0) > 0)
            else (bear_choch_lvl if has_bear_choch else 0.0)
        )
    elif is_m15_bullish:
        actual_sweep_p = sweep_low_price if has_sell_sweep else 0.0
        actual_choch_p = (
            float(m1_info["choch_lvl"]) if (use_m1_tel and m1_info.get("choch_lvl", 0) > 0)
            else (bull_choch_lvl if has_bull_choch else 0.0)
        )
    else:
        actual_sweep_p = sweep_low_price if has_sell_sweep else (sweep_high_price if has_buy_sweep else 0.0)
        actual_choch_p = bull_choch_lvl if has_bull_choch else (bear_choch_lvl if has_bear_choch else 0.0)

    active_sl_p = 0.0
    if use_m1_tel and m1_info.get("sl_price", 0) > 0:
        active_sl_p = float(m1_info["sl_price"])
    elif m5_candidate_sl > 0:
        active_sl_p = float(m5_candidate_sl)
    elif is_m15_bullish and has_sell_sweep:
        active_sl_p = round(sweep_low_price - wick_buf, digits)
    elif is_m15_bearish and has_buy_sweep:
        active_sl_p = round(sweep_high_price + wick_buf, digits)

    tp_str = f" | OpposingTp: {scan_tp:.{digits}f}" if scan_tp > 0 else ""
    sl_str = f" | SlPrice: {active_sl_p:.{digits}f}" if active_sl_p > 0 else ""
    scan_msg = (
        f"Scanning Strict 9-Condition SMC | S1(M15): {step1_s} | S2(Sweep): {step2_s} "
        f"| S3(CHoCH): {step3_s} | S4(Displacement FVG): {step4_s} | S5(Retest): {step5_s} "
        f"| S6(Rejection): {step6_s} | S7(Closed): {step7_s} | S8(SL Buf): {step8_s} "
        f"| S9(Target): {step9_s} | SweepPrice: {actual_sweep_p:.{digits}f} | ChochPrice: {actual_choch_p:.{digits}f}{tp_str}{sl_str}"
    )
    return "NONE", None, None, 0.0, scan_msg
