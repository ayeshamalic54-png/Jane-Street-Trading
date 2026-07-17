import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT t.ticket, t.symbol, t.order_type, t.entry_price, t.close_price, t.profit, t.status, t.comment, t.entry_time, t.close_time, s.id, s.z_score 
        FROM trades t
        LEFT JOIN signals s ON t.signal_id = s.id
        WHERE t.symbol IN ('AAVEUSDT', 'DEXEUSDT')
        ORDER BY t.entry_time DESC
        LIMIT 10
    """)
    colnames = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    print("=== AAVE/DEXE EXECUTED TRADES ===")
    for r in rows:
        for col, val in zip(colnames, r):
            print(f"{col}: {val}")
        print("-" * 20)
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
