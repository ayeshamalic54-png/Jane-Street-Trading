import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, crypto_enabled, metals_enabled, forex_enabled, indices_enabled, drawdown_percent, equity, mt5_equity, crypto_equity FROM bot_state ORDER BY id")
    for r in cur.fetchall():
        print(f"ID: {r[0]} | CryptoEnabled: {r[1]} | MetalsEnabled: {r[2]} | ForexEnabled: {r[3]} | IndicesEnabled: {r[4]} | DD%: {r[5]} | Eq: {r[6]} | MT5Eq: {r[7]} | CryptoEq: {r[8]}")
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
