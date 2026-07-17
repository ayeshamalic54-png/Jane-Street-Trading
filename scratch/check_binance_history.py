import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from binance_execution import send_signed_request

# Fetch recent user trades for BNBUSDT
r = send_signed_request("GET", "/fapi/v1/userTrades", {"symbol": "BNBUSDT", "limit": 20})
if r is not None and r.status_code == 200:
    trades = r.json()
    print("=== BNBUSDT USER TRADES (BINANCE) ===")
    for t in trades:
        print(f"Time: {t.get('time')} | Qty: {t.get('qty')} | Price: {t.get('price')} | Realized Pnl: {t.get('realizedProfit')} | Side: {t.get('side')} | OrderId: {t.get('orderId')}")
else:
    print(f"Failed to fetch user trades: {r.text if r else 'No response'}")

# Fetch recent orders for BNBUSDT
r_ord = send_signed_request("GET", "/fapi/v1/allOrders", {"symbol": "BNBUSDT", "limit": 20})
if r_ord is not None and r_ord.status_code == 200:
    orders = r_ord.json()
    print("\n=== BNBUSDT ALL ORDERS (BINANCE) ===")
    for o in orders:
        print(f"OrderId: {o.get('orderId')} | Side: {o.get('side')} | Type: {o.get('type')} | Price: {o.get('price')} | StopPrice: {o.get('stopPrice')} | Status: {o.get('status')} | Time: {o.get('updateTime')}")
else:
    print(f"Failed to fetch orders: {r_ord.text if r_ord else 'No response'}")
