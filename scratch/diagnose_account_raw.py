import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import binance_execution
from dotenv import load_dotenv
load_dotenv()

res = binance_execution.send_signed_request("GET", "/fapi/v2/account")
print("Response Status:", res.status_code if res else "None")
if res and res.status_code == 200:
    data = res.json()
    print("totalWalletBalance:", data.get("totalWalletBalance"))
    print("totalMarginBalance:", data.get("totalMarginBalance"))
    print("totalOpenOrderInitialMargin:", data.get("totalOpenOrderInitialMargin"))
    print("totalPositionInitialMargin:", data.get("totalPositionInitialMargin"))
    print("availableBalance:", data.get("availableBalance"))
else:
    print(res.text if res else "No response")
