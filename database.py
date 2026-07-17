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

        # Add initial_balance column to bot_state if it doesn't exist yet
        cur.execute("""
            SELECT 1 FROM information_schema.columns 
            WHERE table_name='bot_state' AND column_name='initial_balance'
        """)
        if not cur.fetchone():
            cur.execute("ALTER TABLE bot_state ADD COLUMN initial_balance NUMERIC(15, 2) DEFAULT 100000.00")
            conn.commit()
            print("Added initial_balance column to bot_state table.")

        # Add overall_drawdown column to bot_state if it doesn't exist yet
        cur.execute("""
            SELECT 1 FROM information_schema.columns 
            WHERE table_name='bot_state' AND column_name='overall_drawdown'
        """)
        if not cur.fetchone():
            cur.execute("ALTER TABLE bot_state ADD COLUMN overall_drawdown NUMERIC(5, 2) DEFAULT 0.00")
            conn.commit()
            print("Added overall_drawdown column to bot_state table.")

        # Add max_equity_peak column to bot_state if it doesn't exist yet
        cur.execute("""
            SELECT 1 FROM information_schema.columns 
            WHERE table_name='bot_state' AND column_name='max_equity_peak'
        """)
        if not cur.fetchone():
            cur.execute("ALTER TABLE bot_state ADD COLUMN max_equity_peak NUMERIC(15, 2) DEFAULT 0.00")
            conn.commit()
            print("Added max_equity_peak column to bot_state table.")

        # Add mt5_login column to bot_state if it doesn't exist yet
        cur.execute("""
            SELECT 1 FROM information_schema.columns 
            WHERE table_name='bot_state' AND column_name='mt5_login'
        """)
        if not cur.fetchone():
            cur.execute("ALTER TABLE bot_state ADD COLUMN mt5_login INTEGER DEFAULT 0")
            conn.commit()
            print("Added mt5_login column to bot_state table.")

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

        # 3. Detect if a new account has been attached
        if terminal_active and mt5_login_val > 0 and mt5_login_val != saved_login:
            # Sync to the new account's metrics!
            print(f"New MT5 account detected: {mt5_login_val}. Resetting initial_balance and max_equity_peak to current equity: ${equity:.2f}")
            initial_balance_val = float(equity)
            max_equity_peak_val = float(equity)
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

if __name__ == "__main__":
    initialize_database()
