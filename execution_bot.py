import MetaTrader5 as mt5
import datetime
import logging
import os
import time
from database import log_trade_entry, log_trade_exit, get_connection, utc_now_naive

logger = logging.getLogger("SMC_Forex_Bot")
MAGIC_NUMBER = 992026           # Unique magic number for Jane Street system trades

_BROKER_UTC_OFFSET_CACHE = {"offset_sec": None, "last_tick_time": None}


def _detect_mt5_broker_offset_sec(symbol=None):
    """Detects MT5 broker server timezone offset in seconds vs UTC, caching live readings."""
    env_off = os.getenv("MT5_SERVER_OFFSET_HOURS")
    if env_off is not None and str(env_off).strip() != "":
        try:
            return int(round(float(env_off) * 3600))
        except Exception:
            pass

    now_utc_ts = time.time()
    candidates = []
    for sym in (symbol, "XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "BTCUSD"):
        if sym and sym not in candidates:
            candidates.append(sym)

    tick_times = []
    for sym in candidates:
        try:
            tk = mt5.symbol_info_tick(sym)
            if tk and getattr(tk, "time", 0) and float(tk.time) > 1_000_000_000:
                tick_times.append(float(tk.time))
        except Exception:
            pass

    if tick_times:
        ref_tick_time = max(tick_times)
        diff = ref_tick_time - now_utc_ts
        prev_tick = _BROKER_UTC_OFFSET_CACHE.get("last_tick_time")
        prev_off = _BROKER_UTC_OFFSET_CACHE.get("offset_sec")
        tick_advanced = (prev_tick is not None and ref_tick_time > prev_tick)

        if -43200 <= diff <= 50400 and (tick_advanced or prev_off is None):
            utc_now = datetime.datetime.now(datetime.timezone.utc)
            utc_wd, utc_hr = utc_now.weekday(), utc_now.hour
            is_fx_weekend = (utc_wd == 5) or (utc_wd == 4 and utc_hr >= 22) or (utc_wd == 6 and utc_hr < 22)
            if tick_advanced or not is_fx_weekend:
                est = int(round(diff / 1800.0) * 1800)
                _BROKER_UTC_OFFSET_CACHE["offset_sec"] = est
                _BROKER_UTC_OFFSET_CACHE["last_tick_time"] = ref_tick_time
                return est
        elif prev_tick is None or ref_tick_time > prev_tick:
            _BROKER_UTC_OFFSET_CACHE["last_tick_time"] = ref_tick_time

    if _BROKER_UTC_OFFSET_CACHE["offset_sec"] is not None:
        return _BROKER_UTC_OFFSET_CACHE["offset_sec"]
    return 0


def mt5_epoch_to_utc_naive(epoch_ts, symbol=None):
    """Converts MT5 broker-server-shifted epoch timestamp into a true naive UTC datetime."""
    if epoch_ts is None or float(epoch_ts) <= 0:
        return utc_now_naive()
    offset_sec = _detect_mt5_broker_offset_sec(symbol)
    utc_epoch = float(epoch_ts) - offset_sec
    return datetime.datetime.fromtimestamp(utc_epoch, datetime.timezone.utc).replace(tzinfo=None)

def is_retcode_success(res):
    """Returns True if MT5 order_send result (or raw int retcode) represents a successful fill."""
    if res is None:
        return False
    if isinstance(res, int):
        return res in [mt5.TRADE_RETCODE_DONE, 10008, 10009, 0]
    retcode = getattr(res, 'retcode', None)
    comment = str(getattr(res, 'comment', '') or '').lower()
    if retcode in [mt5.TRADE_RETCODE_DONE, 10008, 10009, 0]:
        return True
    if comment in ["done", "request executed", "order executed"]:
        return True
    return False

def send_order(symbol, order_type, price, volume, sl, tp, comment):
    """Submits order to MT5. Automatically handles FOK vs IOC vs RETURN filling modes and live price updates."""
    # Ensure symbol is active and selected in MT5 Market Watch
    mt5.symbol_select(symbol, True)
    
    # Always refresh live market tick price to prevent 10021 (No prices / Off quotes)
    tick = mt5.symbol_info_tick(symbol)
    if tick:
        live_p = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
        if live_p > 0:
            price = live_p
            
    # Dynamically detect broker's exact supported filling mode and tick precision for this symbol
    info = mt5.symbol_info(symbol)
    digits = int(info.digits) if (info and getattr(info, "digits", None) is not None) else None
    if digits is not None:
        price = round(float(price), digits)
        if sl and float(sl) > 0:
            sl = round(float(sl), digits)
        if tp and float(tp) > 0:
            tp = round(float(tp), digits)
    filling_modes = []
    if info and hasattr(info, "filling_mode"):
        fm = info.filling_mode
        # Bitmask check: Bit 0 (1)=FOK, Bit 1 (2)=IOC, Bit 2 (4)=RETURN
        if fm & 1:
            filling_modes.append(mt5.ORDER_FILLING_FOK)
        if fm & 2:
            filling_modes.append(mt5.ORDER_FILLING_IOC)
        if fm & 4:
            filling_modes.append(mt5.ORDER_FILLING_RETURN)
            
    if not filling_modes:
        filling_modes = [mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_RETURN]

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": MAGIC_NUMBER,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
    }
    
    result = None
    for mode in filling_modes:
        # Re-fetch ultra-fresh tick price before sending to eliminate retcode 10021 (No prices)
        tick = mt5.symbol_info_tick(symbol)
        if tick:
            fresh_p = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
            if fresh_p > 0:
                request["price"] = round(float(fresh_p), digits) if digits is not None else fresh_p

        request["type_filling"] = mode
        result = mt5.order_send(request)
        
        if result is None:
            logger.error(f"MT5 order_send returned None for mode {mode}. Error: {mt5.last_error()}")
            continue
            
        if is_retcode_success(result):
            logger.info(f"Order filled successfully using mode {mode} (retcode={result.retcode}, comment='{result.comment}')")
            return result
            
        # Check if volume is invalid and auto-correct to broker volume_min
        if result.retcode == 10014:
            info = mt5.symbol_info(symbol)
            if info:
                corrected_vol = info.volume_min
                logger.warning(f"[VOLUME HEAL] Retrying order for {symbol} with broker min volume: {corrected_vol}")
                request["volume"] = corrected_vol
                res_retry = mt5.order_send(request)
                if is_retcode_success(res_retry):
                    logger.info(f"Order filled successfully after volume auto-correction.")
                    return res_retry
            logger.error(f"Order rejected due to invalid volume: {result.comment}")
            return None
            
        # Check if stops are invalid (e.g. SL too close for stock CFD) and retry with sl=0.0
        if result.retcode == 10016:
            logger.warning(f"[STOPS HEAL] Retrying order for {symbol} with sl=0.0 due to invalid broker stops level: {result.comment}")
            request["sl"] = 0.0
            res_retry = mt5.order_send(request)
            if is_retcode_success(res_retry):
                logger.info(f"Order filled successfully after stops auto-correction.")
                return res_retry
            logger.error(f"Order rejected due to invalid stops: {result.comment}")
            return None

        # Check if error is due to insufficient margin (10019 "No money")
        comment_str = result.comment or ""
        if result.retcode == 10019 or "No money" in comment_str or "not enough money" in comment_str.lower():
            info = mt5.symbol_info(symbol)
            acc = mt5.account_info()
            min_vol = info.volume_min if info else 0.01
            step_vol = info.volume_step if info else 0.01
            free_m = acc.margin_free if acc else 0.0
            req_m = mt5.order_calc_margin(request["action"], symbol, request["volume"], price) or 1.0
            if req_m > 0 and free_m > 0:
                # If part of a 3-part trade (JS_TP1/2/3), use 26% of free margin per part (78% total), else 80% max margin per Blue Guardian rules
                margin_fraction = 0.26 if "JS_TP" in str(comment) else 0.80
                scaled_vol = request["volume"] * (free_m * margin_fraction / req_m)
                scaled_vol = max(min_vol, round(scaled_vol / step_vol) * step_vol)
                scaled_vol = round(scaled_vol, 2)
                if scaled_vol < request["volume"]:
                    logger.warning(f"[MARGIN HEAL] Insufficient margin ({result.comment}). Auto-scaling volume {request['volume']} -> {scaled_vol}")
                    request["volume"] = scaled_vol
                    res_retry = mt5.order_send(request)
                    if is_retcode_success(res_retry):
                        logger.info(f"Order filled successfully after margin auto-scaling.")
                        return res_retry
            logger.error(f"Order rejected due to insufficient margin: {result.comment}")
            return None

        # Check if the error is due to disabled auto-trading on client or server
        if "AutoTrading disabled" in comment_str or result.retcode in [10022, 10026, 10027, 10034]:
            logger.error(f"⚠️ [ALGO TRADING DISABLED] Order rejected (retcode={result.retcode}): Enable 'Algo Trading' button in MT5 top toolbar! Details: {result.comment}")
            return None
            
        logger.warning(f"Order mode {mode} failed (retcode={result.retcode}): {result.comment}. Trying next filling mode...")
        
    if result:
        logger.error(f"Order failed after trying all filling modes: retcode={result.retcode} ({result.comment})")
    return None


