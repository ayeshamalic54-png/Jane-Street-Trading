import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")
binance_path = os.path.join(os.path.dirname(__file__), "..", "binance_execution.py")

# 1. Update main.py close_orphan_spread_legs
with open(main_path, "r", encoding="utf-8") as f:
    main_content = f.read()

target_main = """        # Find all open trades
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
                            log_trade_exit(ticket, live_p, 0.0, datetime.datetime.now())"""

replacement_main = """        # Find all open trades
        cur.execute("SELECT ticket, symbol, order_type, lots, signal_id, entry_price FROM trades WHERE status = 'OPEN'")
        open_trades = cur.fetchall()
        if not open_trades:
            cur.close()
            conn.close()
            return
            
        # Group open trades by signal_id and symbol
        open_by_signal = {}
        for ticket, symbol, order_type, lots, signal_id, entry_price in open_trades:
            if signal_id is not None:
                open_by_signal.setdefault(signal_id, {}).setdefault(symbol.upper(), []).append((ticket, order_type, lots, entry_price))
                
        for signal_id, symbols_dict in open_by_signal.items():
            # A spread has two legs. If only one symbol has open trades in DB, the other is closed (orphan spread!)
            if len(symbols_dict) == 1:
                orphan_symbol = list(symbols_dict.keys())[0]
                legs_to_close = symbols_dict[orphan_symbol]
                
                logger.info(f"[ORPHAN CLOSER] Detected orphan symbol {orphan_symbol} for signal {signal_id}. Closing open legs...")
                for ticket, order_type, lots, entry_price in legs_to_close:
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
                            mult = 1.0 if order_type.upper() == "BUY" else -1.0
                            calc_profit = (live_p - float(entry_price)) * float(lots) * mult
                            log_trade_exit(ticket, live_p, calc_profit, datetime.datetime.now())"""

if target_main in main_content:
    main_content = main_content.replace(target_main, replacement_main)
    print("main.py Orphan Closer profit calculation added.")
else:
    print("main.py target not found!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(main_content)

# 2. Update binance_execution.py check_closed_binance_trades fallback
with open(binance_path, "r", encoding="utf-8") as f:
    binance_content = f.read()

target_binance = """            # Mark all open tickets in database as CLOSED
            for ticket, entry_price, lots, order_type, _, _ in open_trades:
                part_profit = profit / len(open_trades) if profit != 0.0 else 0.0
                if part_profit == 0.0 and close_price != 0.0:
                    mult = 1.0 if order_type.upper() == "BUY" else -1.0
                    part_profit = (close_price - float(entry_price)) * float(lots) * mult
                log_trade_exit(ticket, close_price, part_profit, close_time)"""

replacement_binance = """            # Mark all open tickets in database as CLOSED
            for ticket, entry_price, lots, order_type, _, _ in open_trades:
                # If history exit trade is delayed, close_price might default to entry_price or 0.0. Fallback to live tick as backup.
                temp_close = close_price
                if temp_close == 0.0 or temp_close == float(entry_price):
                    tick = get_binance_live_tick(symbol)
                    if tick:
                        temp_close = (tick.bid + tick.ask) / 2.0
                        
                part_profit = profit / len(open_trades) if profit != 0.0 else 0.0
                if part_profit == 0.0 and temp_close != 0.0:
                    mult = 1.0 if order_type.upper() == "BUY" else -1.0
                    part_profit = (temp_close - float(entry_price)) * float(lots) * mult
                log_trade_exit(ticket, temp_close, part_profit, close_time)"""

if target_binance in binance_content:
    binance_content = binance_content.replace(target_binance, replacement_binance)
    print("binance_execution.py close price / profit fallback added.")
else:
    print("binance_execution.py target not found!")

with open(binance_path, "w", encoding="utf-8") as f:
    f.write(binance_content)

print("Both files updated.")
