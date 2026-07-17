import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import binance_execution
from dotenv import load_dotenv
load_dotenv()

res = binance_execution.send_signed_request("GET", "/fapi/v1/leverageBracket")
print("Response Status:", res.status_code if res else "None")
if res and res.status_code == 200:
    data = res.json()
    print("Number of symbols returned:", len(data))
    # Print the first bracket as sample
    if data:
        print("Sample Bracket (first element):", data[0])
else:
    print(res.text if res else "No response")
