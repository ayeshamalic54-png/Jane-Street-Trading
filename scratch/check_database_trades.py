import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT ticket, symbol, order_type, lots, entry_price, status, entry_time, comment FROM trades ORDER BY entry_time DESC LIMIT 10")
    print("=== RECENT DATABASE TRADES ===")
    for r in cur.fetchall():
        print(f"Ticket: {r[0]} | Symbol: {r[1]} | Type: {r[2]} | Lots: {r[3]} | Entry: {r[4]} | Status: {r[5]} | Time: {r[6]} | Comment: {r[7]}")
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
