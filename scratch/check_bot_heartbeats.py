import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, last_heartbeat, system_status, equity, crypto_equity, updated_at FROM bot_state ORDER BY id")
    print("=== BOT HEARTBEATS ===")
    for r in cur.fetchall():
        print(f"ID: {r[0]} | Last Heartbeat: {r[1]} | Status: {r[2]} | Equity: {r[3]} | CryptoEquity: {r[4]} | UpdatedAt: {r[5]}")
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
