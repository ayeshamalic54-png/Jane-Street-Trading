import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, system_status, active_pair, equity, drawdown_percent, updated_at FROM bot_state WHERE id = 1")
    row = cur.fetchone()
    print("=== FOREX BOT STATE IN DATABASE ===")
    if row:
        print(f"ID: {row[0]} | Status: {row[1]} | Pair: {row[2]} | Equity: {row[3]} | Drawdown: {row[4]} | Updated: {row[5]}")
    else:
        print("Forex bot state not found.")
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
