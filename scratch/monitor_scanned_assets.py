import os
import sys
import time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import get_connection

print("Monitoring scanned_assets updates for 10 seconds...")
try:
    for i in range(10):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT symbol_pair, win_rate, z_score, action, updated_at FROM scanned_assets ORDER BY updated_at DESC LIMIT 5")
        rows = cur.fetchall()
        print(f"[{i+1}/10] " + " | ".join([f"{r[0]}: Z={r[2]} (Updated: {r[4]})" for r in rows]))
        cur.close()
        conn.close()
        time.sleep(1)
except Exception as e:
    print(f"Error: {e}")
