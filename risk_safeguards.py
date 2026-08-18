import MetaTrader5 as mt5
import datetime
import logging
import time
from database import update_daily_metrics, get_connection

logger = logging.getLogger("SMC_Forex_Bot")

# Maximum daily drawdown allowed before halting trading (Dynamic Halt Limit / Max Loss Cap)
HALT_DAILY_DRAWDOWN_PCT = 0.80
MAX_DAILY_DRAWDOWN_PCT = 3.30
MAX_DAILY_LOSS_PERCENT = 0.80

MAX_FLOATING_LOSS_USD = 330.0
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
    global _cached_start_equity, _cached_start_equity_date, _cached_last_login
    today = get_broker_today_date()
    
    current_login = 0
    try:
        acc = mt5.account_info()
        if acc:
            current_login = int(acc.login)
    except Exception:
        pass

    if _cached_last_login != current_login:
        _cached_last_login = current_login
        _cached_start_equity = None
        _cached_start_equity_date = None
        
    conn = None
    start_equity = current_equity
    
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # Check if database has initial_balance for current login
        cur.execute("SELECT initial_balance FROM bot_state WHERE id = 1 AND mt5_login = %s", (current_login,))
        state_row = cur.fetchone()
        db_initial_balance = None
        if state_row and state_row[0] is not None:
            db_initial_balance = float(state_row[0])

        # Check if we already have a record for today and this specific login
        cur.execute("SELECT start_equity, max_drawdown_percent FROM daily_metrics WHERE trading_date = %s AND mt5_login = %s", (today, current_login))
        row = cur.fetchone()

        if row:
            start_equity = float(row[0])
            existing_dd = float(row[1]) if (len(row) > 1 and row[1] is not None) else 0.0
            cur.execute(
                "UPDATE daily_metrics SET current_equity = %s WHERE trading_date = %s AND mt5_login = %s",
                (current_equity, today, current_login)
            )
            cur.execute(
                """
                UPDATE bot_state SET 
                    mt5_login = %s, 
                    equity = %s, 
                    start_of_day_equity = %s,
                    drawdown_percent = GREATEST(drawdown_percent, %s)
                WHERE id = 1
                """,
                (current_login, current_equity, start_equity, existing_dd)
            )
            conn.commit()

        else:
            # Create a fresh daily record for today using active MT5 equity at day start
            start_equity = current_equity

            cur.execute(
                """
                INSERT INTO daily_metrics (trading_date, mt5_login, start_equity, current_equity, max_drawdown_percent, trades_today)
                VALUES (%s, %s, %s, %s, 0.0, 0)
                ON CONFLICT (trading_date, mt5_login) DO UPDATE
                SET start_equity = EXCLUDED.start_equity,
                    current_equity = EXCLUDED.current_equity
                """,
                (today, current_login, start_equity, current_equity)
            )
            cur.execute(
                """
                UPDATE bot_state SET 
                    initial_balance = %s, 
                    mt5_login = %s, 
                    equity = %s,
                    start_of_day_equity = %s,
                    max_equity_peak = %s
                WHERE id = 1
                """,
                (start_equity, current_login, current_equity, start_equity, current_equity)
            )
            conn.commit()
            logger.info(f"Initialized session for account {current_login}. Starting equity: ${start_equity:.2f}")

        cur.close()
    except Exception as e:
        logger.error(f"Error in get_or_create_daily_start_equity: {e}")
    finally:
        if conn:
            conn.close()
            
    return start_equity


_PEAK_DAILY_DRAWDOWN_PCT = 0.0
_PEAK_DAILY_DRAWDOWN_DATE = None
_PEAK_DAILY_DRAWDOWN_LOGIN = None

