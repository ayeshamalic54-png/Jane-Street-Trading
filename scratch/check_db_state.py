import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import get_connection

conn = None
try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT ticket, symbol, order_type, lots, entry_price, status, profit FROM trades WHERE status = 'OPEN'")
    rows = cur.fetchall()
    print("Trades in DB:")
    if rows:
        for r in rows:
            print(f"Ticket: {r[0]} | Symbol: {r[1]} | Type: {r[2]} | Lots: {r[3]} | Entry: {r[4]} | Status: {r[5]} | Profit: {r[6]}")
    else:
        print("No trades found in DB.")
    cur.close()
except Exception as e:
    print(f"Error: {e}")
finally:
    if conn:
        conn.close()
