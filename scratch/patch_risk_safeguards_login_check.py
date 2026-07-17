import os

risk_path = os.path.join(os.path.dirname(__file__), "..", "risk_safeguards.py")

with open(risk_path, "r", encoding="utf-8") as f:
    content = f.read()

# Add _cached_last_login definition
old_cached_defs = """_cached_trades_count = None
_cached_trades_count_date = None"""

new_cached_defs = """_cached_trades_count = None
_cached_trades_count_date = None
_cached_last_login = None"""

if old_cached_defs in content:
    content = content.replace(old_cached_defs, new_cached_defs)
    print("Added _cached_last_login definition.")
else:
    print("old_cached_defs target not found in risk_safeguards.py!")

# Update get_or_create_daily_start_equity function
old_get_func = """def get_or_create_daily_start_equity(current_equity):
    \"\"\"
    Retrieves the starting equity for the current day from the database.
    If it doesn't exist, initializes it with the current equity.
    Uses caching to minimize database connections.
    \"\"\"
    global _cached_start_equity, _cached_start_equity_date
    today = get_broker_today_date()
    
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
                \"\"\"
                INSERT INTO daily_metrics (trading_date, start_equity, current_equity, max_drawdown_percent, trades_today)
                VALUES (%s, %s, %s, 0.0, 0)
                \"\"\",
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
            
    return start_equity"""

new_get_func = """def get_or_create_daily_start_equity(current_equity):
    \"\"\"
    Retrieves the starting equity for the current day from the database.
    If it doesn't exist, date/account ID mismatches, initializes it with the current equity.
    Uses caching to minimize database connections.
    \"\"\"
    global _cached_start_equity, _cached_start_equity_date, _cached_last_login
    today = get_broker_today_date()
    
    current_login = 0
    try:
        acc = mt5.account_info()
        if acc:
            current_login = int(acc.login)
    except Exception:
        pass
        
    if _cached_last_login is not None and current_login > 0 and _cached_last_login != current_login:
        logger.info(f"Safeguards: Account switch detected ({_cached_last_login} -> {current_login}). Resetting daily start equity cache to ${current_equity:.2f}")
        _cached_start_equity = None
        _cached_start_equity_date = None
        
    _cached_last_login = current_login if current_login > 0 else _cached_last_login
    
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
        
        # Check if login has changed compared to last saved login in DB
        login_changed = False
        cur.execute("SELECT mt5_login FROM bot_state WHERE id = 1")
        state_row = cur.fetchone()
        if state_row and current_login > 0 and state_row[0] is not None and int(state_row[0]) != current_login:
            login_changed = True
            
        if row:
            start_equity = float(row[0])
            logger.info(f"Retrieved daily starting equity from database: ${start_equity:.2f}")
            
            # Reset if no trades taken today OR if account/login changed
            trades_today = get_trades_count_today()
            if (trades_today == 0 or login_changed) and abs(start_equity - current_equity) > 0.01:
                cur.execute(
                    "UPDATE daily_metrics SET start_equity = %s, current_equity = %s WHERE trading_date = %s",
                    (current_equity, current_equity, today)
                )
                conn.commit()
                logger.info(f"Account changed or new session: Automatically updated daily start equity to: ${current_equity:.2f}")
                start_equity = current_equity
        else:
            # Create a new record for today
            cur.execute(
                \"\"\"
                INSERT INTO daily_metrics (trading_date, start_equity, current_equity, max_drawdown_percent, trades_today)
                VALUES (%s, %s, %s, 0.0, 0)
                \"\"\",
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
            
    return start_equity"""

if old_get_func in content:
    content = content.replace(old_get_func, new_get_func)
    print("get_or_create_daily_start_equity successfully updated in risk_safeguards.py.")
else:
    print("old_get_func target not found in risk_safeguards.py!")

with open(risk_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
