import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, timestamp, symbol_a, symbol_b, price_a, price_b, beta, z_score, action FROM signals ORDER BY id DESC LIMIT 15")
    print("=== RECENT SIGNALS ===")
    for r in cur.fetchall():
        print(f"ID: {r[0]} | Time: {r[1]} | SymA: {r[2]} | SymB: {r[3]} | PriceA: {r[4]} | PriceB: {r[5]} | Beta: {r[6]} | Z: {r[7]} | Action: {r[8]}")
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