def execute_three_part_trade(symbol, is_long, entry_price, sl_price, total_lots, tp1, tp2, tp3, signal_id=None):
    """
    Executes a trade split into three parts (TP1, TP2, TP3) for scaling out.
    Also logs the trade entry to the PostgreSQL database.
    Returns (success_boolean, total_filled_lots).
    """
    order_type = mt5.ORDER_TYPE_BUY if is_long else mt5.ORDER_TYPE_SELL
    part_lots = round(total_lots / 3.0, 2)
    
    # Ensure lot size satisfies broker minimums and volume step (e.g. 1.0 share step for Stock CFDs)
    from risk_safeguards import round_volume
    part_lots = round_volume(symbol, part_lots)

    logger.info(f"Executing 3-part quantitative trade | Total Lots: {total_lots} | Part Lots: {part_lots}")
    logger.info(f"Entry: {entry_price:.5f} | SL: {sl_price:.5f}")
    logger.info(f"TP1: {tp1:.5f} | TP2: {tp2:.5f} | TP3: {tp3:.5f}")

    parts = [("TP1", tp1), ("TP2", tp2), ("TP3", tp3)]
    success = False
    total_filled_lots = 0.0

    for part_name, tp_val in parts:
        # Pass the actual tp_val so the MT5 broker server executes the target exit reliably!
        res = send_order(symbol, order_type, entry_price, part_lots, sl_price, tp_val, f"JS_{part_name}")
        if is_retcode_success(res):
            ticket = res.order
            filled_lots = getattr(res, 'volume', part_lots)
            if filled_lots <= 0:
                filled_lots = part_lots
            filled_lots = round_volume(symbol, filled_lots)
            total_filled_lots += filled_lots

            if filled_lots < part_lots:
                logger.warning(f"[MARGIN AUTO-RESCALE] {part_name} volume was auto-scaled from {part_lots} to {filled_lots}. Adjusting subsequent TP parts to {filled_lots} lots.")
                part_lots = filled_lots

            log_trade_entry(
                ticket=ticket,
                symbol=symbol,
                order_type="BUY" if is_long else "SELL",
                lots=filled_lots,
                entry_price=entry_price,
                entry_time=utc_now_naive(),
                comment=f"JaneStreet {part_name}",
                signal_id=signal_id
            )
            logger.info(f"🟢 [ENTRY SUCCESS] Ticket #{ticket} | Symbol: {symbol} | Type: {'BUY' if is_long else 'SELL'} | {part_name} Volume: {filled_lots} Lots | Target TP: {tp_val:.5f} | SL: {sl_price:.5f}")
            success = True
        else:
            err_msg = res.comment if res else "No response"
            logger.error(f"❌ [ENTRY FAILED] {part_name} Order Execution Error: {err_msg}")

            
    return success, total_filled_lots

