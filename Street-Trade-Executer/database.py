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
DB_URL = os.getenv("DATABASE_URL", 'postgresql://neondb_owner:npg_fh3GJr2iTRCW@ep-bitter-mode-aoi5d1e5-pooler.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require')

def get_connection():
    """Returns a new connection to the Neon database."""
    return psycopg2.connect(DB_URL)

def initialize_database():
    """Creates the tables if they do not exist."""
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
            order_type VARCHAR(10) NOT NULL, -- 'BUY' or 'SELL'
            lots NUMERIC(10, 2) NOT NULL,
            entry_price NUMERIC(15, 5) NOT NULL,
            close_price NUMERIC(15, 5),
            profit NUMERIC(15, 2),
            entry_time TIMESTAMP NOT NULL,
            close_time TIMESTAMP,
            status VARCHAR(20) DEFAULT 'OPEN', -- 'OPEN', 'CLOSED'
            comment VARCHAR(100)
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
            action VARCHAR(20) NOT NULL -- 'BUY_SPREAD', 'SELL_SPREAD', 'NONE'
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
        cur.close()
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Failed to initialize database: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def log_signal(symbol_a, symbol_b, price_a, price_b, beta, alpha, z_score, obi, action):
    """Logs a generated mathematical signal."""
    query = """
        INSERT INTO signals (symbol_a, symbol_b, price_a, price_b, beta, alpha, z_score, obi, action)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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
        conn.commit()
        cur.close()
    except Exception as e:
        print(f"Error logging signal to database: {e}")
    finally:
        if conn:
            conn.close()

def log_trade_entry(ticket, symbol, order_type, lots, entry_price, entry_time, comment=""):
    """Logs the entry of a trade."""
    query = """
        INSERT INTO trades (ticket, symbol, order_type, lots, entry_price, entry_time, status, comment)
        VALUES (%s, %s, %s, %s, %s, %s, 'OPEN', %s)
        ON CONFLICT (ticket) DO NOTHING
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(query, (
            int(ticket), symbol, order_type, 
            float(lots), float(entry_price), entry_time, comment
        ))
        conn.commit()
        cur.close()
    except Exception as e:
        print(f"Error logging trade entry: {e}")
    finally:
        if conn:
            conn.close()

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

def update_daily_metrics(date_obj, start_equity, current_equity, max_dd, trades_count, login_id=None):
    """Updates the daily challenge metrics in database without needing 'id' column or ON CONFLICT constraint."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        if login_id is not None:
            cur.execute("SELECT max_drawdown_percent FROM daily_metrics WHERE trading_date = %s AND mt5_login = %s", (date_obj, int(login_id)))
        else:
            cur.execute("SELECT max_drawdown_percent FROM daily_metrics WHERE trading_date = %s", (date_obj,))
            
        row = cur.fetchone()
        if row:
            prev_max_dd = float(row[0] or 0.0)
            new_max_dd = max(prev_max_dd, float(max_dd))
            if login_id is not None:
                cur.execute("""
                    UPDATE daily_metrics 
                    SET current_equity = %s, max_drawdown_percent = %s, trades_today = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE trading_date = %s AND mt5_login = %s
                """, (float(current_equity), new_max_dd, int(trades_count), date_obj, int(login_id)))
            else:
                cur.execute("""
                    UPDATE daily_metrics 
                    SET current_equity = %s, max_drawdown_percent = %s, trades_today = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE trading_date = %s
                """, (float(current_equity), new_max_dd, int(trades_count), date_obj))
        else:
            cur.execute("""
                INSERT INTO daily_metrics (trading_date, mt5_login, start_equity, current_equity, max_drawdown_percent, trades_today, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """, (date_obj, int(login_id or 0), float(start_equity), float(current_equity), float(max_dd), int(trades_count)))
            
        conn.commit()
        cur.close()
    except Exception as e:
        print(f"Error updating daily metrics: {e}")
    finally:
        if conn:
            conn.close()

# Initialize tables immediately if run directly
if __name__ == "__main__":
    initialize_database()
