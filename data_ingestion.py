import MetaTrader5 as mt5
import pandas as pd
import logging
import sys
import os
import re
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

def check_and_subscribe_symbol(symbol, expected_symbol=None):
    """Ensures that the symbol is valid, offered by the broker, visible in Market Watch, and subscribed."""
    global _SUBSCRIBED_SYMBOLS
    canonical = (expected_symbol or symbol or "").strip()
    cache_key = (canonical.upper(), (symbol or "").strip().upper())
    if cache_key in _SUBSCRIBED_SYMBOLS:
        return True

    resolved = resolve_broker_symbol(canonical or symbol)
    target_sym = resolved
    info_r = mt5.symbol_info(target_sym)
    if info_r is None and target_sym != symbol:
        info_r = mt5.symbol_info(symbol)
        if info_r is not None:
            target_sym = symbol

    if info_r is None or not _is_valid_broker_symbol(canonical or symbol, info_r, target_sym):
        logger.info(f"Symbol {canonical or symbol} (resolved={target_sym}) is not a valid offered instrument on this broker account. Skipping scan.")
        return False

    if getattr(info_r, "trade_mode", 4) == getattr(mt5, "SYMBOL_TRADE_MODE_DISABLED", 0):
        logger.info(f"Symbol {target_sym} is trade-disabled (trade_mode=0) on this broker account. Skipping scan.")
        return False

    selected = mt5.symbol_select(target_sym, True)
    if not selected and target_sym != symbol:
        selected = mt5.symbol_select(symbol, True)
        if selected:
            target_sym = symbol

    if not selected:
        logger.info(f"Symbol {canonical or symbol} (or broker alias) is not offered by your broker account. Skipping scan for this symbol.")
        return False

    # Re-verify minimum price sanity after Market Watch selection guarantees live tick/rates access
    if not _passes_price_sanity(canonical or symbol, info_r, target_sym):
        _RESOLVED_CACHE.pop(canonical.upper(), None)
        _RESOLVED_CACHE.pop((target_sym or "").upper(), None)
        return False

    # Subscribe to L2 depth of market book
    book_sub = mt5.market_book_add(target_sym)
    _SUBSCRIBED_SYMBOLS.add(cache_key)
    _SUBSCRIBED_SYMBOLS.add((target_sym.upper(), target_sym.upper()))
    if book_sub:
        logger.info(f"Subscribed to Order Book updates for {target_sym}")
    else:
        logger.info(f"Market Watch active for {target_sym} (Level-1 Bid/Ask ticks active; L2 DOM depth not required).")

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

    # Fast targeted fallback without dumping full symbol database (only validated aliases)
    if rates is None or len(rates) == 0:
        try:
            sym_upper = symbol.strip().upper()
            alias_terms = SYMBOL_ALIASES.get(sym_upper, [sym_upper])
            for term in alias_terms:
                group_syms = mt5.symbols_get(group=f"*{term}*")
                if not group_syms:
                    continue
                for s_info in group_syms:
                    if getattr(s_info, "trade_mode", 4) == getattr(mt5, "SYMBOL_TRADE_MODE_DISABLED", 0):
                        continue
                    s_name = s_info.name
                    if not _is_valid_broker_symbol(sym_upper, s_info, s_name):
                        continue
                    mt5.symbol_select(s_name, True)
                    r_try = mt5.copy_rates_from_pos(s_name, timeframe, 0, count)
                    if r_try is not None and len(r_try) > 0 and _passes_price_sanity(sym_upper, s_info, s_name, rates_sample=r_try):
                        rates = r_try
                        logger.info(f"Resolved alternative tradeable symbol {s_name} for {symbol} candles.")
                        _RESOLVED_CACHE[sym_upper] = s_name
                        break
                if rates is not None and len(rates) > 0:
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
    "NAS100": ["NAS100", "USTEC", "US100", "NQ100", "NDX100", "NASDAQ", "USA100", "TECH100", "NDX"],
    "US30": ["US30", "DJ30", "WS30", "USIND30", "DOW30", "USA30", "WALLST30", "DJI"],
    "US500": ["US500", "SPX500", "SP500", "USA500"],
    "GER30": ["GER30", "GER40", "DAX30", "DAX40", "DE30", "DE40"],
    "UK100": ["UK100", "FTSE100", "GB100"],
    "XAUUSD": ["XAUUSD", "GOLD"],
    "XAGUSD": ["XAGUSD", "SILVER"],
}

