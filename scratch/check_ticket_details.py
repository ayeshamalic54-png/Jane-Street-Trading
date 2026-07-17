import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM trades WHERE ticket = 31997297142")
    colnames = [desc[0] for desc in cur.description]
    row = cur.fetchone()
    print("=== TICKET 31997297142 ===")
    if row:
        for col, val in zip(colnames, row):
            print(f"{col}: {val}")
    else:
        print("Ticket not found.")
        
    print("\n=== ALL TRADES FOR SIGNAL 12523 ===")
    cur.execute("SELECT ticket, symbol, order_type, lots, entry_price, close_price, profit, status, comment FROM trades WHERE signal_id = 12523")
    rows = cur.fetchall()
    for r in rows:
        print(r)
        
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
