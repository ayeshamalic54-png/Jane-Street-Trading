import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    
    print("=== BOT STATE ===")
    cur.execute("SELECT id, active_pair, system_status, crypto_equity, mt5_equity, equity, drawdown_percent, floating_profit, z_score, hedge_ratio, trades_today, updated_at FROM bot_state ORDER BY id")
    for r in cur.fetchall():
        print(f"ID: {r[0]} | Pair: {r[1]} | Status: {r[2]} | CryptoEq: {r[3]} | MT5Eq: {r[4]} | Eq: {r[5]} | DD%: {r[6]} | FP: {r[7]} | Z: {r[8]} | Beta: {r[9]} | TradesToday: {r[10]} | Updated: {r[11]}")
        
    print("\n=== OPEN TRADES ===")
    cur.execute("SELECT ticket, symbol, order_type, lots, entry_price, status, profit, comment FROM trades WHERE status = 'OPEN'")
    for r in cur.fetchall():
        print(f"Ticket: {r[0]} | Symbol: {r[1]} | Type: {r[2]} | Lots: {r[3]} | Entry: {r[4]} | Status: {r[5]} | Profit: {r[6]} | Comment: {r[7]}")
        
    print("\n=== RECENT CLOSED TRADES ===")
    cur.execute("SELECT ticket, symbol, order_type, lots, entry_price, close_price, profit, comment, close_time FROM trades WHERE status = 'CLOSED' ORDER BY close_time DESC LIMIT 5")
    for r in cur.fetchall():
        print(f"Ticket: {r[0]} | Symbol: {r[1]} | Type: {r[2]} | Lots: {r[3]} | Entry: {r[4]} | Close: {r[5]} | Profit: {r[6]} | Comment: {r[7]} | Closed: {r[8]}")
        
    print("\n=== DAILY METRICS ===")
    cur.execute("SELECT trading_date, start_equity, current_equity, max_drawdown_percent, trades_today FROM daily_metrics ORDER BY trading_date DESC LIMIT 5")
    for r in cur.fetchall():
        print(f"Date: {r[0]} | StartEq: {r[1]} | CurrentEq: {r[2]} | MaxDD%: {r[3]} | TradesToday: {r[4]}")
        
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
