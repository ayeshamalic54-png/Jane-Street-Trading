import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    # Check what is currently being logged under scanned_assets
    cur.execute("SELECT symbol_pair, win_rate, z_score, action, updated_at FROM scanned_assets ORDER BY win_rate DESC LIMIT 20")
    print("=== SCANNED ASSETS IN DATABASE ===")
    for r in cur.fetchall():
        print(f"Pair: {r[0]} | WinRate: {r[1]}% | Z: {r[2]} | Action: {r[3]} | Updated: {r[4]}")
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
