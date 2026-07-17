import os

binance_path = os.path.join(os.path.dirname(__file__), "..", "binance_execution.py")

with open(binance_path, "r", encoding="utf-8") as f:
    content = f.read()

target_select = """        cur.execute("SELECT ticket, entry_price, lots, order_type, entry_time FROM trades WHERE status = 'OPEN' AND symbol = %s", (symbol,))
        open_trades = cur.fetchall()"""

replacement_select = """        cur.execute("SELECT ticket, entry_price, lots, order_type, entry_time, comment FROM trades WHERE status = 'OPEN' AND symbol = %s", (symbol,))
        open_trades = cur.fetchall()"""

target_loop = """            # Mark all open tickets in database as CLOSED
            for ticket, entry_price, lots, order_type, _ in open_trades:"""

replacement_loop = """            # Mark all open tickets in database as CLOSED
            for ticket, entry_price, lots, order_type, _, _ in open_trades:"""

target_tp_check = """                for ticket, entry_price, lots, order_type, _ in open_trades:
                    # The ticket is the tp_order_id. If it's no longer in open orders, check if it was FILLED.
                    if ticket not in open_order_ids:"""

replacement_tp_check = """                for ticket, entry_price, lots, order_type, _, comment in open_trades:
                    # Skip check for hedge trades - they are closed when position size goes to 0 or via orphan closer
                    if comment and "HEDGE" in comment.upper():
                        continue
                    # The ticket is the tp_order_id. If it's no longer in open orders, check if it was FILLED.
                    if ticket not in open_order_ids:"""

# Update age check to unpack with comment
target_age = """    newest_trade_time = max(t[4] for t in open_trades) if any(t[4] for t in open_trades) else None"""
replacement_age = """    newest_trade_time = max(t[4] for t in open_trades) if any(t[4] for t in open_trades) else None"""

if target_select in content:
    content = content.replace(target_select, replacement_select)
    print("Select replacement successful.")
else:
    print("Select target not found!")

if target_loop in content:
    content = content.replace(target_loop, replacement_loop)
    print("Loop replacement successful.")
else:
    print("Loop target not found!")

if target_tp_check in content:
    content = content.replace(target_tp_check, replacement_tp_check)
    print("TP check replacement successful.")
else:
    print("TP check target not found!")

with open(binance_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
