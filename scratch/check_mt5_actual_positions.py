import os
import sys
import MetaTrader5 as mt5
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import get_connection

if not mt5.initialize(path="C:\\Program Files\\MetaTrader 5\\terminal64.exe"):
    print("MT5 initialization failed:", mt5.last_error())
    sys.exit()

print("=== ACTUAL OPEN POSITIONS ON MT5 ===")
positions = mt5.positions_get()
if positions is None:
    print("No positions on MT5 or error:", mt5.last_error())
elif len(positions) == 0:
    print("No open positions on MT5.")
else:
    for pos in positions:
        print({
            "ticket": pos.ticket,
            "symbol": pos.symbol,
            "type": "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL",
            "volume": pos.volume,
            "price_open": pos.price_open,
            "price_current": pos.price_current,
            "profit": pos.profit,
            "comment": pos.comment
        })

# Check database open trades
print("\n=== OPEN TRADES IN DATABASE ===")
try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT ticket, symbol, order_type, lots, entry_price, profit, comment FROM trades WHERE status = 'OPEN'")
    db_positions = cur.fetchall()
    for p in db_positions:
        print({
            "ticket": p[0],
            "symbol": p[1],
            "order_type": p[2],
            "lots": float(p[3]),
            "entry_price": float(p[4]),
            "profit": float(p[5]),
            "comment": p[6]
        })
    cur.close()
    conn.close()
except Exception as e:
    print("Database error:", e)

mt5.shutdown()
