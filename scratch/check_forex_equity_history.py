import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    
    # 1. Check daily metrics history
    cur.execute("""
        SELECT trading_date, start_equity, current_equity, max_drawdown_percent, trades_today, bot_id 
        FROM daily_metrics 
        ORDER BY trading_date DESC 
        LIMIT 10
    """)
    print("=== DAILY METRICS HISTORY ===")
    colnames_dm = [desc[0] for desc in cur.description]
    for r in cur.fetchall():
        print(dict(zip(colnames_dm, r)))
        
    # 2. Check recent Forex closed trades from yesterday and today
    cur.execute("""
        SELECT ticket, symbol, order_type, lots, entry_price, close_price, profit, status, entry_time, close_time
        FROM trades
        WHERE symbol NOT LIKE '%USDT' AND entry_time >= '2026-07-14 00:00:00'
        ORDER BY entry_time DESC
        LIMIT 20
    """)
    print("\n=== RECENT FOREX CLOSED TRADES ===")
    colnames_t = [desc[0] for desc in cur.description]
    for r in cur.fetchall():
        print(dict(zip(colnames_t, r)))
        
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