def execute_three_part_hedge_trade(symbol, is_long, entry_price, total_lots, sl_price=0.0, tp_price=0.0, signal_id=None):
    """
    Executes Leg B hedge split into 3 matching hedge orders (JS_HEDGE_TP1, JS_HEDGE_TP2, JS_HEDGE_TP3)
    for 1:1 order mapping architecture with Hard Broker Stop Loss protection on MT5.
    """
    order_type = mt5.ORDER_TYPE_BUY if is_long else mt5.ORDER_TYPE_SELL
    part_lots = round(total_lots / 3.0, 2)
    from risk_safeguards import round_volume
    part_lots = round_volume(symbol, part_lots)
    
    parts = ["TP1", "TP2", "TP3"]
    success = False
    total_filled_lots = 0.0

    for part_name in parts:
        res = send_order(symbol, order_type, entry_price, part_lots, sl_price, tp_price, f"JS_HEDGE_{part_name}")
        if is_retcode_success(res):
            ticket = res.order
            filled_lots = getattr(res, 'volume', part_lots)
            if filled_lots <= 0:
                filled_lots = part_lots
            filled_lots = round_volume(symbol, filled_lots)
            total_filled_lots += filled_lots

            log_trade_entry(
                ticket=ticket,
                symbol=symbol,
                order_type="BUY" if is_long else "SELL",
                lots=filled_lots,
                entry_price=entry_price,
                entry_time=utc_now_naive(),
                comment=f"JaneStreet HEDGE_{part_name}",
                signal_id=signal_id
            )
            logger.info(f"🟢 [HEDGE ENTRY SUCCESS] Ticket #{ticket} | Symbol: {symbol} | Type: {'BUY' if is_long else 'SELL'} | HEDGE_{part_name} Volume: {filled_lots} Lots")
            success = True
        else:
            err_msg = res.comment if res else "No response"
            logger.error(f"❌ [HEDGE ENTRY FAILED] HEDGE_{part_name} Order Execution Error: {err_msg}")

    return success, total_filled_lots

