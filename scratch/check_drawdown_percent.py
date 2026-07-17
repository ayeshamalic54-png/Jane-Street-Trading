import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, drawdown_percent FROM bot_state")
    rows = cur.fetchall()
    print("=== BOT STATE DRAWDOWN PERCENT ===")
    for r in rows:
        print(f"Bot ID {r[0]}: {r[1]}%")
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
