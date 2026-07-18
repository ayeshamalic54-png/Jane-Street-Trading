import psycopg2
from psycopg2 import extras
import datetime
import os

def load_env():
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

load_env()
DB_URL = os.getenv("DATABASE_URL", "")
if not DB_URL:
    raise RuntimeError("DATABASE_URL is not set. Add it to your .env file.")

def get_connection():
    """Returns a new connection to the Neon database with retries to handle transient errors."""
    import time
    last_err = None
    for attempt in range(5):
        try:
            conn = psycopg2.connect(DB_URL, connect_timeout=10)
            # Set statement timeout of 15 seconds to prevent hanging queries
            with conn.cursor() as cur:
                cur.execute("SET statement_timeout = 15000;")
            return conn
        except Exception as e:
            last_err = e
            print(f"Database connection attempt {attempt+1} failed: {e}. Retrying in 2 seconds...")
            time.sleep(2)
    raise last_err

def initialize_database():
    """Creates all tables if they do not exist."""
    commands = [
        """
        CREATE TABLE IF NOT EXISTS daily_metrics (
            trading_date DATE PRIMARY KEY,
            start_equity NUMERIC(15, 2) NOT NULL,
            current_equity NUMERIC(15, 2) NOT NULL,
            max_drawdown_percent NUMERIC(5, 2) DEFAULT 0.00,
            trades_today INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS trades (
            ticket BIGINT PRIMARY KEY,
            symbol VARCHAR(50) NOT NULL,
            order_type VARCHAR(10) NOT NULL,
            lots NUMERIC(10, 2) NOT NULL,
            entry_price NUMERIC(15, 5) NOT NULL,
            close_price NUMERIC(15, 5),
            profit NUMERIC(15, 2),
            entry_time TIMESTAMP NOT NULL,
            close_time TIMESTAMP,
            status VARCHAR(20) DEFAULT 'OPEN',
            comment VARCHAR(100),
            signal_id INTEGER REFERENCES signals(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS signals (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            symbol_a VARCHAR(50) NOT NULL,
            symbol_b VARCHAR(50) NOT NULL,
            price_a NUMERIC(15, 5) NOT NULL,
            price_b NUMERIC(15, 5) NOT NULL,
            beta NUMERIC(15, 5) NOT NULL,
            alpha NUMERIC(15, 5) NOT NULL,
            z_score NUMERIC(10, 4) NOT NULL,
            obi NUMERIC(10, 4) NOT NULL,
            action VARCHAR(20) NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS bot_state (
            id SERIAL PRIMARY KEY,
            active_pair VARCHAR(50) NOT NULL DEFAULT 'EURUSD/GBPUSD',
            system_status VARCHAR(50) NOT NULL DEFAULT 'BOT OFFLINE',
            equity NUMERIC(15, 2) DEFAULT 0,
            drawdown_percent NUMERIC(5, 2) DEFAULT 0,
            floating_profit NUMERIC(15, 2) DEFAULT 0,
            z_score NUMERIC(10, 4) DEFAULT 0,
            hedge_ratio NUMERIC(10, 4) DEFAULT 0,
            obi_a NUMERIC(10, 4) DEFAULT 0,
            obi_b NUMERIC(10, 4) DEFAULT 0,
            trades_today INTEGER DEFAULT 0,
            sl_pips NUMERIC(6, 1) DEFAULT 10,
            smc_enabled BOOLEAN DEFAULT TRUE,
            auto_execute BOOLEAN DEFAULT TRUE,
            crypto_enabled BOOLEAN DEFAULT TRUE,
            metals_enabled BOOLEAN DEFAULT TRUE,
            forex_enabled BOOLEAN DEFAULT TRUE,
            indices_enabled BOOLEAN DEFAULT TRUE,
            risk_limits_enabled BOOLEAN DEFAULT TRUE,
            last_heartbeat TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS fvg_zones (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(50) NOT NULL,
            zone_type VARCHAR(30) NOT NULL,
            low_price NUMERIC(15, 5) NOT NULL,
            high_price NUMERIC(15, 5) NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS scanned_assets (
            symbol_pair VARCHAR(100) PRIMARY KEY,
            price_a NUMERIC(15, 5),
            price_b NUMERIC(15, 5),
            win_rate NUMERIC(5, 2),
            z_score NUMERIC(10, 4),
            action VARCHAR(20),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    ]

    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        for cmd in commands:
            cur.execute(cmd)
        conn.commit()

        # Add risk_limits_enabled column to bot_state if it doesn't exist yet
        cur.execute("""
            SELECT 1 FROM information_schema.columns 
            WHERE table_name='bot_state' AND column_name='risk_limits_enabled'
        """)
        if not cur.fetchone():
            cur.execute("ALTER TABLE bot_state ADD COLUMN risk_limits_enabled BOOLEAN DEFAULT TRUE")
            conn.commit()
            print("Added risk_limits_enabled column to bot_state table.")

        # Add signal_id column to trades if it doesn't exist yet
        cur.execute("""
            SELECT 1 FROM information_schema.columns 
            WHERE table_name='trades' AND column_name='signal_id'
        """)
        if not cur.fetchone():
            cur.execute("ALTER TABLE trades ADD COLUMN signal_id INTEGER REFERENCES signals(id)")
            conn.commit()
            print("Added signal_id column to trades table.")

        # Add z_entry_threshold column to bot_state if it doesn't exist yet
        cur.execute("""
            SELECT 1 FROM information_schema.columns 
            WHERE table_name='bot_state' AND column_name='z_entry_threshold'
        """)
        if not cur.fetchone():
            cur.execute("ALTER TABLE bot_state ADD COLUMN z_entry_threshold NUMERIC(4, 2) DEFAULT 2.00")
            conn.commit()
            print("Added z_entry_threshold column to bot_state table.")

        # Add tp_pips column to bot_state if it doesn't exist yet
        cur.execute("""
            SELECT 1 FROM information_schema.columns 
            WHERE table_name='bot_state' AND column_name='tp_pips'
        """)
        if not cur.fetchone():
            cur.execute("ALTER TABLE bot_state ADD COLUMN tp_pips NUMERIC(6, 1) DEFAULT 20.0")
            conn.commit()
            print("Added tp_pips column to bot_state table.")

        # Add default_lots column to bot_state if it doesn't exist yet
        cur.execute("""
            SELECT 1 FROM information_schema.columns 
            WHERE table_name='bot_state' AND column_name='default_lots'
        """)
        if not cur.fetchone():
            cur.execute("ALTER TABLE bot_state ADD COLUMN default_lots NUMERIC(5, 3) DEFAULT 0.01")
            conn.commit()
            print("Added default_lots column to bot_state table.")

        # Add admin_username column to bot_state if it doesn't exist yet
        cur.execute("""
            SELECT 1 FROM information_schema.columns 
            WHERE table_name='bot_state' AND column_name='admin_username'
        """)
        if not cur.fetchone():
            cur.execute("ALTER TABLE bot_state ADD COLUMN admin_username VARCHAR(50) DEFAULT 'wasee'")
            conn.commit()
            print("Added admin_username column to bot_state table.")

        # Add admin_password column to bot_state if it doesn't exist yet
        cur.execute("""
            SELECT 1 FROM information_schema.columns 
            WHERE table_name='bot_state' AND column_name='admin_password'
        """)
        if not cur.fetchone():
            cur.execute("ALTER TABLE bot_state ADD COLUMN admin_password VARCHAR(100) DEFAULT 'AWais1133@'")
            conn.commit()
            print("Added admin_password column to bot_state table.")

        cur.close()
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Failed to initialize database: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def update_bot_state(active_pair, system_status, equity, drawdown_percent,
                     floating_profit, z_score, hedge_ratio, obi_a, obi_b,
                     trades_today, sl_pips=10.0):
    """
    Upserts live bot telemetry into bot_state table.
    Tracks overall drawdown, max equity peak, and resets metrics if a new MT5 account is attached.
    """
    query = """
        INSERT INTO bot_state (
            id, active_pair, system_status, equity, drawdown_percent,
            floating_profit, z_score, hedge_ratio, obi_a, obi_b,
            trades_today, sl_pips, last_heartbeat, updated_at,
            initial_balance, overall_drawdown, max_equity_peak, mt5_login
        )
        VALUES (
            1, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s, %s, %s, %s
        )
        ON CONFLICT (id) DO UPDATE SET
            system_status      = EXCLUDED.system_status,
            equity             = EXCLUDED.equity,
            drawdown_percent   = EXCLUDED.drawdown_percent,
            floating_profit    = EXCLUDED.floating_profit,
            z_score            = EXCLUDED.z_score,
            hedge_ratio        = EXCLUDED.hedge_ratio,
            obi_a              = EXCLUDED.obi_a,
            obi_b              = EXCLUDED.obi_b,
            trades_today       = EXCLUDED.trades_today,
            initial_balance    = EXCLUDED.initial_balance,
            overall_drawdown   = EXCLUDED.overall_drawdown,
            max_equity_peak    = EXCLUDED.max_equity_peak,
            mt5_login          = EXCLUDED.mt5_login,
            last_heartbeat     = CURRENT_TIMESTAMP,
            updated_at         = CURRENT_TIMESTAMP
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # 1. Fetch current login info from MT5
        import MetaTrader5 as mt5
        mt5_login_val = 0
        terminal_active = False
        try:
            acc_info = mt5.account_info()
            if acc_info:
                mt5_login_val = int(acc_info.login)
                terminal_active = True
        except Exception:
            pass

        # 2. Query current saved overall metrics from DB
        cur.execute("SELECT initial_balance, max_equity_peak, mt5_login FROM bot_state WHERE id = 1")
        row = cur.fetchone()

        initial_balance_val = float(equity)
        max_equity_peak_val = float(equity)
        saved_login = 0

        if row:
            initial_balance_val = float(row[0] or equity)
            max_equity_peak_val = float(row[1] or equity)
            saved_login = int(row[2] or 0)

        # 3. Detect if a new account has been attached OR if there is a mismatch on 0 active trades today
        trades_today_val = int(trades_today)
        # Check if there are active positions in the database
        cur.execute("SELECT COUNT(*) FROM trades WHERE status = 'OPEN'")
        open_trades_count = cur.fetchone()[0] or 0
        has_positions = (open_trades_count > 0) or (float(floating_profit) != 0.0)

        login_changed = (mt5_login_val > 0 and mt5_login_val != saved_login)
        mismatch_reset = (mt5_login_val > 0 and mt5_login_val == saved_login and trades_today_val == 0 and not has_positions and abs(initial_balance_val - float(equity)) > 0.01)

        if terminal_active and (login_changed or mismatch_reset):
            print(f"Syncing account metrics: Resetting initial_balance and max_equity_peak to current equity: ${equity:.2f} (login_changed={login_changed}, mismatch_reset={mismatch_reset})")
            initial_balance_val = float(equity)
            max_equity_peak_val = float(equity)
            if login_changed:
                saved_login = mt5_login_val

        # 4. Update peak equity if exceeded
        if float(equity) > max_equity_peak_val:
            max_equity_peak_val = float(equity)

        # 5. Calculate overall drawdown from peak
        overall_drawdown_val = 0.00
        if max_equity_peak_val > 0.0:
            overall_drawdown_val = ((max_equity_peak_val - float(equity)) / max_equity_peak_val) * 100.0
            overall_drawdown_val = max(0.00, overall_drawdown_val)

        cur.execute(query, (
            str(active_pair), str(system_status),
            float(equity), float(drawdown_percent),
            float(floating_profit), float(z_score),
            float(hedge_ratio), float(obi_a), float(obi_b),
            int(trades_today), float(sl_pips),
            float(initial_balance_val), float(overall_drawdown_val),
            float(max_equity_peak_val), int(saved_login)
        ))
        conn.commit()
        cur.close()
    except Exception as e:
        print(f"Error updating bot_state: {e}")
    finally:
        if conn:
            conn.close()

def get_auto_execute():
    """
    Reads auto_execute flag from bot_state. Returns True by default.
    Called by the bot every ~10s to check if auto-trading is enabled from dashboard.
    """
    query = "SELECT auto_execute FROM bot_state WHERE id = 1"
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(query)
        row = cur.fetchone()
        cur.close()
        if row is not None:
            return bool(row[0])
        return True
    except Exception as e:
        print(f"Error reading auto_execute: {e}")
        return True
    finally:
        if conn:
            conn.close()

def log_fvg_zones(symbol, zones_dict):
    """
    Replaces all active FVG/OB/Breaker/iFVG zones for a symbol.
    zones_dict: output of detect_smc_zones() — dict of zone_type -> [(low, high), ...]
    Called every 10 loops (~20s) when SMC scan updates.
    """
    zone_type_map = {
        'bullish_ob':      'bullish_ob',
        'bearish_ob':      'bearish_ob',
        'bullish_fvg':     'bullish_fvg',
        'bearish_fvg':     'bearish_fvg',
        'bullish_breaker': 'bullish_breaker',
        'bearish_breaker': 'bearish_breaker',
        'bullish_ifvg':    'bullish_ifvg',
        'bearish_ifvg':    'bearish_ifvg',
    }

    rows = []
    for zone_key, db_type in zone_type_map.items():
        for (low, high) in zones_dict.get(zone_key, []):
            rows.append((symbol, db_type, float(low), float(high)))

    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM fvg_zones WHERE symbol = %s", (symbol,))
        if rows:
            cur.executemany(
                "INSERT INTO fvg_zones (symbol, zone_type, low_price, high_price, updated_at) "
                "VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)",
                rows
            )
        conn.commit()
        cur.close()
    except Exception as e:
        print(f"Error logging FVG zones: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def log_signal(symbol_a, symbol_b, price_a, price_b, beta, alpha, z_score, obi, action):
    """Logs a generated mathematical signal. Returns the signal ID."""
    query = """
        INSERT INTO signals (symbol_a, symbol_b, price_a, price_b, beta, alpha, z_score, obi, action)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(query, (
            symbol_a, symbol_b,
            float(price_a), float(price_b),
            float(beta), float(alpha),
            float(z_score), float(obi),
            action
        ))
        row = cur.fetchone()
        conn.commit()
        cur.close()
        if row:
            return row[0]
    except Exception as e:
        print(f"Error logging signal to database: {e}")
    finally:
        if conn:
            conn.close()
    return None

def log_trade_entry(ticket, symbol, order_type, lots, entry_price, entry_time, comment="", signal_id=None):
    """Logs the entry of a trade."""
    query = """
        INSERT INTO trades (ticket, symbol, order_type, lots, entry_price, entry_time, status, comment, signal_id)
        VALUES (%s, %s, %s, %s, %s, %s, 'OPEN', %s, %s)
        ON CONFLICT (ticket) DO NOTHING
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(query, (
            int(ticket), symbol, order_type,
            float(lots), float(entry_price), entry_time, comment,
            int(signal_id) if signal_id is not None else None
        ))
        conn.commit()
        cur.close()
    except Exception as e:
        print(f"Error logging trade entry: {e}")
    finally:
        if conn:
            conn.close()

def get_open_trades_count(symbol=None):
    """Returns the number of currently open trades in the database."""
    query = "SELECT COUNT(*) FROM trades WHERE status = 'OPEN'"
    params = ()
    if symbol:
        query += " AND symbol = %s"
        params = (symbol,)
    conn = None
    count = 0
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(query, params)
        count = cur.fetchone()[0]
        cur.close()
    except Exception as e:
        print(f"Error fetching open trades count: {e}")
    finally:
        if conn:
            conn.close()
    return count

def log_trade_exit(ticket, close_price, profit, close_time):
    """Updates a trade when it is closed."""
    query = """
        UPDATE trades
        SET close_price = %s, profit = %s, close_time = %s, status = 'CLOSED'
        WHERE ticket = %s
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(query, (
            float(close_price), float(profit), close_time, int(ticket)
        ))
        conn.commit()
        cur.close()
    except Exception as e:
        print(f"Error logging trade exit: {e}")
    finally:
        if conn:
            conn.close()

def update_daily_metrics(date_obj, start_equity, current_equity, max_dd, trades_count):
    """Updates the daily challenge metrics in database."""
    query = """
        INSERT INTO daily_metrics (trading_date, start_equity, current_equity, max_drawdown_percent, trades_today, updated_at)
        VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (trading_date) DO UPDATE
        SET current_equity = EXCLUDED.current_equity,
            max_drawdown_percent = GREATEST(daily_metrics.max_drawdown_percent, EXCLUDED.max_drawdown_percent),
            trades_today = EXCLUDED.trades_today,
            updated_at = CURRENT_TIMESTAMP
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(query, (
            date_obj,
            float(start_equity), float(current_equity),
            float(max_dd), int(trades_count)
        ))
        conn.commit()
        cur.close()
    except Exception as e:
        print(f"Error updating daily metrics: {e}")
    finally:
        if conn:
            conn.close()

def update_scanned_asset(symbol_pair, price_a, price_b, win_rate, z_score, action):
    query = """
        INSERT INTO scanned_assets (symbol_pair, price_a, price_b, win_rate, z_score, action, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (symbol_pair) DO UPDATE
        SET price_a = EXCLUDED.price_a,
            price_b = EXCLUDED.price_b,
            win_rate = EXCLUDED.win_rate,
            z_score = EXCLUDED.z_score,
            action = EXCLUDED.action,
            updated_at = CURRENT_TIMESTAMP
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(query, (
            symbol_pair,
            float(price_a), float(price_b),
            float(win_rate), float(z_score),
            action
        ))
        conn.commit()
        cur.close()
    except Exception as e:
        print(f"Error updating scanned asset: {e}")
    finally:
        if conn:
            conn.close()


def reset_database_metrics_for_new_account(login_id, equity):
    """
    Force-updates the database metrics (both bot_state and daily_metrics for today)
    to match the new connected account's starting balance.
    """
    import datetime
    today = datetime.date.today()
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # 1. Update bot_state
        cur.execute("""
            UPDATE bot_state 
            SET initial_balance = %s, max_equity_peak = %s, mt5_login = %s, equity = %s 
            WHERE id = 1
        """, (float(equity), float(equity), int(login_id), float(equity)))
        
        # 2. Update or Insert daily_metrics for today
        cur.execute("SELECT 1 FROM daily_metrics WHERE trading_date = %s", (today,))
        if cur.fetchone():
            cur.execute("""
                UPDATE daily_metrics 
                SET start_equity = %s, current_equity = %s, max_drawdown_percent = 0.00 
                WHERE trading_date = %s
            """, (float(equity), float(equity), today))
        else:
            cur.execute("""
                INSERT INTO daily_metrics (trading_date, start_equity, current_equity, max_drawdown_percent, trades_today)
                VALUES (%s, %s, %s, 0.0, 0)
            """, (today, float(equity), float(equity)))
            
        conn.commit()
        cur.close()
        print(f"Successfully reset database metrics for new account {login_id} (Equity: ${equity:.2f})")
    except Exception as e:
        print(f"Error resetting database metrics for new account: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
            
    # Also invalidate the local safeguards caches
    try:
        import risk_safeguards
        risk_safeguards._cached_start_equity = float(equity)
        risk_safeguards._cached_start_equity_date = today
        risk_safeguards._cached_last_login = int(login_id)
    except Exception as ex:
        print(f"Error updating risk_safeguards cache: {ex}")

if __name__ == "__main__":
    initialize_database()
