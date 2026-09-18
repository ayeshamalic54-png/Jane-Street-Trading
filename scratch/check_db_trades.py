import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_connection

print("=== DB OPEN TRADES ===")
try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT ticket, symbol, order_type, lots, entry_price, close_price, profit, comment FROM trades WHERE status = 'OPEN'")
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(f"Ticket #{r[0]} | Symbol: {r[1]} | Type: {r[2]} | Lots: {r[3]} | Entry: {r[4]} | Profit: ${r[6]} | Comment: {r[7]}")
    else:
        print("No open trades currently in database (0 open trades).")

    print("\n=== BOT STATE METRICS ===")
    cur.execute("SELECT default_lots, active_pair, equity, drawdown_percent, trades_today, auto_execute FROM bot_state WHERE id = 1")
    bs = cur.fetchone()
    if bs:
        print(f"Default Lot Size Config: {bs[0]} lots")
        print(f"Active Pair: {bs[1]}")
        print(f"Equity: ${bs[2]}")
        print(f"Drawdown: {bs[3]}%")
        print(f"Trades Today: {bs[4]}")
        print(f"Auto Execute: {bs[5]}")
    cur.close()
    conn.close()
except Exception as e:
    print(f"DB Error: {e}")
