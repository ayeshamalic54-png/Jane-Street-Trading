import os
import sys
import requests
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import binance_execution
from dotenv import load_dotenv
load_dotenv()

# Execute GET /fapi/v2/balance
res = binance_execution.send_signed_request("GET", "/fapi/v2/balance")
print("Response Status:", res.status_code if res else "None")
if res and res.status_code == 200:
    for asset in res.json():
        if float(asset.get("balance", 0.0)) != 0.0 or asset.get("asset") == "USDT":
            print(asset)
else:
    print(res.text if res else "No response")
