import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, sl_pips, tp_pips, z_entry_threshold, max_trades FROM bot_state ORDER BY id")
    for r in cur.fetchall():
        print(f"Bot ID: {r[0]} | SL Pips: {r[1]} | TP Pips: {r[2]} | Z-Entry: {r[3]} | Max Trades: {r[4]}")
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
