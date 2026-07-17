import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

# Define the self_heal_closed_trades function
self_heal_definition = """def self_heal_closed_trades():
    \"\"\"
    Self-healing logic: checks if any trades marked as CLOSED with 0.0 profit/price
    are actually still open in MT5, and restores them to OPEN.
    \"\"\"
    global FOREX_ENABLED, METALS_ENABLED, INDICES_ENABLED
    if not (FOREX_ENABLED or METALS_ENABLED or INDICES_ENABLED):
        return
        
    logger.info("Running database self-healing checks for active MT5 positions...")
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT ticket, symbol FROM trades WHERE status = 'CLOSED' AND close_price = 0.0")
        closed_zeros = cur.fetchall()
        
        if closed_zeros:
            # Fetch all active positions in MT5
            positions = mt5.positions_get()
            active_tickets = {p.ticket: p for p in positions} if positions else {}
            
            restored_count = 0
            for ticket, symbol in closed_zeros:
                if int(ticket) in active_tickets:
                    logger.info(f"[SELF-HEAL] Position ticket {ticket} ({symbol}) is actually still OPEN in MT5! Restoring status to OPEN in database.")
                    cur.execute("UPDATE trades SET status = 'OPEN', close_price = NULL, profit = NULL, exit_time = NULL WHERE ticket = %s", (int(ticket),))
                    restored_count += 1
            conn.commit()
            if restored_count > 0:
                logger.info(f"Self-healing complete. Restored {restored_count} active trades back to OPEN.")
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error in self_heal_closed_trades: {e}")

"""

# Insert self_heal_definition before get_hedge_quantity
target_insert = "def get_hedge_quantity"
if target_insert in content:
    content = content.replace(target_insert, self_heal_definition + "def get_hedge_quantity")
    print("self_heal_closed_trades definition inserted.")
else:
    print("get_hedge_quantity target not found!")

# Now replace the MT5 initialization and fallback block to:
# 1. Fallback only if is_crypto_only is True
# 2. Call self_heal_closed_trades() if initialization succeeds
target_init = """    mt5_required = (FOREX_ENABLED or METALS_ENABLED or INDICES_ENABLED)
    if mt5_required:
        acc_info = initialize_mt5()
        if acc_info is None:
            if CRYPTO_ENABLED:
                logger.warning("MT5 initialization failed. Falling back to Crypto-Only mode on this VPS!")
                FOREX_ENABLED = False
                METALS_ENABLED = False
                INDICES_ENABLED = False
                acc_info = None
                
                # Re-verify and reset active pair to crypto default
                s_a = GLOBAL_CONFIG.get("SYMBOL_A", "").upper()
                is_crypto = s_a.endswith("USDT") or "USDT" in s_a or any(x in s_a for x in ["BTC", "ETH", "SOL", "BNB", "AVAX", "XRP", "ADA", "DOGE", "MATIC", "POL", "LTC", "LINK", "DOT", "UNI", "SHIB"])
                if not is_crypto:
                    logger.warning("Resetting active pair to BTCUSDT/ETHUSDT default for Crypto-only fallback.")
                    GLOBAL_CONFIG["SYMBOL_A"] = "BTCUSDT"
                    GLOBAL_CONFIG["SYMBOL_B"] = "ETHUSDT"
                    save_config("BTCUSDT/ETHUSDT")
            else:
                logger.error("MT5 initialization failed and Crypto is disabled. Exiting.")
                sys.exit(1)
    else:
        logger.info("Only Crypto is enabled. Skipping MT5 initialization on startup.")
        acc_info = None"""

replacement_init = """    mt5_required = (FOREX_ENABLED or METALS_ENABLED or INDICES_ENABLED)
    if mt5_required:
        acc_info = initialize_mt5()
        if acc_info is None:
            is_crypto_only = (os.getenv("OVERRIDE_CRYPTO_ENABLED") == "True") and (os.getenv("OVERRIDE_FOREX_ENABLED", "False").lower() != "true")
            if is_crypto_only and CRYPTO_ENABLED:
                logger.warning("MT5 initialization failed. Falling back to Crypto-Only mode on this Crypto VPS!")
                FOREX_ENABLED = False
                METALS_ENABLED = False
                INDICES_ENABLED = False
                acc_info = None
                
                # Re-verify and reset active pair to crypto default
                s_a = GLOBAL_CONFIG.get("SYMBOL_A", "").upper()
                is_crypto = s_a.endswith("USDT") or "USDT" in s_a or any(x in s_a for x in ["BTC", "ETH", "SOL", "BNB", "AVAX", "XRP", "ADA", "DOGE", "MATIC", "POL", "LTC", "LINK", "DOT", "UNI", "SHIB"])
                if not is_crypto:
                    logger.warning("Resetting active pair to BTCUSDT/ETHUSDT default for Crypto-only fallback.")
                    GLOBAL_CONFIG["SYMBOL_A"] = "BTCUSDT"
                    GLOBAL_CONFIG["SYMBOL_B"] = "ETHUSDT"
                    save_config("BTCUSDT/ETHUSDT")
            else:
                logger.error("MT5 initialization failed on this Forex VPS. Ensure MT5 terminal is open and logged in! Exiting.")
                sys.exit(1)
        else:
            self_heal_closed_trades()
    else:
        logger.info("Only Crypto is enabled. Skipping MT5 initialization on startup.")
        acc_info = None"""

if target_init in content:
    content = content.replace(target_init, replacement_init)
    print("MT5 initialization block updated with self-heal and strict Forex VPS exit.")
else:
    print("target_init block not found!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
