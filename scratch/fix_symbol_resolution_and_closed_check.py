import os

ingestion_path = os.path.join(os.path.dirname(__file__), "..", "data_ingestion.py")
exec_bot_path = os.path.join(os.path.dirname(__file__), "..", "execution_bot.py")

# 1. Update resolve_broker_symbol in data_ingestion.py
with open(ingestion_path, "r", encoding="utf-8") as f:
    ing_content = f.read()

target_ing = """def resolve_broker_symbol(symbol: str) -> str:
    symbol_upper = symbol.upper()
    # Check if symbol is already valid in MT5
    info = mt5.symbol_info(symbol_upper)
    if info is not None:
        return symbol_upper"""

replacement_ing = """def resolve_broker_symbol(symbol: str) -> str:
    symbol_upper = symbol.upper()
    # Check if symbol is already valid in MT5 and tradeable
    info = mt5.symbol_info(symbol_upper)
    if info is not None:
        trade_mode = getattr(info, "trade_mode", 0)
        tick = mt5.symbol_info_tick(symbol_upper)
        if trade_mode != 0 and tick is not None:
            return symbol_upper"""

if target_ing in ing_content:
    ing_content = ing_content.replace(target_ing, replacement_ing)
    print("data_ingestion.py resolve_broker_symbol updated.")
else:
    print("data_ingestion.py target not found!")

with open(ingestion_path, "w", encoding="utf-8") as f:
    f.write(ing_content)

# 2. Update check_closed_trades in execution_bot.py to query strictly by ticket
with open(exec_bot_path, "r", encoding="utf-8") as f:
    exec_content = f.read()

target_exec = """def check_closed_trades(symbol):
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
            logger.info(f"Logged closed trade ticket {ticket} | Exit: {close_price:.5f} | Profit: ${profit:.2f}")"""

replacement_exec = """def check_closed_trades(symbol):
    \"\"\"
    Checks if any open trades in the database have been closed in MT5.
    Queries the MT5 history deals to log close price and profit to the database.
    \"\"\"
    from data_ingestion import resolve_broker_symbol
    resolved_symbol = resolve_broker_symbol(symbol)
    
    conn = None
    open_trades = []
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT ticket, entry_price, lots, order_type FROM trades WHERE status = 'OPEN' AND symbol = %s", (symbol,))
        open_trades = cur.fetchall()
        cur.close()
    except Exception as e:
        logger.error(f"Database error checking open tickets: {e}")
    finally:
        if conn:
            conn.close()

    if not open_trades:
        return

    for ticket, entry_price, lots, order_type in open_trades:
        # Query MT5 position directly by ticket ID (immune to symbol suffix anomalies)
        pos_list = mt5.positions_get(ticket=int(ticket))
        if not pos_list:
            # Position is closed. Let's find exit deal details in MT5 history
            logger.info(f"Detected closed trade ticket: {ticket}. Fetching details from MT5 history...")
            
            # Primary method: Get deals by position ID directly
            history_deals = mt5.history_deals_get(position=int(ticket))
            
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
                        mult = 1.0 if str(order_type).upper() == "BUY" else -1.0
                        sym_info = mt5.symbol_info(resolved_symbol)
                        contract_size = sym_info.trade_contract_size if sym_info else 100000.0
                        profit = (close_price - float(entry_price)) * float(lots) * mult * contract_size
                    except Exception as fe:
                        logger.error(f"Failed to calculate fallback MT5 profit: {fe}")

            log_trade_exit(ticket, close_price, profit, close_time)
            logger.info(f"Logged closed trade ticket {ticket} | Exit: {close_price:.5f} | Profit: ${profit:.2f}")"""

if target_exec in exec_content:
    exec_content = exec_content.replace(target_exec, replacement_exec)
    print("execution_bot.py check_closed_trades updated to ticket-based check.")
else:
    # Let's inspect content or do a direct string match
    print("execution_bot.py target not found! Let's check matching index.")
    # We will fallback to exact block replacement if string doesn't match perfectly.
    start_idx = exec_content.find("def check_closed_trades")
    end_idx = exec_content.find("def close_position_by_ticket")
    if start_idx != -1 and end_idx != -1:
        exec_content = exec_content[:start_idx] + replacement_exec + "\n\n" + exec_content[end_idx:]
        print("Block replaced successfully.")

with open(exec_bot_path, "w", encoding="utf-8") as f:
    f.write(exec_content)
print("Files updated.")