_MIN_ASSET_PRICES = {
    "US30": 15000.0,
    "NAS100": 8000.0,
    "US500": 2500.0,
    "GER30": 8000.0,
    "UK100": 4000.0,
    "XAUUSD": 1000.0,
    "XAGUSD": 10.0,
}

_NON_CFD_PATH_KEYWORDS = (
    "stock", "equit", "etf", "bond", "treasury", "share", "fund", "crypto", "coin"
)

_RESOLVED_CACHE = {}
COMMON_SUFFIXES = ["", ".m", ".pro", ".raw", ".cash", "+", "c", ".a", ".ecn", ".i", "m", "_i", "-", ".s"]

def _extract_canonical_tokens(cand_sym: str):
    """Extracts normalized token variants for strict boundary-safe broker alias matching."""
    raw = (cand_sym or "").strip()
    if not raw:
        return set()
    # Strip leading broker markers (#, ., $, [)
    clean_raw = re.sub(r'^[^A-Za-z0-9]+', '', raw)
    # Split on separator punctuation to isolate core symbol (e.g. "US30.cash" -> "US30", "USTEC_i" -> "USTEC")
    head_raw = re.split(r'[._\-\+\s\[\]]+', clean_raw)[0] if clean_raw else ""
    head_u = head_raw.upper()
    tokens = set()
    if head_u:
        tokens.add(head_u)
    # Allow lowercase single-letter micro/ecn broker suffixes like US30m, XAUUSDc, NAS100r
    if len(head_raw) > 3 and head_raw[-1] in ("m", "c", "r", "i", "e", "p", "f", "s"):
        tokens.add(head_raw[:-1].upper())
    # Allow explicit two/three-letter known suffixes glued without dot (e.g., US30PRO, USTECRAW)
    for glued in ("PRO", "RAW", "ECN", "CASH", "STD", "MICRO", "MINI", "CFD"):
        if head_u.endswith(glued) and len(head_u) > len(glued) + 2:
            tokens.add(head_u[:-len(glued)])
    return tokens

def _is_valid_broker_symbol(requested_sym: str, info_obj, cand_sym: str) -> bool:
    """
    Validates that a candidate MT5 symbol matches the requested canonical instrument without
    false substring/ETF/stock matches (e.g. rejects BNDX bond ETF for NAS100/NDX or $22 stock for US30).
    """
    if not cand_sym:
        return False
    sym_upper = (requested_sym or "").strip().upper()
    candidates = set(SYMBOL_ALIASES.get(sym_upper, [sym_upper]))
    cand_tokens = _extract_canonical_tokens(cand_sym)
    if not (cand_tokens & candidates):
        return False

    if info_obj is not None and sym_upper in _MIN_ASSET_PRICES:
        sym_path = (getattr(info_obj, "path", "") or "").lower()
        if sym_path and any(kw in sym_path for kw in _NON_CFD_PATH_KEYWORDS):
            logger.warning(f"🛑 [SYMBOL GUARD] Rejected non-CFD symbol {cand_sym} (path='{sym_path}') for {sym_upper}")
            return False

    return True

def _passes_price_sanity(requested_sym: str, info_obj, cand_sym: str, rates_sample=None) -> bool:
    """Rejects candidate symbols whose live tick / M5 bar price falls below index/metal sanity bounds."""
    sym_upper = (requested_sym or "").strip().upper()
    min_price = _MIN_ASSET_PRICES.get(sym_upper, 0.0)
    if min_price <= 0.0:
        return True

    price_chk = 0.0
    try:
        tick = mt5.symbol_info_tick(cand_sym)
        if tick is not None:
            price_chk = float(getattr(tick, "bid", 0.0) or getattr(tick, "last", 0.0) or getattr(tick, "ask", 0.0) or 0.0)
    except Exception:
        tick = None

    if price_chk <= 0.0 and info_obj is not None:
        try:
            price_chk = float(getattr(info_obj, "bid", 0.0) or getattr(info_obj, "last", 0.0) or 0.0)
        except Exception:
            price_chk = 0.0

    if price_chk <= 0.0 and rates_sample is not None and len(rates_sample) > 0:
        try:
            last_bar = rates_sample[-1]
            price_chk = float(last_bar["close"] if isinstance(last_bar, dict) or hasattr(last_bar, "dtype") else getattr(last_bar, "close", 0.0))
        except Exception:
            price_chk = 0.0

    if price_chk <= 0.0 and hasattr(mt5, "copy_rates_from_pos"):
        try:
            r1 = mt5.copy_rates_from_pos(cand_sym, mt5.TIMEFRAME_M5, 0, 1)
            if r1 is not None and len(r1) > 0:
                last_bar = r1[-1]
                price_chk = float(last_bar["close"] if isinstance(last_bar, dict) or hasattr(last_bar, "dtype") else getattr(last_bar, "close", 0.0))
        except Exception:
            pass

    if price_chk > 0.0 and price_chk < min_price:
        logger.warning(f"🛑 [SYMBOL SANITY REJECT] {cand_sym} price {price_chk:.2f} < min {min_price:.2f} for {sym_upper}; refusing stock/ETF mis-mapping.")
        return False

    return True

