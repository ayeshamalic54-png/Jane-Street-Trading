import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT ticket, symbol, order_type, lots, entry_price, close_price, close_time, profit, comment, status FROM trades WHERE symbol LIKE '%UNI%' OR symbol LIKE '%NEAR%'")
    rows = cur.fetchall()
    print("=== DETAILS OF CLOSED TRADES ===")
    for r in rows:
        print(f"Ticket: {r[0]} | Symbol: {r[1]} | Type: {r[2]} | Lots: {r[3]} | Entry: {r[4]} | Close: {r[5]} | CloseTime: {r[6]} | Profit: {r[7]} | Comment: {r[8]} | Status: {r[9]}")
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
