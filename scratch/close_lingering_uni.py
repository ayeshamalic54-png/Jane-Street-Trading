import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from binance_execution import send_signed_request
from database import get_connection

try:
    # 1. Fetch current UNIUSDT position from Binance
    res = send_signed_request("GET", "/fapi/v2/positionRisk", {"symbol": "UNIUSDT"})
    if res is not None and res.status_code == 200:
        positions = res.json()
        uni_pos = None
        for pos in positions:
            if pos.get("symbol") == "UNIUSDT":
                uni_pos = pos
                break
        
        if uni_pos:
            amt = float(uni_pos.get("positionAmt", 0.0))
            if amt != 0.0:
                print(f"Found active UNIUSDT position on Binance: {amt}")
                # Close the position by placing a market order with opposite side
                side = "SELL" if amt > 0 else "BUY"
                close_qty = abs(amt)
                
                params = {
                    "symbol": "UNIUSDT",
                    "side": side,
                    "type": "MARKET",
                    "quantity": close_qty,
                    "reduceOnly": "true"
                }
                close_res = send_signed_request("POST", "/fapi/v1/order", params)
                if close_res and close_res.status_code == 200:
                    print(f"Successfully closed UNIUSDT position of {close_qty} on Binance!")
                    # Cancel any open orders for UNI
                    send_signed_request("DELETE", "/fapi/v1/allOpenOrders", {"symbol": "UNIUSDT"})
                else:
                    print(f"Failed to close position on Binance: {close_res.text if close_res else 'No response'}")
            else:
                print("No active UNIUSDT position found on Binance (positionAmt is 0.0).")
        else:
            print("UNIUSDT not found in positionRisk response.")
            
    # 2. Also ensure all database UNI trades are closed
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE trades SET status = 'CLOSED', close_time = NOW() WHERE symbol = 'UNIUSDT' AND status = 'OPEN'")
    conn.commit()
    print(f"Marked {cur.rowcount} UNIUSDT database trades as CLOSED.")
    cur.close()
    conn.close()

except Exception as e:
    print(f"Error in close script: {e}")
