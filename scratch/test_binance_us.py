import requests
import json

base_url = "https://api.binance.us"

print("=== TESTING BINANCE US TICK ===")
try:
    r = requests.get(f"{base_url}/api/v3/ticker/bookTicker", params={"symbol": "BTCUSDT"}, timeout=5)
    print(f"Status Code: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"BTCUSDT Tick: bid={data.get('bidPrice')} / ask={data.get('askPrice')}")
    else:
        print(f"Failed: {r.text}")
except Exception as e:
    print(f"Exception: {e}")

print("\n=== TESTING BINANCE US KLINES ===")
try:
    r = requests.get(f"{base_url}/api/v3/klines", params={"symbol": "BTCUSDT", "interval": "5m", "limit": 5}, timeout=5)
    print(f"Status Code: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"Loaded {len(data)} candles. Last close: {data[-1][4]}")
    else:
        print(f"Failed: {r.text}")
except Exception as e:
    print(f"Exception: {e}")
