import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update get_symbol_category to check is_crypto_only
target_cat = """def get_symbol_category(symbol: str) -> str:
    if os.getenv("OVERRIDE_CRYPTO_ENABLED") == "True":
        return "crypto"
    s = symbol.upper()"""

replacement_cat = """def get_symbol_category(symbol: str) -> str:
    is_crypto_only = (os.getenv("OVERRIDE_CRYPTO_ENABLED") == "True") and (os.getenv("OVERRIDE_FOREX_ENABLED", "False").lower() != "true")
    if is_crypto_only:
        return "crypto"
    s = symbol.upper()"""

if target_cat in content:
    content = content.replace(target_cat, replacement_cat)
    print("get_symbol_category updated.")
else:
    print("get_symbol_category target not found!")

# 2. Update category constraints on startup (around line 1158)
target_constraints = """        # Enforce VPS-specific category constraints
        is_crypto_vps = os.getenv("OVERRIDE_CRYPTO_ENABLED") == "True"
        if is_crypto_vps:
            CRYPTO_ENABLED = startup_crypto
            METALS_ENABLED = False
            FOREX_ENABLED = False
            INDICES_ENABLED = False"""

replacement_constraints = """        # Enforce VPS-specific category constraints (Hybrid support)
        is_crypto_only = (os.getenv("OVERRIDE_CRYPTO_ENABLED") == "True") and (os.getenv("OVERRIDE_FOREX_ENABLED", "False").lower() != "true")
        if is_crypto_only:
            CRYPTO_ENABLED = startup_crypto
            METALS_ENABLED = False
            FOREX_ENABLED = False
            INDICES_ENABLED = False
        else:
            CRYPTO_ENABLED = startup_crypto
            METALS_ENABLED = startup_metals
            FOREX_ENABLED = startup_forex
            INDICES_ENABLED = startup_indices"""

if target_constraints in content:
    content = content.replace(target_constraints, replacement_constraints)
    print("Startup category constraints updated.")
else:
    print("Startup category constraints target not found!")

# 3. Update close_orphan_spread_legs to close based on active settings rather than hardcoded is_crypto_vps
target_orphan = """                    if cat == "crypto":
                        if is_crypto_vps:
                            is_long = (order_type.upper() == "BUY")
                            logger.info(f"[ORPHAN CLOSER] Closing crypto leg {orphan_symbol} (lots: {lots}) on Binance...")
                            close_binance_partial(orphan_symbol, lots, is_long)
                            send_signed_request("DELETE", "/fapi/v1/allOpenOrders", {"symbol": orphan_symbol})
                            
                            # Fetch price for close log
                            tick = get_binance_live_tick(orphan_symbol)
                            live_p = (tick.bid + tick.ask) / 2.0 if tick else 0.0
                            mult = 1.0 if order_type.upper() == "BUY" else -1.0
                            calc_profit = (live_p - float(entry_price)) * float(lots) * mult
                            log_trade_exit(ticket, live_p, calc_profit, datetime.datetime.now())
                    else:
                        if not is_crypto_vps:
                            logger.info(f"[ORPHAN CLOSER] Closing MT5 leg {orphan_symbol} (ticket: {ticket})...")
                            close_position_by_ticket(ticket)"""

replacement_orphan = """                    if cat == "crypto":
                        if CRYPTO_ENABLED:
                            is_long = (order_type.upper() == "BUY")
                            logger.info(f"[ORPHAN CLOSER] Closing crypto leg {orphan_symbol} (lots: {lots}) on Binance...")
                            close_binance_partial(orphan_symbol, lots, is_long)
                            send_signed_request("DELETE", "/fapi/v1/allOpenOrders", {"symbol": orphan_symbol})
                            
                            # Fetch price for close log
                            tick = get_binance_live_tick(orphan_symbol)
                            live_p = (tick.bid + tick.ask) / 2.0 if tick else 0.0
                            mult = 1.0 if order_type.upper() == "BUY" else -1.0
                            calc_profit = (live_p - float(entry_price)) * float(lots) * mult
                            log_trade_exit(ticket, live_p, calc_profit, datetime.datetime.now())
                    else:
                        if FOREX_ENABLED or METALS_ENABLED or INDICES_ENABLED:
                            logger.info(f"[ORPHAN CLOSER] Closing MT5 leg {orphan_symbol} (ticket: {ticket})...")
                            close_position_by_ticket(ticket)"""

if target_orphan in content:
    content = content.replace(target_orphan, replacement_orphan)
    print("Orphan closer updated.")
else:
    print("Orphan closer target not found!")

# 4. Update equity check to sum both when hybrid mode is active
target_equity = """            # Determine equity based strictly on the VPS type
            is_crypto_vps = os.getenv("OVERRIDE_CRYPTO_ENABLED") == "True"
            if is_crypto_vps:
                try:
                    usdt_bal, _ = get_binance_usdt_balance()
                    unrealized_pnl = 0.0
                    pos_res = send_signed_request("GET", "/fapi/v2/positionRisk")
                    if pos_res is not None and pos_res.status_code == 200:
                        for pos in pos_res.json():
                            amt = float(pos.get("positionAmt", 0.0))
                            if amt != 0.0:
                                unrealized_pnl += float(pos.get("unRealizedProfit", 0.0))
                    current_equity = usdt_bal + unrealized_pnl
                except Exception as eq_err:
                    logger.error(f"Error calculating crypto equity: {eq_err}")"""

replacement_equity = """            # Determine equity based strictly on the VPS type (Hybrid support)
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
                current_equity = binance_equity + mt5_equity"""

if target_equity in content:
    content = content.replace(target_equity, replacement_equity)
    print("Equity logic updated.")
else:
    print("Equity logic target not found!")

# 5. Fix filter candidate_signals in scan loop (skip non-crypto check)
target_filter = """                    # If this is a Crypto-only VPS, strictly skip non-crypto pairs
                    if is_crypto_vps:
                        if cat_a_sig != "crypto" or cat_b_sig != "crypto":
                            continue"""

replacement_filter = """                    # If this is a Crypto-only VPS, strictly skip non-crypto pairs
                    is_crypto_only = (os.getenv("OVERRIDE_CRYPTO_ENABLED") == "True") and (os.getenv("OVERRIDE_FOREX_ENABLED", "False").lower() != "true")
                    if is_crypto_only:
                        if cat_a_sig != "crypto" or cat_b_sig != "crypto":
                            continue"""

if target_filter in content:
    content = content.replace(target_filter, replacement_filter)
    print("Candidate signals filtering updated.")
else:
    print("Candidate signals filtering target not found!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
