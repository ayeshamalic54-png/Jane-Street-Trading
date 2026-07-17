import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT ticket, symbol, status, close_price, profit, close_time, comment FROM trades WHERE symbol = 'UNIUSDT' ORDER BY entry_time DESC LIMIT 10")
    print("=== RECENT UNIUSDT TRADES ===")
    for r in cur.fetchall():
        print(f"Ticket: {r[0]} | Symbol: {r[1]} | Status: {r[2]} | ClosePrice: {r[3]} | Profit: {r[4]} | CloseTime: {r[5]} | Comment: {r[6]}")
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
