import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """                                    cur.execute(
                                        "UPDATE trades SET close_price = %s, profit = %s WHERE ticket = %s",
                                        (float(live_price), float(profit_val), int(ticket))
                                    )
                conn.commit()"""

replacement = """                                    cur.execute(
                                        "UPDATE trades SET close_price = %s, profit = %s WHERE ticket = %s",
                                        (float(live_price), float(profit_val), int(ticket))
                                    )
                    
                    # Ghost Position Closer: Close any position active on Binance that is not recorded as OPEN in database
                    try:
                        db_open_symbols = {sym.upper() for sym in crypto_open_by_symbol.keys()}
                        for b_sym, pos in binance_positions.items():
                            if b_sym not in db_open_symbols:
                                amt = float(pos["positionAmt"])
                                logger.warning(f"[GHOST CLOSER] Active position for {b_sym} ({amt}) not open in DB. Closing immediately...")
                                is_long = (amt > 0)
                                close_binance_partial(b_sym, abs(amt), is_long)
                                send_signed_request("DELETE", "/fapi/v1/allOpenOrders", {"symbol": b_sym})
                    except Exception as gc_err:
                        logger.error(f"Error in Ghost Position Closer: {gc_err}")
                conn.commit()"""

if target in content:
    content = content.replace(target, replacement)
    print("Ghost Closer insertion successful.")
else:
    print("Target not found!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
