import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT ticket, symbol, status, profit, entry_price FROM trades WHERE status = 'OPEN'")
    print("=== OPEN TRADES IN DB ===")
    for r in cur.fetchall():
        print(f"Ticket: {r[0]} | Symbol: {r[1]} | Status: {r[2]} | Profit: {r[3]} | EntryPrice: {r[4]}")
    
    cur.execute("SELECT id, status, equity, crypto_equity, system_status FROM bot_status")
    print("=== BOT STATUS IN DB ===")
    for r in cur.fetchall():
        print(f"ID: {r[0]} | Status: {r[1]} | Equity: {r[2]} | CryptoEquity: {r[3]} | SystemStatus: {r[4]}")
        
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
