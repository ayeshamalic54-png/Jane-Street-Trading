import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import binance_execution
from dotenv import load_dotenv
load_dotenv()

# 1. Check account balance details
print("=== BINANCE FUTURES BALANCE INFO ===")
res_acc = binance_execution.send_signed_request("GET", "/fapi/v2/account")
if res_acc and res_acc.status_code == 200:
    data = res_acc.json()
    print("totalWalletBalance:", data.get("totalWalletBalance"))
    print("totalMarginBalance:", data.get("totalMarginBalance"))
    print("totalUnrealizedProfit:", data.get("totalUnrealizedProfit"))
    print("availableBalance:", data.get("availableBalance"))
else:
    print("Failed to get account info:", res_acc.text if res_acc else "No response")

# 2. Check open orders
print("\n=== OPEN ORDERS ON BINANCE ===")
res_orders = binance_execution.send_signed_request("GET", "/fapi/v1/openOrders")
if res_orders and res_orders.status_code == 200:
    orders = res_orders.json()
    if not orders:
        print("No open orders.")
    for o in orders:
        print({
            "orderId": o.get("orderId"),
            "symbol": o.get("symbol"),
            "side": o.get("side"),
            "type": o.get("type"),
            "price": o.get("price"),
            "origQty": o.get("origQty")
        })
else:
    print("Failed to get open orders:", res_orders.text if res_orders else "No response")

# 3. Check recent user trades
print("\n=== RECENT USER TRADES (LAST 5) ===")
res_trades = binance_execution.send_signed_request("GET", "/fapi/v1/userTrades", {"limit": 5})
if res_trades and res_trades.status_code == 200:
    trades = res_trades.json()
    if not trades:
        print("No recent trades.")
    for t in trades:
        print({
            "id": t.get("id"),
            "symbol": t.get("symbol"),
            "side": "BUY" if t.get("buyer") else "SELL",
            "price": t.get("price"),
            "qty": t.get("qty"),
            "realizedProfit": t.get("realizedProfit"),
            "time": t.get("time")
        })
else:
    print("Failed to get user trades:", res_trades.text if res_trades else "No response")
