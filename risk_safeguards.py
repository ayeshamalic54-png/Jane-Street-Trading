import MetaTrader5 as mt5
import datetime
import logging
import time
from database import update_daily_metrics, get_connection

logger = logging.getLogger("SMC_Forex_Bot")

# Maximum daily drawdown allowed before halting trading (e.g. 4.2% to safely stay below prop firm 5%)
MAX_DAILY_LOSS_PERCENT = 4.2
# Maximum number of trades allowed per day
MAX_DAILY_TRADES = 3
# Risk percentage per trade (e.g. 1.0% of account equity)
RISK_PERCENT = 1.0
# Maximum spread allowed in pips
MAX_SPREAD_PIPS = 2.0

_cached_start_equity = None
_cached_start_equity_date = None

_cached_trades_count = None
_cached_trades_count_date = None
_cached_last_login = None

_last_metrics_update_time = 0
_peak_drawdown_today = 0.0
_peak_drawdown_date = None

def invalidate_trades_cache():
    global _cached_trades_count
    _cached_trades_count = None

def increment_trades_count():
    global _cached_trades_count
    if _cached_trades_count is not None:
        _cached_trades_count += 1

def get_broker_today_date():
    """
    Returns today's date adjusted to the broker's MT5 server time.
    Falls back to system date if MT5 is not connected or symbol tick cannot be read.
    """
    try:
        tick = mt5.symbol_info_tick("EURUSD")
        if tick:
            # tick.time is epoch timestamp of the broker server
            broker_time = datetime.datetime.fromtimestamp(tick.time)
            return broker_time.date()
    except Exception:
        pass
    return datetime.date.today()

def get_or_create_daily_start_equity(current_equity):
    """
    Retrieves the starting equity for the current day from the database.
    If it doesn't exist, date/account ID mismatches, initializes it with the current equity.
    """
    today = get_broker_today_date()
    
    current_login = 0
    try:
        acc = mt5.account_info()
        if acc:
            current_login = int(acc.login)
    except Exception:
        pass
        
    conn = None
    start_equity = current_equity
    
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # Check if database has a different initial_balance (suggesting user manually reset it)
        cur.execute("SELECT initial_balance FROM bot_state WHERE id = 1")
        state_row = cur.fetchone()
        db_initial_balance = None
        if state_row and state_row[0] is not None:
            db_initial_balance = float(state_row[0])
            
        # Check if we already have a record for today and this specific login
        cur.execute("SELECT start_equity FROM daily_metrics WHERE trading_date = %s AND mt5_login = %s", (today, current_login))
        row = cur.fetchone()
        
        if row:
            start_equity = float(row[0])
            # If database has a different initial_balance (suggesting manual reset), sync it to start_equity
            if db_initial_balance is not None and abs(start_equity - db_initial_balance) > 0.01:
                start_equity = db_initial_balance
                cur.execute(
                    "UPDATE daily_metrics SET start_equity = %s WHERE trading_date = %s AND mt5_login = %s",
                    (db_initial_balance, today, current_login)
                )
                
            cur.execute(
                "UPDATE daily_metrics SET current_equity = %s WHERE trading_date = %s AND mt5_login = %s",
                (current_equity, today, current_login)
            )
            cur.execute(
                "UPDATE bot_state SET mt5_login = %s, equity = %s WHERE id = 1",
                (current_login, current_equity)
            )
            conn.commit()
        else:
            # Create a new record for today for this specific login
            start_equity = db_initial_balance if db_initial_balance is not None else current_equity
            cur.execute(
                """
                INSERT INTO daily_metrics (trading_date, mt5_login, start_equity, current_equity, max_drawdown_percent, trades_today)
                VALUES (%s, %s, %s, %s, 0.0, 0)
                ON CONFLICT (trading_date, mt5_login) DO UPDATE
                SET current_equity = EXCLUDED.current_equity
                """,
                (today, current_login, start_equity, current_equity)
            )
            cur.execute(
                "UPDATE bot_state SET initial_balance = %s, mt5_login = %s, equity = %s WHERE id = 1",
                (start_equity, current_login, current_equity)
            )
            conn.commit()
            logger.info(f"Initialized new daily trading session for account {current_login}. Starting equity: ${start_equity:.2f}")
            
        cur.close()
    except Exception as e:
        logger.error(f"Error in get_or_create_daily_start_equity: {e}")
    finally:
        if conn:
            conn.close()
            
    return start_equity

