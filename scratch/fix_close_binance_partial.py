import os

binance_path = os.path.join(os.path.dirname(__file__), "..", "binance_execution.py")

with open(binance_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """    logger.info(f"Binance Partial Close: {side} {rounded_qty} {symbol}")
    res = send_signed_request("POST", "/fapi/v1/order", params)
    if res and res.status_code == 200:
        logger.info(f"Successfully placed Binance close order for {symbol}")
        return True
    else:
        err_msg = res.text if res else "No response"
        logger.error(f"Binance close order failed: {err_msg}")
        return False"""

replacement = """    logger.info(f"Binance Partial Close: {side} {rounded_qty} {symbol}")
    res = send_signed_request("POST", "/fapi/v1/order", params)
    if res and res.status_code == 200:
        res_data = res.json()
        avg_price = float(res_data.get("avgPrice") or res_data.get("price") or 0.0)
        logger.info(f"Successfully placed Binance close order for {symbol} at avgPrice: {avg_price}")
        return avg_price
    else:
        err_msg = res.text if res else "No response"
        logger.error(f"Binance close order failed: {err_msg}")
        return None"""

if target in content:
    content = content.replace(target, replacement)
    print("Replacement successful.")
else:
    print("Target not found!")

with open(binance_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