def resolve_broker_symbol(symbol):
    """Resolves broker-specific symbol names (e.g. XAUUSD -> XAUUSD.m, NAS100 -> USTEC) with strict boundary + price sanity checks."""
    global _RESOLVED_CACHE
    if not symbol:
        return symbol
    
    sym_upper = symbol.strip().upper()
    if sym_upper in _RESOLVED_CACHE:
        cached = _RESOLVED_CACHE[sym_upper]
        info_cached = mt5.symbol_info(cached)
        if info_cached is not None and _is_valid_broker_symbol(sym_upper, info_cached, cached) and _passes_price_sanity(sym_upper, info_cached, cached):
            return cached
        _RESOLVED_CACHE.pop(sym_upper, None)

    disabled_fallback = None
    try:
        def _is_tradeable(cand_sym):
            info_c = mt5.symbol_info(cand_sym)
            if info_c is None:
                return False, False
            if not _is_valid_broker_symbol(sym_upper, info_c, cand_sym):
                return False, False
            if getattr(info_c, "trade_mode", 4) == getattr(mt5, "SYMBOL_TRADE_MODE_DISABLED", 0):
                return True, False
            if sym_upper in _MIN_ASSET_PRICES and hasattr(mt5, "symbol_select"):
                try:
                    mt5.symbol_select(cand_sym, True)
                except Exception:
                    pass
            if not _passes_price_sanity(sym_upper, info_c, cand_sym):
                return False, False
            return True, True

        # 1. Direct match on exact symbol (only cache immediately if tradeable)
        exists_s, ok_s = _is_tradeable(symbol)
        if exists_s:
            if ok_s:
                _RESOLVED_CACHE[sym_upper] = symbol
                return symbol
            disabled_fallback = disabled_fallback or symbol

        # 2. Direct match on uppercase
        if sym_upper != symbol:
            exists_u, ok_u = _is_tradeable(sym_upper)
            if exists_u:
                if ok_u:
                    _RESOLVED_CACHE[sym_upper] = sym_upper
                    return sym_upper
                disabled_fallback = disabled_fallback or sym_upper

        # 3. Check aliases with common broker suffixes (takes < 0.005s total)
        candidates = SYMBOL_ALIASES.get(sym_upper, [sym_upper])
        for alias in candidates:
            for sfx in COMMON_SUFFIXES:
                cand = f"{alias}{sfx}"
                exists_c, ok_c = _is_tradeable(cand)
                if exists_c:
                    if ok_c:
                        _RESOLVED_CACHE[sym_upper] = cand
                        return cand
                    disabled_fallback = disabled_fallback or cand

        # 4. Targeted group search across explicit aliases ONLY (strict boundary match prevents BNDX / stock matches)
        for term in candidates:
            group_syms = mt5.symbols_get(group=f"*{term}*")
            if not group_syms:
                continue
            for s in group_syms:
                if getattr(s, "trade_mode", 4) != getattr(mt5, "SYMBOL_TRADE_MODE_DISABLED", 0):
                    if not _is_valid_broker_symbol(sym_upper, s, s.name):
                        continue
                    try:
                        if hasattr(mt5, "symbol_select"):
                            mt5.symbol_select(s.name, True)
                    except Exception:
                        pass
                    if not _passes_price_sanity(sym_upper, s, s.name):
                        continue
                    _RESOLVED_CACHE[sym_upper] = s.name
                    return s.name
    except Exception as e:
        logger.debug(f"Symbol resolution exception for {symbol}: {e}")

    return disabled_fallback or symbol
