import MetaTrader5 as mt5
import pandas as pd
import logging
import sys
import os

logger = logging.getLogger("SMC_Forex_Bot")

def load_env():
    """Loads env variables from a local .env file."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("=", 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip()
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    os.environ[key] = val

def initialize_mt5():
    """Initializes MetaTrader 5 terminal and connection, performing login if credentials exist."""
    load_env()
    terminal_path = "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
    
    login = os.getenv("MT5_LOGIN")
    password = os.getenv("MT5_PASSWORD")
    server = os.getenv("MT5_SERVER")
    
    if login and password and server:
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
        sys.exit(1)
        
    logger.info("Successfully connected to MetaTrader 5 Terminal!")
    logger.info(f"Login: {acc_info.login} | Server: {acc_info.server} | Balance: ${acc_info.balance:.2f} | Equity: ${acc_info.equity:.2f}")
    return acc_info

def check_and_subscribe_symbol(symbol):
    """Ensures that the symbol is visible in the Market Watch and subscribes to its order book."""
    selected = mt5.symbol_select(symbol, True)
    if not selected:
        logger.error(f"Symbol {symbol} is not available in the Market Watch or is invalid.")
        return False
        
    # Subscribe to L2 depth of market book
    book_sub = mt5.market_book_add(symbol)
    if book_sub:
        logger.info(f"Subscribed to Order Book updates for {symbol}")
    else:
        logger.warning(f"Could not subscribe to Order Book for {symbol} (Level-2 depth might be disabled by broker)")
        
    return True

def get_rates_df(symbol, timeframe, count=200):
    """Fetches historical price candles and returns them as a pandas DataFrame."""
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    if rates is None:
        logger.error(f"Failed to fetch rates for {symbol}. Error: {mt5.last_error()}")
        return None
        
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

def get_live_ticks(symbol):
    """Fetches the latest tick (bid, ask, time) for a symbol."""
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        logger.warning(f"Failed to get live tick for {symbol}")
        return None
    return tick

def get_market_book(symbol):
    """
    Fetches the Level-2 order book depth from MT5.
    Returns: (bids, asks) where each is a list of (price, volume) tuples.
    """
    book = mt5.market_book_get(symbol)
    if book is None:
        # If market depth is unavailable, return empty lists
        return [], []
        
    bids = []
    asks = []
    
    for level in book:
        price = level.price
        # volume_real is available in newer MT5 versions, fallback to volume
        volume = level.volume_real if hasattr(level, 'volume_real') else level.volume
        
        # level.type values:
        # mt5.BOOK_TYPE_BUY: Bid (Buy Order)
        # mt5.BOOK_TYPE_SELL: Ask (Sell Order)
        if level.type == mt5.BOOK_TYPE_BUY:
            bids.append((price, volume))
        elif level.type == mt5.BOOK_TYPE_SELL:
            asks.append((price, volume))
            
    # Sort bids descending (highest buy price first) and asks ascending (lowest sell price first)
    bids.sort(key=lambda x: x[0], reverse=True)
    asks.sort(key=lambda x: x[0])
    
    return bids, asks

def shutdown_mt5(symbol=None):
    """Cleans up subscriptions and shuts down MT5 connection."""
    if symbol:
        try:
            mt5.market_book_release(symbol)
        except Exception:
            pass
    mt5.shutdown()
    logger.info("MT5 connection closed.")