def close_all_positions(symbol, comment_filter="JS_"):
    """Closes all active positions matching the magic number and symbol."""
    if symbol == "ALL" or not symbol:
        positions = mt5.positions_get()
    else:
        positions = mt5.positions_get(symbol=symbol)
        if not positions:
            from data_ingestion import resolve_broker_symbol
            resolved = resolve_broker_symbol(symbol)
            if resolved != symbol:
                positions = mt5.positions_get(symbol=resolved)
        if not positions:
            all_pos = mt5.positions_get()
            if all_pos:
                base_sym = symbol.split('.')[0].upper()
                positions = [p for p in all_pos if p.symbol.split('.')[0].upper() == base_sym]
        
    if not positions:
        return
        
    filling_modes = [
        mt5.ORDER_FILLING_FOK,
        mt5.ORDER_FILLING_IOC,
        mt5.ORDER_FILLING_RETURN
    ]

    for pos in positions:
        if pos.magic == MAGIC_NUMBER and comment_filter in pos.comment:
            order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            
            # Fetch latest price for the specific symbol
            tick = mt5.symbol_info_tick(pos.symbol)
            if tick is None:
                continue
            price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": order_type,
                "position": pos.ticket,
                "price": price,
                "deviation": 10,
                "magic": MAGIC_NUMBER,
                "comment": "JS Drawdown Emergency Exit",
                "type_time": mt5.ORDER_TIME_GTC,
            }
            
            closed_ok = False
            for mode in filling_modes:
                request["type_filling"] = mode
                res = mt5.order_send(request)
                if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                    logger.info(f"Emergency closed position ticket: {pos.ticket} using mode {mode}")
                    check_closed_trades(pos.symbol)
                    closed_ok = True
                    break
            if not closed_ok:
                err_msg = res.comment if res else "No response"
                logger.error(f"Failed to close position ticket {pos.ticket}: {err_msg}")

