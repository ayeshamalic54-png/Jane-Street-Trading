import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import binance_execution
from database import get_connection
from dotenv import load_dotenv
load_dotenv()

# 1. Fetch from Binance API
print("=== ACTUAL OPEN POSITIONS ON BINANCE ===")
res = binance_execution.send_signed_request("GET", "/fapi/v2/positionRisk")
binance_positions = []
if res and res.status_code == 200:
    for pos in res.json():
        amt = float(pos.get("positionAmt", 0.0))
        if amt != 0.0:
            p_data = {
                "symbol": pos.get("symbol"),
                "positionAmt": amt,
                "entryPrice": float(pos.get("entryPrice", 0.0)),
                "unrealizedProfit": float(pos.get("unRealizedProfit", 0.0)),
                "positionSide": pos.get("positionSide")
            }
            binance_positions.append(p_data)
            print(p_data)
else:
    print("Failed to fetch Binance positions:", res.text if res else "No response")

# 2. Fetch from Database
print("\n=== OPEN TRADES IN DATABASE ===")
try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT ticket, symbol, order_type, lots, entry_price, profit, comment, signal_id FROM trades WHERE status = 'OPEN'")
    db_positions = cur.fetchall()
    for p in db_positions:
        print({
            "ticket": p[0],
            "symbol": p[1],
            "order_type": p[2],
            "lots": float(p[3]),
            "entry_price": float(p[4]),
            "profit": float(p[5]),
            "comment": p[6],
            "signal_id": p[7]
        })
    cur.close()
    conn.close()
except Exception as e:
    print("Database error:", e)