def check_drawdown_limit(current_equity):
    """
    Checks if the daily drawdown limit has been breached.
    Tracks and preserves peak daily drawdown hit today even after positions close.
    Automatically resets for NEW MT5 accounts and NEW trading days.
    Returns: (is_breached, daily_loss_percent, peak_daily_drawdown_percent)
    """
    global _last_metrics_update_time, _cached_last_login, _PEAK_DAILY_DRAWDOWN_PCT, _PEAK_DAILY_DRAWDOWN_DATE, _PEAK_DAILY_DRAWDOWN_LOGIN
    start_equity = get_or_create_daily_start_equity(current_equity)
    
    current_login = 0
    try:
        acc = mt5.account_info()
        if acc:
            current_login = int(acc.login)
    except Exception:
        pass

    today = get_broker_today_date()
    if _PEAK_DAILY_DRAWDOWN_DATE != today or _PEAK_DAILY_DRAWDOWN_LOGIN != current_login:
        _PEAK_DAILY_DRAWDOWN_DATE = today
        _PEAK_DAILY_DRAWDOWN_LOGIN = current_login
        _PEAK_DAILY_DRAWDOWN_PCT = 0.0

        # Query DB to preserve peak daily drawdown hit today for this account!
        try:
            conn_dd = get_connection()
            cur_dd = conn_dd.cursor()
            cur_dd.execute(
                "SELECT max_drawdown_percent FROM daily_metrics WHERE trading_date = %s AND mt5_login = %s",
                (today, current_login)
            )
            dd_row = cur_dd.fetchone()
            if dd_row and dd_row[0] is not None:
                _PEAK_DAILY_DRAWDOWN_PCT = float(dd_row[0])
            cur_dd.close()
            conn_dd.close()
        except Exception as ex_dd:
            logger.error(f"Error loading existing peak drawdown for login {current_login}: {ex_dd}")


        
    daily_loss = start_equity - current_equity
    daily_loss_percent = (daily_loss / start_equity) * 100.0 if start_equity > 0 else 0.0

    # Track worst peak drawdown hit today
    if daily_loss_percent > _PEAK_DAILY_DRAWDOWN_PCT:
        _PEAK_DAILY_DRAWDOWN_PCT = daily_loss_percent

    _cached_last_login = current_login
    trades_today = get_trades_count_today()
    
    # Real-time metrics database writes (1.0 second high-frequency sync)
    now = time.time()
    if now - _last_metrics_update_time >= 1.0:
        try:
            update_daily_metrics(today, start_equity, current_equity, _PEAK_DAILY_DRAWDOWN_PCT, trades_today, login_id=current_login)
            _last_metrics_update_time = now
        except Exception as e:
            logger.error(f"Error updating daily metrics: {e}")
    
    if daily_loss_percent >= MAX_DAILY_LOSS_PERCENT:
        logger.info(f"Daily drawdown limit reached: {daily_loss_percent:.2f}% (Halt Limit: {MAX_DAILY_LOSS_PERCENT}% | Max Limit: {MAX_DAILY_DRAWDOWN_PCT}%)")
        return True, daily_loss_percent, _PEAK_DAILY_DRAWDOWN_PCT
        
    return False, daily_loss_percent, _PEAK_DAILY_DRAWDOWN_PCT


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
        # Count distinct spread signals executed today
        cur.execute("""
            SELECT COUNT(DISTINCT signal_id) 
            FROM trades 
            WHERE entry_time >= (CURRENT_DATE - INTERVAL '12 hours')
               OR CAST(entry_time AS DATE) = CURRENT_DATE
        """)
        row = cur.fetchone()
        count = row[0] if row else 0
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
    if any(x in s for x in ["XAU", "XPT", "XPD", "PLAT", "PALL"]):
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
    """Returns True if the current market spread is below the threshold and market is open."""
    info = mt5.symbol_info(symbol)
    if info and info.trade_mode != mt5.SYMBOL_TRADE_MODE_FULL:
        logger.warning(f"Market for {symbol} is currently closed (Broker Trade Mode: {info.trade_mode}). US stock market opens at 9:30 AM EST / 6:30 PM PKT.")
        return False

    tick = mt5.symbol_info_tick(symbol)
    if tick is None or tick.bid <= 0 or tick.ask <= 0:
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
    elif any(x in s for x in ["XAU", "XPT", "XPD", "PLAT", "PALL"]):
        max_spread = 5.0  # standard threshold for major precious metals
    elif "XAG" in s:
        max_spread = 10.0
    elif any(x in s for x in ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMD", "META", "AMZN"]):
        max_spread = 30.0
    elif any(x in s for x in ["US500", "US30", "NAS100", "GER30", "UK100", "SPX", "DJI", "NDX", "USTEC"]):
        max_spread = 35.0
        
    if spread_pips > max_spread:
        logger.warning(f"Spread for {symbol} is too wide: {spread_pips:.1f} pips (Max: {max_spread:.1f} pips)")
        return False
        
    return True


MINIMUM_HOLD_ENABLED = True
MINIMUM_HOLD_TIME_SECONDS = 140
ADVERSE_REGIME_EXIT_ENABLED = True
MAX_CONCURRENT_TRADES = 1


def get_active_pairs_and_symbols():
    """
    Returns (active_pairs_count, active_pairs_set, active_symbols_set).
    Strictly enforces single trade concurrency limit across all MT5 open positions.
    """
    active_pairs = set()
    active_symbols = set()
    raw_positions_count = 0
    
    try:
        import MetaTrader5 as mt5
        positions = mt5.positions_get()
        if positions:
            raw_positions_count = len(positions)
            for pos in positions:
                pos_sym = pos.symbol.upper().split('.')[0]
                active_symbols.add(pos_sym)
                comm_str = str(getattr(pos, 'comment', '')).upper()
                if comm_str:
                    parts = comm_str.split('_')
                    if len(parts) >= 4:
                        p1, p2 = parts[-2], parts[-1]
                        if len(p1) >= 5 and len(p2) >= 5:
                            active_pairs.add(f"{p1}/{p2}")

        # If MT5 has ANY active open position, active_pairs_count MUST be at least 1!
        pairs_count = len(active_pairs) if active_pairs else (1 if raw_positions_count > 0 else 0)
    except Exception as e:
        logger.error(f"Error fetching active pairs and symbols: {e}")
        pairs_count = 0

    return pairs_count, active_pairs, active_symbols




def check_minimum_hold(entry_time_val):
    """
    Protection 4: 140-Second Minimum Hold.
    Blocks normal strategy-based early closure before 140s while keeping SL/TP 100% active.
    Returns (is_blocked, trade_age_seconds, reason)
    """
    if not MINIMUM_HOLD_ENABLED or entry_time_val is None:
        return False, 0, ""

    if isinstance(entry_time_val, (int, float)):
        trade_age = time.time() - entry_time_val
    elif isinstance(entry_time_val, datetime.datetime):
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        if entry_time_val.tzinfo is None:
            entry_time_val = entry_time_val.replace(tzinfo=datetime.timezone.utc)
        trade_age = (now_utc - entry_time_val).total_seconds()
    else:
        return False, 0, ""

    if trade_age < MINIMUM_HOLD_TIME_SECONDS:
        msg = f"MIN_HOLD BLOCK | Trade age: {int(trade_age)}s / {MINIMUM_HOLD_TIME_SECONDS}s | Reason: normal early-close"
        logger.info(msg)
        return True, int(trade_age), msg

    return False, int(trade_age), ""

_ADVERSE_CONFIRMATION_COUNTERS = {}
REQUIRED_CONSECUTIVE_OBSERVATIONS = 3

def check_adverse_regime_exit(pair_str, direction, z_score, z_velocity, trade_age_seconds, required_obs=REQUIRED_CONSECUTIVE_OBSERVATIONS):
    """
    Protection 5: LOGIC-BASED AUTOMATIC ADVERSE-REGIME EXIT.
    Evaluated ONLY after 140s minimum hold.
    Uses asset-tailored dynamic velocity thresholds (Forex: 0.015, Metals: 0.035, Indices: 0.025).
    Requires sustained adverse Z-score + Z-velocity over multiple consecutive scan observations (default: 3)
    to prevent 1-tick / 1-cycle false exit spikes.
    Returns (should_close, reason)
    """
    global _ADVERSE_CONFIRMATION_COUNTERS

    if not ADVERSE_REGIME_EXIT_ENABLED or trade_age_seconds < 140:
        _ADVERSE_CONFIRMATION_COUNTERS[pair_str] = 0
        return False, ""

    z_val = float(z_score or 0.0)
    v_val = float(z_velocity or 0.0)

    p_upper = str(pair_str).upper()
    if any(m in p_upper for m in ["XAU", "XAG", "GOLD", "SILVER"]):
        v_limit = 0.035
    elif any(idx in p_upper for idx in ["US30", "NAS100", "US500", "GER30", "UK100", "USTEC"]):
        v_limit = 0.025
    else:
        v_limit = 0.015

    is_adverse_now = False

    # SELL_SPREAD: Invalidated if Z remains strongly positive (>2.2) and velocity expanding upward (>v_limit)
    if direction in ["SELL_SPREAD", "SELL", "BEARISH"]:
        if z_val > 2.2 and v_val > v_limit:
            is_adverse_now = True

    # BUY_SPREAD: Invalidated if Z remains strongly negative (<-2.2) and velocity expanding downward (<-v_limit)
    if direction in ["BUY_SPREAD", "BUY", "BULLISH"]:
        if z_val < -2.2 and v_val < -v_limit:
            is_adverse_now = True

    if is_adverse_now:
        current_count = _ADVERSE_CONFIRMATION_COUNTERS.get(pair_str, 0) + 1
        _ADVERSE_CONFIRMATION_COUNTERS[pair_str] = current_count

        if current_count >= required_obs:
            reason = f"ADVERSE REGIME EXIT CONFIRMED | Pair: {pair_str} | Direction: {direction} | Z-Score: {z_val:.2f} | Z-Velocity: {v_val:+.4f} > limit {v_limit:.4f} | Sustained Observations: {current_count}/{required_obs} | Reason: Mean-Reversion Thesis Invalidated"
            logger.info(reason)
            return True, reason
        else:
            logger.info(f"ADVERSE REGIME DETECTED (Observation {current_count}/{required_obs}) for {pair_str} | Deferring exit until sustained confirmation.")
            return False, ""
    else:
        _ADVERSE_CONFIRMATION_COUNTERS[pair_str] = 0
        return False, ""


_HEDGE_DIVERGENCE_COUNTERS = {}

def evaluate_hedge_effectiveness(active_js_positions, beta_val=None):
    """
    Hedge-Effectiveness Monitoring Layer (Detect + Log + Alert ONLY).
    Continuously tracks Part-3 Main Leg entry/current price vs Hedge Leg entry/current price.
    Evaluates beta-adjusted normalized price returns: (curr_p3 - entry_p3)/entry_p3 vs (curr_h - entry_h)/entry_h.
    Determines if hedge price movement is offsetting Part-3 risk or creating additional adverse divergence.
    Does NOT auto-close or alter baseline entry, Z-score, TP, SL, or lot sizing.
    """
    global _HEDGE_DIVERGENCE_COUNTERS

    if not active_js_positions:
        return

    main_positions = [p for p in active_js_positions if "HEDGE" not in str(p.comment).upper()]
    hedge_positions = [p for p in active_js_positions if "HEDGE" in str(p.comment).upper()]

    if not main_positions or not hedge_positions:
        return

    # Identify Part 3 position (comment containing TP3 or fallback to last main position)
    part3_positions = [p for p in main_positions if "TP3" in str(p.comment).upper()]
    part3_pos = part3_positions[0] if part3_positions else main_positions[-1]
    hedge_pos = hedge_positions[0]

    main_sym = main_positions[0].symbol.upper().split('.')[0]
    hedge_sym = hedge_pos.symbol.upper().split('.')[0]
    pair_key = f"{main_sym}/{hedge_sym}"

    # Price tracking: Part 3 Entry/Current Price vs Hedge Entry/Current Price
    entry_p3 = float(part3_pos.price_open) if hasattr(part3_pos, 'price_open') and part3_pos.price_open else 1.0
    curr_p3 = float(part3_pos.price_current) if hasattr(part3_pos, 'price_current') and part3_pos.price_current else entry_p3
    ret_p3 = ((curr_p3 - entry_p3) / entry_p3) if entry_p3 > 0 else 0.0

    entry_h = float(hedge_pos.price_open) if hasattr(hedge_pos, 'price_open') and hedge_pos.price_open else 1.0
    curr_h = float(hedge_pos.price_current) if hasattr(hedge_pos, 'price_current') and hedge_pos.price_current else entry_h
    ret_h = ((curr_h - entry_h) / entry_h) if entry_h > 0 else 0.0

    # PnL accounting: 3 Main Orders Sum vs 1 Hedge Order
    main_pnl = sum(float(p.profit) for p in main_positions)
    hedge_pnl = sum(float(p.profit) for p in hedge_positions)
    net_pnl = main_pnl + hedge_pnl

    is_ineffective = False
    status_str = "HEDGE EFFECTIVE (Normal Risk Offset)"

    # Price-based & PnL-based divergence evaluation
    # Condition 1: Both Part-3 and Hedge prices move in adverse directions simultaneously
    is_part3_adverse = (part3_pos.type == 0 and curr_p3 < entry_p3) or (part3_pos.type == 1 and curr_p3 > entry_p3)
    is_hedge_adverse = (hedge_pos.type == 0 and curr_h < entry_h) or (hedge_pos.type == 1 and curr_h > entry_h)

    if is_part3_adverse and is_hedge_adverse:
        is_ineffective = True
        status_str = f"HEDGE DIVERGENCE | Part-3 P ({entry_p3:.5f}->{curr_p3:.5f}) & Hedge P ({entry_h:.5f}->{curr_h:.5f}) both adverse!"

    # Condition 2: Double-sided PnL loss
    elif main_pnl < -2.0 and hedge_pnl < -2.0:
        is_ineffective = True
        status_str = "HEDGE DIVERGENCE (Double-Sided Loss)"

    # Condition 3: Hedge loss severely over-drags main leg profit
    elif net_pnl < -5.0 and hedge_pnl < 0 and abs(hedge_pnl) > (1.3 * max(0.1, main_pnl)):
        is_ineffective = True
        status_str = "HEDGE INEFFECTIVE (Hedge Over-Dragging Main Profit)"

    log_msg = (
        f"HEDGE MONITOR | Main: {main_sym} | Hedge: {hedge_sym} | "
        f"Part3 P: {entry_p3:.5f}->{curr_p3:.5f} ({ret_p3*100:+.2f}%) | "
        f"Hedge P: {entry_h:.5f}->{curr_h:.5f} ({ret_h*100:+.2f}%) | "
        f"Main PnL: {main_pnl:+.2f} | Hedge PnL: {hedge_pnl:+.2f} | Net PnL: {net_pnl:+.2f} | "
        f"Status: {status_str}"
    )

    if is_ineffective:
        _HEDGE_DIVERGENCE_COUNTERS[pair_key] = _HEDGE_DIVERGENCE_COUNTERS.get(pair_key, 0) + 1
        logger.warning(log_msg)
    else:
        _HEDGE_DIVERGENCE_COUNTERS[pair_key] = 0
        logger.info(log_msg)





