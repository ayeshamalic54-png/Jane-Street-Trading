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
            
            # Smart Reset: If no trades have been taken today, and equity has changed (e.g., balance reset or account change),
            # we should update start_equity to match current_equity to prevent false limit breaches.
            trades_today = get_trades_count_today()
            if trades_today == 0 and abs(start_equity - current_equity) > 0.01:
                cur.execute(
                    "UPDATE daily_metrics SET start_equity = %s, current_equity = %s WHERE trading_date = %s",
                    (current_equity, current_equity, today)
                )
                conn.commit()
                logger.info(f"No trades taken today. Automatically updated daily start equity to match current equity: ${current_equity:.2f}")
                start_equity = current_equity
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

def check_drawdown_limit(current_equity):
    """
    Checks if the daily drawdown limit has been breached.
    Returns: (is_breached, daily_loss_percent)
    """
    global _last_metrics_update_time
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
        
    if spread_pips > max_spread:
        logger.warning(f"Spread for {symbol} is too wide: {spread_pips:.1f} pips (Max: {max_spread:.1f} pips)")
        return False
        
    return True
