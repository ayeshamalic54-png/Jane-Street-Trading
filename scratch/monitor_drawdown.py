import os
import sys
import time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import get_connection

print("Monitoring bot_state drawdown_percent for 15 seconds...")
try:
    for i in range(15):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, drawdown_percent, updated_at FROM bot_state ORDER BY id")
        rows = cur.fetchall()
        print(f"[{i+1}/15] " + " | ".join([f"ID {r[0]}: DD={r[1]}% (Updated: {r[2]})" for r in rows]))
        cur.close()
        conn.close()
        time.sleep(1)
except Exception as e:
    print(f"Error: {e}")
