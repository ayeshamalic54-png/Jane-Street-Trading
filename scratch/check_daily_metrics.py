import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM daily_metrics ORDER BY trading_date DESC, updated_at DESC LIMIT 10")
    colnames = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    print("=== DAILY METRICS ===")
    for r in rows:
        for col, val in zip(colnames, r):
            print(f"{col}: {val}")
        print("-" * 20)
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
