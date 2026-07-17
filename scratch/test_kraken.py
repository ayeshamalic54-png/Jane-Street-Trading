import requests

print("=== TESTING KRAKEN TICK ===")
try:
    # Kraken uses XXBTZUSD for BTCUSD
    r = requests.get("https://api.kraken.com/0/public/Ticker", params={"pair": "XBTUSD"}, timeout=5)
    print(f"Status Code: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        pair_data = data.get("result", {}).get("XXBTZUSD", {})
        # b is bid ([price, whole lot volume, lot volume])
        # a is ask ([price, whole lot volume, lot volume])
        bid = pair_data.get("b", [None])[0]
        ask = pair_data.get("a", [None])[0]
        print(f"Kraken BTCUSD Tick: bid={bid} / ask={ask}")
    else:
        print(f"Failed: {r.text}")
except Exception as e:
    print(f"Exception: {e}")

print("\n=== TESTING KRAKEN OHLC ===")
try:
    r = requests.get("https://api.kraken.com/0/public/OHLC", params={"pair": "XBTUSD", "interval": "5", "limit": 5}, timeout=5)
    print(f"Status Code: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        pair_data = data.get("result", {}).get("XXBTZUSD", [])
        print(f"Loaded {len(pair_data)} candles. Last close: {pair_data[-1][4] if pair_data else None}")
    else:
        print(f"Failed: {r.text}")
except Exception as e:
    print(f"Exception: {e}")
