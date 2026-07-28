import MetaTrader5 as mt5
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("check_account")

if not mt5.initialize():
    logger.error("MT5 initialize failed")
else:
    logger.info("Connected to MT5 successfully")
    acct_info = mt5.account_info()
    if acct_info:
        logger.info(f"Login: {acct_info.login}")
        logger.info(f"Trade Mode: {acct_info.trade_mode}")
        logger.info(f"Server: {acct_info.server}")
        logger.info(f"Company: {acct_info.company}")
        logger.info(f"Balance: {acct_info.balance}")
        logger.info(f"Equity: {acct_info.equity}")
    else:
        logger.error("Failed to retrieve account info")
    mt5.shutdown()
