import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from binance_execution import send_signed_request

try:
    # Check Futures Account Balance
    f_res = send_signed_request("GET", "/fapi/v2/balance")
    futures_bal = 0.0
    if f_res and f_res.status_code == 200:
        for asset in f_res.json():
            if asset["asset"] == "USDT":
                futures_bal = float(asset["balance"])
                print(f"Futures Wallet USDT Balance: {futures_bal} USDT")
    else:
        print(f"Failed to fetch Futures balance: {f_res.text if f_res else 'No response'}")

    # Check Spot Account Balance
    # Spot endpoint uses different base url or requires spot credentials?
    # Wait, Binance API key has access to both Spot and Futures.
    # Let's try to query Spot account info if possible.
    # Spot base url is https://api.binance.com, but send_signed_request is hardcoded to Futures URL.
    # Let's check how send_signed_request is implemented.
except Exception as e:
    print(f"Error: {e}")
