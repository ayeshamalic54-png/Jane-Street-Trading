import os
import sys
import requests
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from binance_execution import PUBLIC_BASE_URL

try:
    r = requests.get(f"{PUBLIC_BASE_URL}/ticker/bookTicker")
    if r.status_code == 200:
        data = r.json()
        zec = [d for d in data if d["symbol"] == "ZECUSDT"]
        bnb = [d for d in data if d["symbol"] == "BNBUSDT"]
        print("=== BINANCE FUTURES REAL TICKERS ===")
        print("ZEC:", zec)
        print("BNB:", bnb)
    else:
        print("Failed to fetch bookTickers from Binance")
except Exception as e:
    print("Error:", e)
