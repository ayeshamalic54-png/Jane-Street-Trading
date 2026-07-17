import requests

url = "https://jane-street-arbitrage.onrender.com/api/dashboard"
print(f"Fetching dashboard state from Render API: {url}")
try:
    r = requests.get(url, timeout=10)
    print(f"Status Code: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print("Keys in response:", list(data.keys()))
        print("forexState exists:", "forexState" in data)
        print("cryptoState exists:", "cryptoState" in data)
        if "forexState" in data:
            print("Forex state details:", data["forexState"])
        if "cryptoState" in data:
            print("Crypto state details:", data["cryptoState"])
    else:
        print("Response text:", r.text[:200])
except Exception as e:
    print(f"Error: {e}")
