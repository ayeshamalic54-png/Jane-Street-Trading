import os

binance_path = os.path.join(os.path.dirname(__file__), "..", "binance_execution.py")

with open(binance_path, "r", encoding="utf-8") as f:
    content = f.read()

target_urls = """BASE_URL = "https://fapi.binance.com"
PUBLIC_BASE_URL = "https://fapi.binance.com/fapi/v1\""""

replacement_urls = """USE_TESTNET = os.getenv("USE_BINANCE_TESTNET", "false").lower() == "true"
if USE_TESTNET:
    BASE_URL = "https://testnet.binancefuture.com"
    PUBLIC_BASE_URL = "https://testnet.binancefuture.com/fapi/v1"
    logger.info("BINANCE CLIENT INITIALIZED IN TESTNET MODE")
else:
    BASE_URL = "https://fapi.binance.com"
    PUBLIC_BASE_URL = "https://fapi.binance.com/fapi/v1\""""

target_geo = 'if r.status_code == 451 and "fapi.binance.com" in url:'
replacement_geo = 'if r.status_code == 451 and ("fapi.binance.com" in url or "testnet.binancefuture.com" in url):'

target_geo2 = 'if "fapi.binance.com" in url:'
replacement_geo2 = 'if "fapi.binance.com" in url or "testnet.binancefuture.com" in url:'

target_geo3 = 'new_url = url.replace("https://fapi.binance.com/fapi/v1", "https://api.binance.us/api/v3")'
replacement_geo3 = 'new_url = url.replace(PUBLIC_BASE_URL, "https://api.binance.us/api/v3")'

if target_urls in content:
    content = content.replace(target_urls, replacement_urls)
    print("URLs updated.")
else:
    print("URLs target not found!")

if target_geo in content:
    content = content.replace(target_geo, replacement_geo)
    print("Geo fallback updated.")
else:
    print("Geo fallback target not found!")

if target_geo2 in content:
    content = content.replace(target_geo2, replacement_geo2)
    print("Geo fallback 2 updated.")
else:
    print("Geo fallback 2 target not found!")

if target_geo3 in content:
    content = content.replace(target_geo3, replacement_geo3)
    print("Geo fallback 3 updated.")
else:
    print("Geo fallback 3 target not found!")

with open(binance_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
