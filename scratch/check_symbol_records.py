import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT ticket, symbol, order_type, lots, entry_price, status, comment FROM trades WHERE symbol LIKE '%UNI%' OR symbol LIKE '%NEAR%'")
    rows = cur.fetchall()
    print(f"=== FOUND {len(rows)} RECORDS ===")
    for r in rows:
        print(f"Ticket: {r[0]} | Symbol: {r[1]} | Type: {r[2]} | Lots: {r[3]} | Entry: {r[4]} | Status: {r[5]} | Comment: {r[6]}")
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
