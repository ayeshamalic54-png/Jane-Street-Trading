import os

path = os.path.join(os.path.dirname(__file__), "..", "data_ingestion.py")

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Target block to add the account info check and return
target_block = """            else:
                logger.error(f"MT5 initialization failed. Error code: {mt5.last_error()}")
                sys.exit(1)"""

replacement_block = """            else:
                logger.error(f"MT5 initialization failed. Error code: {mt5.last_error()}")
                sys.exit(1)
                
    acc_info = mt5.account_info()
    if acc_info is None:
        logger.error("Failed to retrieve account info. Ensure MT5 terminal is open and logged in.")
        sys.exit(1)
        
    logger.info("Successfully connected to MetaTrader 5 Terminal!")
    logger.info(f"Login: {acc_info.login} | Server: {acc_info.server} | Balance: ${acc_info.balance:.2f} | Equity: ${acc_info.equity:.2f}")
    return acc_info"""

if target_block in content:
    content = content.replace(target_block, replacement_block)
    print("Successfully added account info fetch and return to initialize_mt5.")
else:
    print("Target block not found in data_ingestion.py!")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
