import os

binance_path = os.path.join(os.path.dirname(__file__), "..", "binance_execution.py")

with open(binance_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """def get_binance_usdt_balance():
    \"\"\"Fetches total and available USDT balance on Binance Futures.\"\"\"
    res = send_signed_request("GET", "/fapi/v2/balance")
    if res is not None and res.status_code == 200:
        data = res.json()
        for asset in data:
            if asset.get("asset") == "USDT":
                total = float(asset.get("balance", 0.0))
                available = float(asset.get("availableBalance", 0.0))
                return total, available
    else:
        status_code = res.status_code if res is not None else "None"
        err_msg = res.text if res is not None else "No response"
        if status_code == 451:
            logger.error("Binance Futures API is geo-blocked (status 451) on this server. To bypass this, please configure a proxy by adding 'BINANCE_PROXY=your_proxy_address' in your .env file.")
        else:
            logger.error(f"Failed to fetch Binance Futures balance (status {status_code}): {err_msg}")
    return 0.0, 0.0"""

replacement = """def get_binance_usdt_balance():
    \"\"\"Fetches total and available USD margin balance on Binance Futures (supports Multi-Asset and Single-Asset modes).\"\"\"
    res = send_signed_request("GET", "/fapi/v2/account")
    if res is not None and res.status_code == 200:
        data = res.json()
        total = float(data.get("totalWalletBalance", 0.0))
        available = float(data.get("availableBalance", 0.0))
        return total, available
    else:
        status_code = res.status_code if res is not None else "None"
        err_msg = res.text if res is not None else "No response"
        if status_code == 451:
            logger.error("Binance Futures API is geo-blocked (status 451) on this server. To bypass this, please configure a proxy by adding 'BINANCE_PROXY=your_proxy_address' in your .env file.")
        else:
            logger.error(f"Failed to fetch Binance Futures balance (status {status_code}): {err_msg}")
    return 0.0, 0.0"""

if target in content:
    content = content.replace(target, replacement)
    print("Replacement successful.")
else:
    print("Target not found!")

with open(binance_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
