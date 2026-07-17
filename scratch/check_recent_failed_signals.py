import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    
    # Check recent signals
    cur.execute("SELECT id, symbol_a, symbol_b, price_a, price_b, beta, z_score, action, timestamp FROM signals ORDER BY id DESC LIMIT 10")
    print("=== RECENT SIGNALS ===")
    for r in cur.fetchall():
        print(r)
        
    # Check recent trades
    cur.execute("SELECT ticket, symbol, order_type, lots, entry_price, close_price, profit, status, comment, signal_id, entry_time FROM trades ORDER BY entry_time DESC LIMIT 15")
    print("\n=== RECENT TRADES ===")
    for r in cur.fetchall():
        print(r)
        
    cur.close()
    conn.close()
except Exception as e:
    print("Error:", e)
