import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import MetaTrader5 as mt5
from database import get_connection

print("=== CHECKING MT5 LIVE POSITIONS ===")
if mt5.initialize():
    positions = mt5.positions_get()
    if positions:
        for p in positions:
            side = "BUY" if p.type == 0 else "SELL"
            print(f"MT5 Ticket: {p.ticket} | Symbol: {p.symbol} | Type: {side} | Lots: {p.volume} | Entry: {p.price_open} | Current: {p.price_current} | Profit: ${p.profit:.2f}")
    else:
        print("No open positions currently in MT5 terminal.")
    mt5.shutdown()
else:
    print("Could not initialize MT5 terminal.")

print("\n=== CHECKING DATABASE OPEN TRADES ===")
try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT ticket, symbol, order_type, lots, entry_price, close_price, profit, comment FROM trades WHERE status = 'OPEN'")
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(f"DB Ticket: {r[0]} | Symbol: {r[1]} | Type: {r[2]} | Lots: {r[3]} | Entry: {r[4]} | Profit: ${r[6]} | Comment: {r[7]}")
    else:
        print("No open trades in PostgreSQL database.")
    cur.close()
    conn.close()
except Exception as e:
    print(f"DB Error: {e}")
