import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """def close_single_trade(symbol, ticket, volume, order_type):
    cat = get_symbol_category(symbol)
    if cat == "crypto":
        is_long = (order_type.upper() == "BUY")
        ok = close_binance_partial(symbol, volume, is_long)
        if ok:
            log_trade_exit(ticket, 0.0, 0.0, datetime.datetime.now())
        return ok
    else:
        return close_position_by_ticket(symbol, ticket, volume)"""

replacement = """def close_single_trade(symbol, ticket, volume, order_type):
    cat = get_symbol_category(symbol)
    if cat == "crypto":
        is_long = (order_type.upper() == "BUY")
        close_price = close_binance_partial(symbol, volume, is_long)
        if close_price is not None and close_price > 0.0:
            entry_price = 0.0
            try:
                db_conn = get_connection()
                db_cur = db_conn.cursor()
                db_cur.execute("SELECT entry_price FROM trades WHERE ticket = %s", (int(ticket),))
                row_t = db_cur.fetchone()
                if row_t:
                    entry_price = float(row_t[0])
                db_cur.close()
                db_conn.close()
            except Exception as e_p:
                logger.error(f"Error fetching entry price for profit calculation: {e_p}")
            
            mult = 1.0 if is_long else -1.0
            profit_val = (close_price - entry_price) * float(volume) * mult
            log_trade_exit(ticket, close_price, profit_val, datetime.datetime.now())
            return True
        return False
    else:
        return close_position_by_ticket(symbol, ticket, volume)"""

if target in content:
    content = content.replace(target, replacement)
    print("Replacement successful.")
else:
    print("Target not found!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
