import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import binance_execution
from dotenv import load_dotenv
load_dotenv()

# Test leverage setting for LABUSDT
res_lev = binance_execution.send_signed_request("POST", "/fapi/v1/leverage", {"symbol": "LABUSDT", "leverage": 20})
print("LABUSDT Leverage Set Status:", res_lev.status_code if res_lev else "None")
print("Response:", res_lev.text if res_lev else "No response")

# Test leverage setting for ALPINEUSDT
res_lev2 = binance_execution.send_signed_request("POST", "/fapi/v1/leverage", {"symbol": "ALPINEUSDT", "leverage": 20})
print("ALPINEUSDT Leverage Set Status:", res_lev2.status_code if res_lev2 else "None")
print("Response:", res_lev2.text if res_lev2 else "No response")
