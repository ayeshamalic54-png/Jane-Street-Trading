import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")
ingestion_path = os.path.join(os.path.dirname(__file__), "..", "data_ingestion.py")

# 1. Modify data_ingestion.py initialize_mt5 to return None instead of calling sys.exit(1)
with open(ingestion_path, "r", encoding="utf-8") as f:
    ing_content = f.read()

target_ing = """    if login and password and server:
        logger.info(f"Attempting programmatic login to Server: {server} Account: {login}...")
        try:
            login_int = int(login)
            if not mt5.initialize(path=terminal_path, login=login_int, password=password, server=server, timeout=60000):
                logger.error(f"MT5 initialization and login failed. Error code: {mt5.last_error()}")
                sys.exit(1)
            logger.info("Programmatic login successful!")
        except ValueError:
            logger.error("MT5_LOGIN in .env must be an integer account number.")
            sys.exit(1)
    else:
        logger.info(f"Initializing MT5 using path: {terminal_path} (no credentials provided)")
        if not mt5.initialize(path=terminal_path, timeout=60000):
            logger.error(f"MT5 initialization failed. Error code: {mt5.last_error()}")
            sys.exit(1)
            
    acc_info = mt5.account_info()
    if acc_info is None:
        logger.error("Failed to retrieve account info. Ensure MT5 terminal is open and logged in.")
        sys.exit(1)"""

replacement_ing = """    if login and password and server:
        logger.info(f"Attempting programmatic login to Server: {server} Account: {login}...")
        try:
            login_int = int(login)
            if not mt5.initialize(path=terminal_path, login=login_int, password=password, server=server, timeout=60000):
                logger.error(f"MT5 initialization and login failed. Error code: {mt5.last_error()}")
                return None
            logger.info("Programmatic login successful!")
        except ValueError:
            logger.error("MT5_LOGIN in .env must be an integer account number.")
            return None
    else:
        logger.info(f"Initializing MT5 using path: {terminal_path} (no credentials provided)")
        if not mt5.initialize(path=terminal_path, timeout=60000):
            logger.error(f"MT5 initialization failed. Error code: {mt5.last_error()}")
            return None
            
    acc_info = mt5.account_info()
    if acc_info is None:
        logger.error("Failed to retrieve account info. Ensure MT5 terminal is open and logged in.")
        return None"""

if target_ing in ing_content:
    ing_content = ing_content.replace(target_ing, replacement_ing)
    print("data_ingestion.py MT5 return updates applied.")
else:
    print("data_ingestion.py target not found!")

with open(ingestion_path, "w", encoding="utf-8") as f:
    f.write(ing_content)

# 2. Modify main.py MT5 initialization fallback block
with open(main_path, "r", encoding="utf-8") as f:
    main_content = f.read()

target_main = """    mt5_required = (FOREX_ENABLED or METALS_ENABLED or INDICES_ENABLED)
    if mt5_required:
        acc_info = initialize_mt5()
    else:
        logger.info("Only Crypto is enabled. Skipping MT5 initialization on startup.")
        acc_info = None"""

replacement_main = """    mt5_required = (FOREX_ENABLED or METALS_ENABLED or INDICES_ENABLED)
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

if target_main in main_content:
    main_content = main_content.replace(target_main, replacement_main)
    print("main.py MT5 fallback logic applied.")
else:
    print("main.py target not found!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(main_content)

print("Both files updated.")
