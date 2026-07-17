import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    # Query Forex signals from today
    cur.execute("""
        SELECT id, timestamp, symbol_a, symbol_b, price_a, price_b, z_score, action 
        FROM signals 
        WHERE symbol_a NOT LIKE '%USDT' AND timestamp >= '2026-07-15 00:00:00'
        ORDER BY timestamp DESC
        LIMIT 20
    """)
    colnames = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    print("=== FOREX SIGNALS GENERATED TODAY ===")
    for r in rows:
        for col, val in zip(colnames, r):
            print(f"{col}: {val}")
        print("-" * 20)
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
