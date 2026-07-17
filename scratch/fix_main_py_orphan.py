import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

# Define replacement 1 (function definition)
target1 = """    if any(x in s for x in ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMD", "META", "AMZN", "US500", "US30", "NAS100", "GER30", "UK100"]):
        return "indices"
    return "forex"

def get_hedge_quantity(symbol_a: str, symbol_b: str, qty_a: float, beta: float, cat_a: str, cat_b: str) -> float:"""

replacement1 = """    if any(x in s for x in ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMD", "META", "AMZN", "US500", "US30", "NAS100", "GER30", "UK100"]):
        return "indices"
    return "forex"

def close_orphan_spread_legs():
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
        logger.error(f"Error in close_orphan_spread_legs: {e}")

def get_hedge_quantity(symbol_a: str, symbol_b: str, qty_a: float, beta: float, cat_a: str, cat_b: str) -> float:"""

# Define replacement 2 (function call in the loop)
target2 = """                is_crypto_vps = os.getenv("OVERRIDE_CRYPTO_ENABLED") == "True"
                for sym in open_symbols:
                    cat = get_symbol_category(sym)
                    if cat == "crypto":
                        if is_crypto_vps:
                            check_closed_binance_trades(sym)
                    else:
                        if not is_crypto_vps:
                            check_closed_trades(sym)"""

replacement2 = """                is_crypto_vps = os.getenv("OVERRIDE_CRYPTO_ENABLED") == "True"
                for sym in open_symbols:
                    cat = get_symbol_category(sym)
                    if cat == "crypto":
                        if is_crypto_vps:
                            check_closed_binance_trades(sym)
                    else:
                        if not is_crypto_vps:
                            check_closed_trades(sym)
                
                # Close any orphan legs
                close_orphan_spread_legs()"""

if target1 in content:
    content = content.replace(target1, replacement1)
    print("Replacement 1 successful.")
else:
    print("Replacement 1 failed.")

if target2 in content:
    content = content.replace(target2, replacement2)
    print("Replacement 2 successful.")
else:
    print("Replacement 2 failed.")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
