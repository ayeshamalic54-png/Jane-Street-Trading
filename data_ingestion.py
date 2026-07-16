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

def resolve_broker_symbol(symbol: str) -> str:
    symbol_upper = symbol.upper()
    # Check if symbol is already valid in MT5
    info = mt5.symbol_info(symbol_upper)
    if info is not None:
        return symbol_upper

    # Check common index aliases
    aliases = {
        "NAS100": ["USTEC", "US100", "NDX", ".US100", "NAS100.cash", "USTEC.cash", "US100.cash"],
        "US500": ["SPX", "SPX500", "US500.cash", "SPX500.cash", ".US500"],
        "US30": ["DJI", "US30.cash", "DJI.cash", ".US30"],
        "GER30": ["DE30", "DAX30", "GER30.cash", "DE30.cash"],
    }
    
    if symbol_upper in aliases:
        for alias in aliases[symbol_upper]:
            if mt5.symbol_info(alias) is not None:
                logger.info(f"Resolved symbol alias: {symbol_upper} -> {alias}")
                return alias

    # Try common suffixes for stocks (e.g. AAPL -> AAPL.us, AAPL.cfd, AAPL#US)
    suffixes = [".us", ".cfd", "#US", ".m", ".c", ".s", ".h"]
    for suf in suffixes:
        test_sym = f"{symbol_upper}{suf}"
        if mt5.symbol_info(test_sym) is not None:
            logger.info(f"Resolved stock alias: {symbol_upper} -> {test_sym}")
            return test_sym
            
    # Try searching the entire MT5 symbols list for a partial match
    try:
        all_syms = mt5.symbols_get()
        if all_syms:
            for s in all_syms:
                s_name = s.name.upper()
                if symbol_upper in s_name or s_name in symbol_upper:
                    logger.info(f"Resolved partial match: {symbol_upper} -> {s.name}")
                    return s.name
    except Exception:
        pass

    return symbol_upper

SUBSCRIBED_SYMBOLS = set()

def check_and_subscribe_symbol(symbol):
    """Ensures that the symbol is visible in the Market Watch and subscribes to its order book."""
    resolved = resolve_broker_symbol(symbol)
    if resolved in SUBSCRIBED_SYMBOLS:
        return True
        
    # Check if the symbol is valid/exists in MT5
    info = mt5.symbol_info(resolved)
    if info is None:
        logger.error(f"Symbol {resolved} is invalid or not found in the broker's database.")
        return False
        
    # If the symbol is valid but not visible, select/add it to Market Watch
    if not info.visible:
        selected = mt5.symbol_select(resolved, True)
        if not selected:
            logger.warning(f"Could not select symbol {resolved} in Market Watch (proceeding anyway)")
        else:
            logger.info(f"Symbol {resolved} successfully added to Market Watch watchlist")
        
    # Subscribe to L2 depth of market book
    book_sub = mt5.market_book_add(resolved)
    SUBSCRIBED_SYMBOLS.add(resolved)
    if book_sub:
        logger.info(f"Subscribed to Order Book updates for {resolved}")
    else:
        logger.warning(f"Could not subscribe to Order Book for {resolved} (Level-2 depth might be disabled by broker)")
        
    return True

def get_rates_df(symbol, timeframe, count=200):
    """Fetches historical price candles and returns them as a pandas DataFrame."""
    resolved = resolve_broker_symbol(symbol)
    rates = mt5.copy_rates_from_pos(resolved, timeframe, 0, count)
    if rates is None:
        logger.error(f"Failed to fetch rates for {resolved} (requested: {symbol}). Error: {mt5.last_error()}")
        return None
        
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

def get_live_ticks(symbol):
    """Fetches the latest tick (bid, ask, time) for a symbol."""
    resolved = resolve_broker_symbol(symbol)
    tick = mt5.symbol_info_tick(resolved)
    if tick is None:
        logger.warning(f"Failed to get live tick for {resolved} (requested: {symbol})")
        return None
    return tick

def get_market_book(symbol):
    """
    Fetches the Level-2 order book depth from MT5.
    Returns: (bids, asks) where each is a list of (price, volume) tuples.
    """
    resolved = resolve_broker_symbol(symbol)
    book = mt5.market_book_get(resolved)
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
            resolved = resolve_broker_symbol(symbol)
            mt5.market_book_release(resolved)
        except Exception:
            pass
    mt5.shutdown()
    logger.info("MT5 connection closed.")
