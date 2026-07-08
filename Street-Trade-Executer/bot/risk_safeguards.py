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

_last_metrics_update_time = 0

def invalidate_trades_cache():
    global _cached_trades_count
    _cached_trades_count = None

def increment_trades_count():
    global _cached_trades_count
    if _cached_trades_count is not None:
        _cached_trades_count += 1

def get_or_create_daily_start_equity(current_equity):
    """
    Retrieves the starting equity for the current day from the database.
    If it doesn't exist, initializes it with the current equity.
    Uses caching to minimize database connections.
    """
    global _cached_start_equity, _cached_start_equity_date
    today = datetime.date.today()
    
    if _cached_start_equity is not None and _cached_start_equity_date == today:
        return _cached_start_equity
        
    conn = None
    start_equity = current_equity
    
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # Check if we already have a record for today
        cur.execute("SELECT start_equity FROM daily_metrics WHERE trading_date = %s", (today,))
        row = cur.fetchone()
        
        if row:
            start_equity = float(row[0])
            logger.info(f"Retrieved daily starting equity from database: ${start_equity:.2f}")
        else:
            # Create a new record for today
            cur.execute(
                """
                INSERT INTO daily_metrics (trading_date, start_equity, current_equity, max_drawdown_percent, trades_today)
                VALUES (%s, %s, %s, 0.0, 0)
                """,
                (today, current_equity, current_equity)
            )
            conn.commit()
            logger.info(f"Initialized new daily trading session. Starting equity: ${start_equity:.2f}")
            
        cur.close()
        _cached_start_equity = start_equity
        _cached_start_equity_date = today
    except Exception as e:
        logger.error(f"Error in get_or_create_daily_start_equity: {e}")
    finally:
        if conn:
            conn.close()
            
    return start_equity

def check_drawdown_limit(acc_info):
    """
    Checks if the daily drawdown limit has been breached.
    Returns: (is_breached, daily_loss_percent)
    """
    global _last_metrics_update_time
    current_equity = acc_info.equity
    start_equity = get_or_create_daily_start_equity(current_equity)
    
    daily_loss = start_equity - current_equity
    daily_loss_percent = (daily_loss / start_equity) * 100.0 if start_equity > 0 else 0.0
    
    today = datetime.date.today()
    trades_today = get_trades_count_today()
    
    # Throttle metrics database writes to once every 30 seconds
    now = time.time()
    if now - _last_metrics_update_time >= 30.0:
        try:
            update_daily_metrics(today, start_equity, current_equity, max(0.0, daily_loss_percent), trades_today)
            _last_metrics_update_time = now
        except Exception as e:
            logger.error(f"Error updating daily metrics: {e}")
    
    if daily_loss_percent >= MAX_DAILY_LOSS_PERCENT:
        logger.critical(f"DAILY LIMIT BREACHED: Drawdown is {daily_loss_percent:.2f}% (Limit: {MAX_DAILY_LOSS_PERCENT}%)")
        return True, daily_loss_percent
        
    return False, daily_loss_percent

def get_trades_count_today():
    """Returns the number of trades taken today with caching."""
    global _cached_trades_count, _cached_trades_count_date
    today = datetime.date.today()
    
    if _cached_trades_count is not None and _cached_trades_count_date == today:
        return _cached_trades_count
        
    conn = None
    count = 0
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM trades WHERE CAST(entry_time AS DATE) = %s", (today,))
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

def is_spread_valid(symbol):
    """Returns True if the current market spread is below the threshold."""
    tick = mt5.symbol_info_tick(symbol)
    info = mt5.symbol_info(symbol)
    if tick is None or info is None:
        return False
        
    spread = tick.ask - tick.bid
    digits = info.digits
    
    # Calculate spread in pips
    pip_size = 0.01 if (digits == 3 or digits == 2) else 0.0001
    spread_pips = spread / pip_size
    
    if spread_pips > MAX_SPREAD_PIPS:
        logger.warning(f"Spread for {symbol} is too wide: {spread_pips:.1f} pips (Max: {MAX_SPREAD_PIPS} pips)")
        return False
        
    return True
