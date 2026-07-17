import os

exec_bot_path = os.path.join(os.path.dirname(__file__), "..", "execution_bot.py")

with open(exec_bot_path, "r", encoding="utf-8") as f:
    content = f.read()

# Locate check_closed_trades block to replace
start_check = content.find("def check_closed_trades")
end_check = content.find("def close_position_by_ticket")

if start_check != -1 and end_check != -1:
    old_check_block = content[start_check:end_check]
    new_check_block = """def check_closed_trades(symbol):
    \"\"\"
    Checks if any open trades in the database have been closed in MT5.
    Queries the MT5 history deals to log close price and profit to the database.
    \"\"\"
    from data_ingestion import resolve_broker_symbol
    resolved_symbol = resolve_broker_symbol(symbol)
    
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

    # Get active positions from MT5
    positions = mt5.positions_get(symbol=resolved_symbol)
    active_tickets = [p.ticket for p in positions] if positions else []

    for ticket in open_tickets:
        if ticket not in active_tickets:
            # Trade is closed. Let's find exit deal details in MT5 history
            logger.info(f"Detected closed trade ticket: {ticket}. Fetching details from MT5 history...")
            
            # Primary method: Get deals by position ID directly (timezone and date range independent)
            history_deals = mt5.history_deals_get(position=ticket)
            
            # Fallback method: if direct position query returns nothing, search by date range
            if not history_deals:
                from_date = datetime.datetime.now() - datetime.timedelta(days=30)
                to_date = datetime.datetime.now() + datetime.timedelta(days=1)
                history_deals = mt5.history_deals_get(from_date, to_date)
            
            close_price = 0.0
            profit = 0.0
            close_time = datetime.datetime.now()
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
                    close_time = datetime.datetime.fromtimestamp(deal.time)
                    found_exit_deal = True

            if not found_exit_deal:
                # Fallback to mathematical profit calculation using current/last tick price and database record
                logger.warning(f"Could not retrieve history deals for closed ticket {ticket}. Using mathematical fallback...")
                tick = mt5.symbol_info_tick(resolved_symbol)
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
                            sym_info = mt5.symbol_info(resolved_symbol)
                            contract_size = sym_info.trade_contract_size if sym_info else 100000.0
                            profit = (close_price - float(e_price)) * float(lts) * mult * contract_size
                    except Exception as fe:
                        logger.error(f"Failed to calculate fallback MT5 profit: {fe}")

            log_trade_exit(ticket, close_price, profit, close_time)
            logger.info(f"Logged closed trade ticket {ticket} | Exit: {close_price:.5f} | Profit: ${profit:.2f}")

"""
    content = content.replace(old_check_block, new_check_block)
    print("check_closed_trades block replaced.")
else:
    print("check_closed_trades block not found!")

# Now locate and replace close_position_by_ticket block
# It's at the end of the file, starting with def close_position_by_ticket
start_close = content.find("def close_position_by_ticket")

if start_close != -1:
    old_close_block = content[start_close:]
    new_close_block = """def close_position_by_ticket(symbol, ticket, volume_to_close):
    \"\"\"Closes a specific MT5 position by its ticket (fully or partially).\"\"\"
    from data_ingestion import resolve_broker_symbol
    resolved_symbol = resolve_broker_symbol(symbol)
    
    positions = mt5.positions_get(ticket=int(ticket))
    if not positions:
        logger.warning(f"Could not find MT5 position ticket {ticket} to close. Checking if it's already closed...")
        # Check if already closed to avoid double log
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT status FROM trades WHERE ticket = %s", (int(ticket),))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row and row[0] == 'OPEN':
            logger.info(f"Ticket {ticket} still open in DB but missing in MT5. Marking as CLOSED in DB.")
            log_trade_exit(ticket, 0.0, 0.0, datetime.datetime.now())
        return False
        
    pos = positions[0]
    # Enforce 31-second minimum hold time safeguard for Forex accounts to prevent broker block
    import time
    open_time = getattr(pos, "time_msc", 0) / 1000.0 if getattr(pos, "time_msc", 0) > 0 else getattr(pos, "time", 0)
    if open_time > 0:
        elapsed = time.time() - open_time
        if elapsed < 32.0:
            wait_time = 32.0 - elapsed
            logger.info(f"Safeguard: Position ticket {pos.ticket} was opened only {elapsed:.1f}s ago. Waiting {wait_time:.1f}s to satisfy the 31-second broker minimum hold time rule...")
            time.sleep(wait_time)

    order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    
    # Fetch latest price
    tick = mt5.symbol_info_tick(resolved_symbol)
    if tick is None:
        logger.error(f"Failed to fetch tick for {resolved_symbol} to close position {ticket}")
        return False
    price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
    
    # Ensure volume to close doesn't exceed current position volume
    vol = min(float(volume_to_close), float(pos.volume))
    
    # Check broker minimum step size
    info = mt5.symbol_info(resolved_symbol)
    if info:
        step = info.volume_step
        vol = round(round(vol / step) * step, 2)
        if vol < info.volume_min:
            vol = info.volume_min
            
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": resolved_symbol,
        "volume": vol,
        "type": order_type,
        "position": int(ticket),
        "price": price,
        "deviation": 10,
        "magic": MAGIC_NUMBER,
        "comment": "JS Arbitrage Exit",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    # Try all filling modes
    filling_modes = [mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_RETURN]
    res = None
    for mode in filling_modes:
        request["type_filling"] = mode
        res = mt5.order_send(request)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"Successfully closed position ticket {ticket} | Volume: {vol}")
            # Log close in DB
            check_closed_trades(symbol)
            return True
            
    err_comment = res.comment if res else "No response"
    logger.error(f"Failed to close position ticket {ticket}: {err_comment}")
    return False
"""
    content = content.replace(old_close_block, new_close_block)
    print("close_position_by_ticket block replaced.")
else:
    print("close_position_by_ticket block not found!")

with open(exec_bot_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
