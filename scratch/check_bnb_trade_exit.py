import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT ticket, symbol, order_type, lots, entry_price, close_price, profit, status, comment, close_time FROM trades WHERE symbol IN ('BNBUSDT', 'NEARUSDT') ORDER BY entry_time DESC LIMIT 10")
    colnames = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    print("=== BNB / NEAR TRADES ===")
    for r in rows:
        for col, val in zip(colnames, r):
            print(f"{col}: {val}")
        print("-" * 20)
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
