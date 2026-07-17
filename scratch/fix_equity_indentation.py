import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """            # Determine equity based strictly on the VPS type (Hybrid support)
            is_crypto_only = (os.getenv("OVERRIDE_CRYPTO_ENABLED") == "True") and (os.getenv("OVERRIDE_FOREX_ENABLED", "False").lower() != "true")
            binance_equity = 0.0
            mt5_equity = 0.0
            
            if CRYPTO_ENABLED:
                try:
                    usdt_bal, _ = get_binance_usdt_balance()
                    unrealized_pnl = 0.0
                    pos_res = send_signed_request("GET", "/fapi/v2/positionRisk")
                    if pos_res is not None and pos_res.status_code == 200:
                        for pos in pos_res.json():
                            amt = float(pos.get("positionAmt", 0.0))
                            if amt != 0.0:
                                unrealized_pnl += float(pos.get("unRealizedProfit", 0.0))
                    binance_equity = usdt_bal + unrealized_pnl
                except Exception as eq_err:
                    logger.error(f"Error calculating crypto equity: {eq_err}")
                    
            if FOREX_ENABLED or METALS_ENABLED or INDICES_ENABLED:
                try:
                    acc_info = mt5.account_info()
                    if acc_info:
                        mt5_equity = float(acc_info.equity)
                except Exception as mt5_eq_err:
                    logger.error(f"Error calculating MT5 equity: {mt5_eq_err}")
            
            # If strictly running crypto, use binance_equity. If hybrid or forex-only, combine or use MT5.
            if is_crypto_only:
                current_equity = binance_equity
            elif not CRYPTO_ENABLED:
                current_equity = mt5_equity
            else:
                current_equity = binance_equity  # Default to binance balance for challenge if both are active, or combine:
                # Let's combine them for overall dashboard visibility if both are active
                current_equity = binance_equity + mt5_equity
                    current_equity = 0.0
            else:
                current_equity = acc_info.equity if acc_info else 0.0"""

replacement = """            # Determine equity based strictly on the VPS type (Hybrid support)
            is_crypto_only = (os.getenv("OVERRIDE_CRYPTO_ENABLED") == "True") and (os.getenv("OVERRIDE_FOREX_ENABLED", "False").lower() != "true")
            binance_equity = 0.0
            mt5_equity = 0.0
            
            if CRYPTO_ENABLED:
                try:
                    usdt_bal, _ = get_binance_usdt_balance()
                    unrealized_pnl = 0.0
                    pos_res = send_signed_request("GET", "/fapi/v2/positionRisk")
                    if pos_res is not None and pos_res.status_code == 200:
                        for pos in pos_res.json():
                            amt = float(pos.get("positionAmt", 0.0))
                            if amt != 0.0:
                                unrealized_pnl += float(pos.get("unRealizedProfit", 0.0))
                    binance_equity = usdt_bal + unrealized_pnl
                except Exception as eq_err:
                    logger.error(f"Error calculating crypto equity: {eq_err}")
                    
            if FOREX_ENABLED or METALS_ENABLED or INDICES_ENABLED:
                try:
                    acc_info = mt5.account_info()
                    if acc_info:
                        mt5_equity = float(acc_info.equity)
                except Exception as mt5_eq_err:
                    logger.error(f"Error calculating MT5 equity: {mt5_eq_err}")
            
            # If strictly running crypto, use binance_equity. If hybrid or forex-only, combine or use MT5.
            if is_crypto_only:
                current_equity = binance_equity
            elif not CRYPTO_ENABLED:
                current_equity = mt5_equity
            else:
                # Let's combine them for overall dashboard visibility if both are active
                current_equity = binance_equity + mt5_equity"""

if target in content:
    content = content.replace(target, replacement)
    print("Indentation error fixed.")
else:
    print("Target not found!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
