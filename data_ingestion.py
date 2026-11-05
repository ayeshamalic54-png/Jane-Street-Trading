import MetaTrader5 as mt5
import pandas as pd
import logging
import sys
import os
import time

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
        logger.info("Initializing MT5 using currently running terminal instance (no path or credentials provided)")
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

_SUBSCRIBED_SYMBOLS = set()

def check_and_subscribe_symbol(symbol):
    """Ensures that the symbol is visible in the Market Watch and subscribes to its order book once."""
    global _SUBSCRIBED_SYMBOLS
    if symbol in _SUBSCRIBED_SYMBOLS:
        return True
        
    resolved = resolve_broker_symbol(symbol)
    selected = mt5.symbol_select(resolved, True)
    if not selected:
        selected = mt5.symbol_select(symbol, True)
        
    if not selected:
        logger.info(f"Symbol {symbol} (or broker alias) is not offered by your broker account. Skipping scan for this symbol.")
        return False
        
    # Subscribe to L2 depth of market book
    book_sub = mt5.market_book_add(resolved)
    _SUBSCRIBED_SYMBOLS.add(symbol)
    _SUBSCRIBED_SYMBOLS.add(resolved)
    if book_sub:
        logger.info(f"Subscribed to Order Book updates for {resolved}")
    else:
        logger.info(f"Market Watch active for {resolved} (Level-1 Bid/Ask ticks active; L2 DOM depth not required).")
        
    return True



def get_rates_df(symbol, timeframe, count=200):
    """Fetches historical price candles and returns them as a pandas DataFrame."""
    resolved = resolve_broker_symbol(symbol)
    
    # Ensure symbol is selected in MT5 Market Watch
    try:
        mt5.symbol_select(resolved, True)
        if resolved != symbol:
            mt5.symbol_select(symbol, True)
    except Exception:
        pass

    rates = None
    for attempt in range(5):
        rates = mt5.copy_rates_from_pos(resolved, timeframe, 0, count)
        if rates is not None and len(rates) > 0:
            break
        if resolved != symbol:
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
            if rates is not None and len(rates) > 0:
                resolved = symbol
                break
        
        # Poke tick data to trigger MT5 history stream download from broker
        if attempt == 0:
            try:
                mt5.symbol_info_tick(resolved)
            except Exception:
                pass

        time.sleep(0.2 * (attempt + 1))

    # Fast targeted fallback without dumping full symbol database
    if rates is None or len(rates) == 0:
        try:
            target_base = symbol.upper().replace("USD", "").replace("EUR", "")
            if len(target_base) >= 3:
                group_syms = mt5.symbols_get(group=f"*{target_base}*")
                if group_syms:
                    for s_info in group_syms:
                        if s_info.trade_mode == mt5.SYMBOL_TRADE_MODE_DISABLED:
                            continue
                        s_name = s_info.name
                        mt5.symbol_select(s_name, True)
                        r_try = mt5.copy_rates_from_pos(s_name, timeframe, 0, count)
                        if r_try is not None and len(r_try) > 0:
                            rates = r_try
                            logger.info(f"Resolved alternative tradeable symbol {s_name} for {symbol} candles.")
                            _RESOLVED_CACHE[symbol.strip().upper()] = s_name
                            break
        except Exception:
            pass

    if rates is None or len(rates) == 0:
        err = mt5.last_error()
        logger.warning(f"Broker does not offer candles for {symbol} (resolved: {resolved}, MT5 error: {err}). Tip: Open {resolved} chart in MT5 to force history sync.")
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

SYMBOL_ALIASES = {
    "NAS100": ["NAS100", "USTEC", "US100", "NQ100", "NDX100", "NASDAQ"],
    "US30": ["US30", "DJ30", "WS30", "USIND30", "DOW30"],
    "US500": ["US500", "SPX500", "SP500", "USA500"],
    "GER30": ["GER30", "GER40", "DAX30", "DAX40", "DE30", "DE40"],
    "UK100": ["UK100", "FTSE100", "GB100"],
    "XAUUSD": ["XAUUSD", "GOLD"],
    "XAGUSD": ["XAGUSD", "SILVER"],
}

_RESOLVED_CACHE = {}
COMMON_SUFFIXES = ["", ".m", ".pro", ".raw", "+", "c", ".a", ".ecn", ".i", "m", "_i", "-", ".s"]

def resolve_broker_symbol(symbol):
    """Resolves broker-specific symbol names (e.g. XAUUSD -> XAUUSD.m, NAS100 -> USTEC) with zero IPC lag using direct symbol_info and memory caching."""
    global _RESOLVED_CACHE
    if not symbol:
        return symbol
    
    sym_upper = symbol.strip().upper()
    if sym_upper in _RESOLVED_CACHE:
        return _RESOLVED_CACHE[sym_upper]

    try:
        # 1. Direct match on exact symbol
        info = mt5.symbol_info(symbol)
        if info is not None:
            _RESOLVED_CACHE[sym_upper] = symbol
            return symbol

        # 2. Direct match on uppercase
        if sym_upper != symbol:
            info = mt5.symbol_info(sym_upper)
            if info is not None:
                _RESOLVED_CACHE[sym_upper] = sym_upper
                return sym_upper

        # 3. Check aliases with common broker suffixes (takes < 0.005s total)
        candidates = SYMBOL_ALIASES.get(sym_upper, [sym_upper])
        for alias in candidates:
            for sfx in COMMON_SUFFIXES:
                cand = f"{alias}{sfx}"
                info = mt5.symbol_info(cand)
                if info is not None:
                    _RESOLVED_CACHE[sym_upper] = cand
                    return cand

        # 4. Fast targeted query by group prefix (never dumps all 50,000 symbols)
        prefix = sym_upper[:3]
        group_syms = mt5.symbols_get(group=f"*{prefix}*")
        if group_syms:
            for s in group_syms:
                if s.trade_mode != mt5.SYMBOL_TRADE_MODE_DISABLED:
                    if sym_upper in s.name.upper() or s.name.upper().startswith(sym_upper) or any(a in s.name.upper() for a in candidates):
                        _RESOLVED_CACHE[sym_upper] = s.name
                        return s.name
    except Exception as e:
        logger.debug(f"Symbol resolution exception for {symbol}: {e}")

    _RESOLVED_CACHE[sym_upper] = symbol
    return symbol
