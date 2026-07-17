import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, active_pair, system_status, equity, updated_at FROM bot_state")
    print("=== BOT STATE ===")
    for r in cur.fetchall():
        print(f"ID: {r[0]} | ActivePair: {r[1]} | Status: {r[2]} | Equity: {r[3]} | Updated: {r[4]}")
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