def _sync_open_sl_to_db(ticket, new_sl):
    """Immediately updates SL for an OPEN ticket in PostgreSQL so dashboard/chart reflect Breakeven."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE trades SET sl = %s WHERE ticket = %s AND status = 'OPEN'", (float(new_sl), int(ticket)))
        conn.commit()
        cur.close()
    except Exception as e:
        logger.debug(f"Could not sync updated SL to DB for ticket {ticket}: {e}")
    finally:
        if conn:
            conn.close()


def modify_position_sl(ticket, symbol, new_sl):
    """
    Modifies the Stop Loss of an active MT5 position to new_sl (e.g. Breakeven / Entry +/- fee buffer).
    Enforces broker digits rounding, stops-level safety, and strictly forward SL ratcheting.
    """
    try:
        mt5.symbol_select(symbol, True)
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            all_pos = mt5.positions_get(symbol=symbol)
            if all_pos:
                positions = [p for p in all_pos if p.ticket == ticket]
        if not positions:
            logger.warning(f"Could not find position ticket {ticket} ({symbol}) to modify SL.")
            return False

        pos = positions[0]
        info = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)
        is_metals = any(m in symbol.upper() for m in ("XAU", "GOLD", "XAG", "SILVER"))
        digits = int(info.digits) if (info and getattr(info, "digits", None) is not None) else (2 if is_metals else 5)
        point = float(info.point) if (info and getattr(info, "point", 0.0)) else (10 ** -digits)
        stops_level = float(getattr(info, "trade_stops_level", 0) or 0) if info else 0.0
        min_stop_dist = stops_level * point + point

        rounded_sl = round(float(new_sl), digits)
        curr_sl = float(getattr(pos, "sl", 0.0) or 0.0)
        tp_val = round(float(pos.tp), digits) if (getattr(pos, "tp", 0.0) or 0.0) > 0 else 0.0
        pos_type = int(getattr(pos, "type", 0))

        eps = point * 0.5
        if pos_type == mt5.ORDER_TYPE_BUY:
            if curr_sl > 0.0 and rounded_sl <= curr_sl + eps:
                return False
            if tick and getattr(tick, "bid", 0.0) > 0 and rounded_sl > tick.bid - min_stop_dist:
                return False
        else:
            if curr_sl > 0.0 and rounded_sl >= curr_sl - eps:
                return False
            if tick and getattr(tick, "ask", 0.0) > 0 and rounded_sl < tick.ask + min_stop_dist:
                return False

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "symbol": symbol,
            "sl": rounded_sl,
            "tp": tp_val,
            "magic": MAGIC_NUMBER,
        }
        res = mt5.order_send(request)
        if is_retcode_success(res):
            logger.info(f"🛡️ [BREAKEVEN SL ACTIVATED] Moved Stop Loss for ticket {ticket} ({symbol}) to {rounded_sl:.{digits}f}")
            _sync_open_sl_to_db(ticket, rounded_sl)
            return True
        else:
            err_c = res.comment if res else mt5.last_error()
            logger.error(f"Failed to modify SL for ticket {ticket}: {err_c}")
            return False
    except Exception as e:
        logger.error(f"Error modifying SL for ticket {ticket}: {e}")
        return False


def apply_pure_breakeven_guard(active_positions, floating_profit=0.0, peak_floating_profit=0.0, modify_fn=None):
    """
    Pure Risk-Free Breakeven Protection (NO trailing stop beyond Entry):
    1. When position or basket profit hits BREAKEVEN_TRIGGER_PROFIT_USD (+$35.00), shifts SL ONCE to Entry +/- fee buffer.
    2. When open >= STAGNATION_BE_MINUTES (60 mins) and floating >= +$5.00, shifts SL ONCE to Entry +/- fee buffer.
    Never chases price or eats structural TP; leaves user's tighter manual SL untouched.
    Returns True if any position currently sits risk-free at/past Breakeven SL.
    """
    if not active_positions:
        return False

    import risk_safeguards
    is_be_enabled = getattr(risk_safeguards, "BREAKEVEN_GUARD_ENABLED", True)
    be_trigger_usd = float(getattr(risk_safeguards, "BREAKEVEN_TRIGGER_PROFIT_USD", 35.0))
    gold_buf = float(getattr(risk_safeguards, "BREAKEVEN_GOLD_BUFFER", 0.25))
    fx_buf = float(getattr(risk_safeguards, "BREAKEVEN_FX_BUFFER", 0.00020))
    is_stag_enabled = getattr(risk_safeguards, "STAGNATION_GUARD_ENABLED", True)
    stag_mins = float(getattr(risk_safeguards, "STAGNATION_BE_MINUTES", 60.0))

    sl_modifier = modify_fn or modify_position_sl
    now_utc = utc_now_naive()
    any_be_active = False

    for p in active_positions:
        sym = str(getattr(p, "symbol", ""))
        sym_up = sym.upper()
        if any(c in sym_up for c in ("BTC", "ETH", "SOL", "BNB", "XRP", "USDT")):
            continue

        entry_p = float(getattr(p, "price_open", 0.0) or 0.0)
        if entry_p <= 0.0:
            continue

        is_metals = any(m in sym_up for m in ("XAU", "GOLD", "XAG", "SILVER"))
        digits = 2 if is_metals else 5
        be_buf = gold_buf if is_metals else fx_buf
        tol = 0.01 if is_metals else 0.00005

        curr_sl = float(getattr(p, "sl", 0.0) or 0.0)
        pos_profit = float(getattr(p, "profit", 0.0) or 0.0)
        pos_type = int(getattr(p, "type", 0))
        is_buy = (pos_type == getattr(mt5, "ORDER_TYPE_BUY", 0))

        if is_buy:
            target_sl = round(entry_p + be_buf, digits)
            already_be = (curr_sl > 0.0 and curr_sl >= entry_p - tol)
        else:
            target_sl = round(entry_p - be_buf, digits)
            already_be = (curr_sl > 0.0 and curr_sl <= entry_p + tol)

        if already_be:
            any_be_active = True
            continue

        profit_hit = is_be_enabled and (
            pos_profit >= be_trigger_usd
            or floating_profit >= be_trigger_usd
            or peak_floating_profit >= be_trigger_usd
        )

        elapsed_min = 0.0
        pos_time = getattr(p, "time", None)
        if pos_time:
            open_utc = mt5_epoch_to_utc_naive(pos_time, sym)
            elapsed_min = max(0.0, (now_utc - open_utc).total_seconds() / 60.0)

        stag_hit = is_stag_enabled and elapsed_min >= stag_mins and pos_profit >= 5.0

        if profit_hit or stag_hit:
            reason = (
                f"Profit ${pos_profit:.2f} (Peak ${peak_floating_profit:.2f}) >= ${be_trigger_usd:.2f}"
                if profit_hit
                else f"60m+ Stagnation ({elapsed_min:.1f}m, Profit +${pos_profit:.2f})"
            )
            if sl_modifier(p.ticket, sym, target_sl):
                any_be_active = True
                logger.info(
                    f"🛡️ [PURE BREAKEVEN LOCKED 🟢] Ticket #{p.ticket} ({sym}) | {reason} | "
                    f"SL moved ONCE to {target_sl:.{digits}f} (No Trailing — TP Untouched)"
                )

    return any_be_active


def modify_sl_for_trade(symbol, new_sl):
    """Modifies the Stop Loss of all active trade parts to the new_sl price."""
    positions = mt5.positions_get(symbol=symbol)
    if not positions:
        from data_ingestion import resolve_broker_symbol
        resolved = resolve_broker_symbol(symbol)
        if resolved != symbol:
            positions = mt5.positions_get(symbol=resolved)
    if not positions:
        all_pos = mt5.positions_get()
        if all_pos:
            base_sym = symbol.split('.')[0].upper()
            positions = [p for p in all_pos if p.symbol.split('.')[0].upper() == base_sym]
            
    if not positions:
        return
        
    for pos in positions:
        if pos.magic == MAGIC_NUMBER:
            # Check if SL change is significant
            if abs(pos.sl - new_sl) > 0.00001:
                request = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "position": pos.ticket,
                    "symbol": pos.symbol,
                    "sl": new_sl,
                    "tp": pos.tp
                }

                res = mt5.order_send(request)
                if is_retcode_success(res):
                    logger.info(f"🛡️ [BREAKEVEN APPLIED] MT5 Ticket #{pos.ticket} SL moved to Breakeven (${new_sl:.5f}) 🛡️")
                else:

                    err_msg = res.comment if res else "No response"
                    logger.error(f"Failed to modify SL for position ticket {pos.ticket}: {err_msg}")

def check_closed_trades(symbol):
    """
    Checks if any open trades in the database have been closed in MT5.
    Queries the MT5 history deals to log close price and profit to the database.
    """
    conn = None
    open_tickets = []
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT ticket FROM trades WHERE status = 'OPEN' AND symbol = %s", (symbol,))
        open_tickets = [row[0] for row in cur.fetchall()]
        cur.close()
    except Exception as e:
        logger.error(f"Database error checking open tickets: {e}")
    finally:
        if conn:
            conn.close()

    if not open_tickets:
        return

    # Get active positions from MT5 (without symbol filter to avoid suffix/naming mismatches)
    positions = mt5.positions_get()
    if positions is None:
        # Transient connection issues - abort sync to prevent false trade closures
        return
    active_tickets = [p.ticket for p in positions]

    for ticket in open_tickets:
        if ticket not in active_tickets:
            # Trade is closed. Let's find exit deal details in MT5 history
            logger.info(f"Detected closed trade ticket: {ticket}. Fetching details from MT5 history...")
            
            # Primary method: Get deals by position ID directly (timezone and date range independent)
            history_deals = mt5.history_deals_get(position=ticket)
            
            # Fallback method: if direct position query returns nothing, search by date range
            if not history_deals:
                from_date = utc_now_naive() - datetime.timedelta(days=30)
                to_date = utc_now_naive() + datetime.timedelta(days=2)
                history_deals = mt5.history_deals_get(from_date, to_date)
            
            close_price = 0.0
            profit = 0.0
            close_time = utc_now_naive()
            found_exit_deal = False
            
            if history_deals:
                # Exit deals have entry Out (mt5.DEAL_ENTRY_OUT = 1)
                exit_deals = [d for d in history_deals if d.position_id == ticket and d.entry == mt5.DEAL_ENTRY_OUT]
                
                if exit_deals:
                    deal = exit_deals[0]
                    close_price = float(deal.price)
                    
                    # Sum profit/commission/swaps for all deals associated with this ticket
                    all_deals_for_pos = [d for d in history_deals if d.position_id == ticket]
                    profit = sum(d.profit + d.commission + d.swap for d in all_deals_for_pos if d.entry == mt5.DEAL_ENTRY_OUT)
                    close_time = mt5_epoch_to_utc_naive(deal.time, symbol)
                    found_exit_deal = True

            if not found_exit_deal:
                # Fallback to mathematical profit calculation using current/last tick price and database record
                logger.warning(f"Could not retrieve history deals for closed ticket {ticket}. Using mathematical fallback...")
                tick = mt5.symbol_info_tick(symbol)
                if tick:
                    close_price = (tick.bid + tick.ask) / 2.0
                else:
                    close_price = 0.0
                
                if close_price > 0.0:
                    try:
                        conn_db = get_connection()
                        cur_db = conn_db.cursor()
                        cur_db.execute("SELECT entry_price, lots, order_type FROM trades WHERE ticket = %s", (int(ticket),))
                        row = cur_db.fetchone()
                        cur_db.close()
                        conn_db.close()
                        if row:
                            e_price, lts, o_type = row
                            mult = 1.0 if str(o_type).upper() == "BUY" else -1.0
                            sym_info = mt5.symbol_info(symbol)
                            contract_size = sym_info.trade_contract_size if sym_info else 100000.0
                            profit = (close_price - float(e_price)) * float(lts) * mult * contract_size
                    except Exception as fe:
                        logger.error(f"Failed to calculate fallback MT5 profit: {fe}")

            log_trade_exit(ticket, close_price, profit, close_time)
            logger.info(f"Logged closed trade ticket {ticket} | Exit: {close_price:.5f} | Profit: ${profit:.2f}")

            # Send Discord exit notification
            try:
                conn_info = get_connection()
                cur_info = conn_info.cursor()
                cur_info.execute("SELECT symbol, order_type, lots, comment FROM trades WHERE ticket = %s", (int(ticket),))
                row_info = cur_info.fetchone()
                cur_info.close()
                conn_info.close()
                if row_info:
                    sym_name, o_type, lts, cmt = row_info
                    pnl_emoji = "🟢" if profit >= 0 else "🔴"
                    pnl_word = "PROFIT" if profit >= 0 else "LOSS"
                    
                    disc_msg = (
                        f"⏹ **JANE STREET POSITION CLOSED** ⏹\n\n"
                        f"🎫 **Ticket:** `{ticket}`\n"
                        f"💱 **Symbol:** `{sym_name}` ({cmt})\n"
                        f"📦 **Size:** `{lts:.2f} lots` ({o_type})\n"
                        f"💵 **Exit Price:** `{close_price:.5f}`\n"
                        f"{pnl_emoji} **P&L:** **${profit:+.2f}** ({pnl_word})\n"
                    )
                    from database import send_discord_message
                    send_discord_message(disc_msg)
            except Exception as e_disc:
                logger.error(f"Error sending Discord exit message: {e_disc}")

def get_filling_modes_for_symbol(symbol):
    """Detects broker supported filling modes for a symbol, putting native supported mode first."""
    info = mt5.symbol_info(symbol)
    modes = []
    if info:
        f_mode = getattr(info, "filling_mode", 0)
        if f_mode & 1:
            modes.append(mt5.ORDER_FILLING_FOK)
        if f_mode & 2:
            modes.append(mt5.ORDER_FILLING_IOC)
    for fallback in [mt5.ORDER_FILLING_RETURN, mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_IOC]:
        if fallback not in modes:
            modes.append(fallback)
    return modes


def close_position_by_ticket(symbol, ticket, volume_to_close):
    """Closes a specific MT5 position by its ticket (fully or partially). Handles FOK/IOC/RETURN filling modes and market closed status."""
    mt5.symbol_select(symbol, True)
    positions = mt5.positions_get(ticket=int(ticket))
    if positions is None:
        return False
    if len(positions) == 0:
        sym_positions = mt5.positions_get(symbol=symbol)
        if not sym_positions:
            from data_ingestion import resolve_broker_symbol
            resolved = resolve_broker_symbol(symbol)
            if resolved != symbol:
                sym_positions = mt5.positions_get(symbol=resolved)
        if not sym_positions:
            all_pos = mt5.positions_get()
            if all_pos:
                base_sym = symbol.split('.')[0].upper()
                sym_positions = [p for p in all_pos if p.symbol.split('.')[0].upper() == base_sym]
        if sym_positions:
            pos = sym_positions[0]
            ticket = pos.ticket
            logger.info(f"[NETTING AUTO-RESOLVE] Ticket not found, using active position ticket {pos.ticket} for {symbol}.")
            positions = [pos]
        else:
            logger.warning(f"Could not find MT5 position ticket {ticket} to close. Checking DB...")
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT status FROM trades WHERE ticket = %s", (int(ticket),))
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row and row[0] == 'OPEN':
                logger.info(f"Ticket {ticket} open in DB but missing in MT5. Marking as CLOSED.")
                log_trade_exit(ticket, 0.0, 0.0, utc_now_naive())
            return False
        
    pos = positions[0]

    # ── HOLD GUARD DISABLED PER USER DIRECTIVE FOR INSTANT MANUAL/BOT CLOSES ──
    # Positions can close instantly at any time without 140s delay
    
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        logger.error(f"Failed to fetch tick for {symbol} to close position {ticket}")
        return False
    close_order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
    
    from risk_safeguards import round_volume
    vol = round_volume(symbol, min(float(volume_to_close), float(pos.volume)))
            
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": vol,
        "type": close_order_type,
        "position": int(ticket),
        "price": price,
        "deviation": 10,
        "magic": MAGIC_NUMBER,
        "comment": "JS Arbitrage Exit",
        "type_time": mt5.ORDER_TIME_GTC,
    }
    
    filling_modes = get_filling_modes_for_symbol(symbol)
    res = None
    for mode in filling_modes:
        request["type_filling"] = mode
        res = mt5.order_send(request)
        if is_retcode_success(res):
            logger.info(f"🔴 [TRADE EXIT EXECUTED] Ticket #{ticket} | Symbol: {symbol} | Volume: {vol} Lots | Execution Mode: {mode}")
            check_closed_trades(symbol)
            return True
        elif res and res.retcode in (10018, 10021): # Market is closed
            logger.warning(f"Market is closed for {symbol} (Ticket {ticket}). Deferring close until market reopens.")
            return False

            
    err_comment = res.comment if res else "No response"
    logger.error(f"Failed to close position ticket {ticket}: {err_comment}")
    return False


def check_pre_entry_direction_confirmation(signal_type, z_score, z_velocity, pair_str="", velocity_threshold=None):
    """
    Protection 3: Pre-Entry Direction Confirmation.
    COMPLETELY DISABLED per user directive to ensure pure baseline immediate entry on Z threshold cross!
    """
    return True, "Pre-entry direction filter DISABLED (Pure Baseline)"