def check_drawdown_limit(current_equity):
    """
    Checks if the daily drawdown limit has been breached.
    Returns: (is_breached, daily_loss_percent)
    """
    global _last_metrics_update_time, _peak_drawdown_today, _peak_drawdown_date
    start_equity = get_or_create_daily_start_equity(current_equity)
    
    current_login = 0
    try:
        acc = mt5.account_info()
        if acc:
            current_login = int(acc.login)
    except Exception:
        pass
        
    daily_loss = start_equity - current_equity
    daily_loss_percent = (daily_loss / start_equity) * 100.0 if start_equity > 0 else 0.0
    
    today = get_broker_today_date()
    
    # Reset peak drawdown on new day
    if _peak_drawdown_date != today:
        _peak_drawdown_today = 0.0
        _peak_drawdown_date = today
        
    _peak_drawdown_today = max(_peak_drawdown_today, daily_loss_percent)
    
    trades_today = get_trades_count_today()
    
    # Throttle metrics database writes to once every 30 seconds
    now = time.time()
    if now - _last_metrics_update_time >= 30.0:
        try:
            update_daily_metrics(today, start_equity, current_equity, max(0.0, _peak_drawdown_today), trades_today, login_id=current_login)
            _last_metrics_update_time = now
        except Exception as e:
            logger.error(f"Error updating daily metrics: {e}")
    
    if _peak_drawdown_today >= MAX_DAILY_LOSS_PERCENT:
        logger.info(f"Daily drawdown limit reached: {_peak_drawdown_today:.2f}% (Limit: {MAX_DAILY_LOSS_PERCENT}%)")
        return True, _peak_drawdown_today
        
    return False, max(0.0, _peak_drawdown_today)

def get_trades_count_today():
    """Returns the number of trades taken today with caching."""
    global _cached_trades_count, _cached_trades_count_date
    today = get_broker_today_date()
    
    if _cached_trades_count is not None and _cached_trades_count_date == today:
        return _cached_trades_count
        
    conn = None
    count = 0
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM trades WHERE CAST(entry_time AS DATE) = %s AND (comment LIKE '%%TP1%%' OR comment LIKE '%%Manual%%' OR comment LIKE '%%MANUAL%%')",
            (today,)
        )
        count = cur.fetchone()[0]
        cur.close()
        
        _cached_trades_count = count
        _cached_trades_count_date = today
    except Exception as e:
        logger.error(f"Error fetching trades count: {e}")
    finally:
        if conn:
            conn.close()
    return count

def round_volume(symbol, volume):
    """Rounds trade volume to broker volume step and limits to min/max sizes."""
    info = mt5.symbol_info(symbol)
    if info is None:
        return round(volume, 2)
    step = info.volume_step
    min_vol = info.volume_min
    max_vol = info.volume_max
    
    # Round to volume step
    rounded = round(round(volume / step) * step, 8)
    if rounded < min_vol:
        rounded = min_vol
    elif rounded > max_vol:
        rounded = max_vol
    return round(rounded, 2)

def calculate_lots(symbol, sl_distance_price, acc_info):
    """
    Calculates lot size based on a fixed risk percentage of account equity.
    sl_distance_price: Absolute price difference between entry and stop loss
    """
    info = mt5.symbol_info(symbol)
    if info is None or sl_distance_price <= 0:
        return 0.01
        
    tick_size = info.trade_tick_size
    tick_value = info.trade_tick_value  # Value of 1 tick in account currency (e.g. USD)
    equity = acc_info.equity
    
    risk_amount = equity * (RISK_PERCENT / 100.0)
    
    # Formula: Lots = Risk Amount / (SL distance * (Tick Value / Tick Size))
    lots = risk_amount / (sl_distance_price * (tick_value / tick_size))
    
    return round_volume(symbol, lots)

def get_pip_size(symbol: str) -> float:
    s = symbol.upper()
    if "JPY" in s:
        return 0.01
    if "XAU" in s:
        return 1.0
    if "XAG" in s:
        return 0.1
    if "BTC" in s:
        return 1.0
    if "ETH" in s:
        return 0.1
    if any(x in s for x in ["SOL", "BNB", "AVAX"]):
        return 0.01
    if any(x in s for x in ["XRP", "ADA", "DOGE", "MATIC"]):
        return 0.0001
    # Handle Indices & Stocks
    if any(x in s for x in ["US500", "US30", "NAS100", "GER30", "UK100", "SPX", "DJI", "NDX"]):
        return 1.0
    if any(x in s for x in ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMD", "META", "AMZN"]):
        return 0.1
    return 0.0001

def is_spread_valid(symbol):
    """Returns True if the current market spread is below the threshold."""
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return False
        
    spread = tick.ask - tick.bid
    
    # Calculate spread in pips
    pip_size = get_pip_size(symbol)
    spread_pips = spread / pip_size
    
    # Dynamic spread threshold based on asset class
    max_spread = MAX_SPREAD_PIPS
    s = symbol.upper()
    if any(x in s for x in ["BTC", "ETH", "SOL", "BNB", "AVAX", "XRP", "ADA", "DOGE", "MATIC"]):
        # For crypto, use 0.1% of current price as the threshold in pips
        price = (tick.bid + tick.ask) / 2.0
        max_spread = (price * 0.001) / pip_size
    elif "XAU" in s:
        max_spread = 5.0
    elif "XAG" in s:
        max_spread = 10.0
    elif any(x in s for x in ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMD", "META", "AMZN"]):
        max_spread = 10.0
    elif any(x in s for x in ["US500", "US30", "NAS100", "GER30", "UK100", "SPX", "DJI", "NDX", "USTEC"]):
        max_spread = 15.0
        
    if spread_pips > max_spread:
        logger.warning(f"Spread for {symbol} is too wide: {spread_pips:.1f} pips (Max: {max_spread:.1f} pips)")
        return False
        
    return True
