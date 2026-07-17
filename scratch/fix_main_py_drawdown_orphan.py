import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

# Define replacement 1: New close_orphan_spread_legs implementation
target_orphan = """def close_orphan_spread_legs():
    \"\"\"
    Detects if one leg of a spread pair has been marked CLOSED in the database,
    and automatically closes the other open leg on the broker (Binance/MT5) and marks it CLOSED.
    \"\"\"
    is_crypto_vps = os.getenv("OVERRIDE_CRYPTO_ENABLED") == "True"
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # Find all open trades
        cur.execute("SELECT ticket, symbol, order_type, lots, signal_id FROM trades WHERE status = 'OPEN'")
        open_trades = cur.fetchall()
        if not open_trades:
            cur.close()
            conn.close()
            return
            
        # Group open trades by signal_id
        open_by_signal = {}
        for ticket, symbol, order_type, lots, signal_id in open_trades:
            if signal_id is not None:
                open_by_signal.setdefault(signal_id, []).append((ticket, symbol, order_type, lots))
                
        for signal_id, legs in open_by_signal.items():
            # Check if there are other trades with the same signal_id that are CLOSED
            cur.execute("SELECT ticket, symbol, status FROM trades WHERE signal_id = %s AND status = 'CLOSED'", (signal_id,))
            closed_legs = cur.fetchall()
            
            # If some legs of this signal are closed but some are still open, it is an orphan spread!
            if closed_legs:
                logger.info(f"[ORPHAN CLOSER] Detected orphan legs for signal {signal_id}. Closing open legs...")
                for ticket, symbol, order_type, lots in legs:
                    cat = get_symbol_category(symbol)
                    if cat == "crypto":
                        if is_crypto_vps:
                            is_long = (order_type.upper() == "BUY")
                            logger.info(f"[ORPHAN CLOSER] Closing crypto leg {symbol} (lots: {lots}) on Binance...")
                            close_binance_partial(symbol, lots, is_long)
                            send_signed_request("DELETE", "/fapi/v1/allOpenOrders", {"symbol": symbol})
                            
                            # Fetch price for close log
                            tick = get_binance_live_tick(symbol)
                            live_p = (tick.bid + tick.ask) / 2.0 if tick else 0.0
                            log_trade_exit(ticket, live_p, 0.0, datetime.datetime.now())
                    else:
                        if not is_crypto_vps:
                            logger.info(f"[ORPHAN CLOSER] Closing MT5 leg {symbol} (ticket: {ticket})...")
                            close_position_by_ticket(ticket)
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error in close_orphan_spread_legs: {e}")"""

replacement_orphan = """def close_orphan_spread_legs():
    \"\"\"
    Detects if one symbol of a spread pair has no open trades in the database,
    but the other symbol still has open trades, and automatically closes the other symbol's positions.
    \"\"\"
    is_crypto_vps = os.getenv("OVERRIDE_CRYPTO_ENABLED") == "True"
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # Find all open trades
        cur.execute("SELECT ticket, symbol, order_type, lots, signal_id FROM trades WHERE status = 'OPEN'")
        open_trades = cur.fetchall()
        if not open_trades:
            cur.close()
            conn.close()
            return
            
        # Group open trades by signal_id and symbol
        open_by_signal = {}
        for ticket, symbol, order_type, lots, signal_id in open_trades:
            if signal_id is not None:
                open_by_signal.setdefault(signal_id, {}).setdefault(symbol.upper(), []).append((ticket, order_type, lots))
                
        for signal_id, symbols_dict in open_by_signal.items():
            # A spread has two legs. If only one symbol has open trades in DB, the other is closed (orphan spread!)
            if len(symbols_dict) == 1:
                orphan_symbol = list(symbols_dict.keys())[0]
                legs_to_close = symbols_dict[orphan_symbol]
                
                logger.info(f"[ORPHAN CLOSER] Detected orphan symbol {orphan_symbol} for signal {signal_id}. Closing open legs...")
                for ticket, order_type, lots in legs_to_close:
                    cat = get_symbol_category(orphan_symbol)
                    if cat == "crypto":
                        if is_crypto_vps:
                            is_long = (order_type.upper() == "BUY")
                            logger.info(f"[ORPHAN CLOSER] Closing crypto leg {orphan_symbol} (lots: {lots}) on Binance...")
                            close_binance_partial(orphan_symbol, lots, is_long)
                            send_signed_request("DELETE", "/fapi/v1/allOpenOrders", {"symbol": orphan_symbol})
                            
                            # Fetch price for close log
                            tick = get_binance_live_tick(orphan_symbol)
                            live_p = (tick.bid + tick.ask) / 2.0 if tick else 0.0
                            log_trade_exit(ticket, live_p, 0.0, datetime.datetime.now())
                    else:
                        if not is_crypto_vps:
                            logger.info(f"[ORPHAN CLOSER] Closing MT5 leg {orphan_symbol} (ticket: {ticket})...")
                            close_position_by_ticket(ticket)
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error in close_orphan_spread_legs: {e}")"""

# Define replacement 2: Drawdown breach bypass for Crypto VPS
target_drawdown = """            # Calculate daily drawdown using the correct equity (only if equity > 0.0)
            if current_equity > 0.0:
                is_limit_breached, daily_loss_p = check_drawdown_limit(current_equity)
            else:
                is_limit_breached, daily_loss_p = False, 0.0"""

replacement_drawdown = """            # Calculate daily drawdown using the correct equity (only if equity > 0.0)
            if current_equity > 0.0:
                is_limit_breached, daily_loss_p = check_drawdown_limit(current_equity)
                if is_crypto_vps:
                    is_limit_breached = False  # Bypass daily drawdown limit check for Crypto VPS
            else:
                is_limit_breached, daily_loss_p = False, 0.0"""

# Define replacement 3: acc_info.equity crash fix
target_equity_crash = """                    system_status="HALTED (Max Loss)",
                    equity=acc_info.equity,
                    drawdown_percent=daily_loss_p,"""

replacement_equity_crash = """                    system_status="HALTED (Max Loss)",
                    equity=current_equity,
                    drawdown_percent=daily_loss_p,"""


if target_orphan in content:
    content = content.replace(target_orphan, replacement_orphan)
    print("Replacement 1 (orphan closer) successful.")
else:
    print("Replacement 1 failed!")

if target_drawdown in content:
    content = content.replace(target_drawdown, replacement_drawdown)
    print("Replacement 2 (drawdown bypass) successful.")
else:
    print("Replacement 2 failed!")

if target_equity_crash in content:
    content = content.replace(target_equity_crash, replacement_equity_crash)
    print("Replacement 3 (equity crash fix) successful.")
else:
    print("Replacement 3 failed!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
