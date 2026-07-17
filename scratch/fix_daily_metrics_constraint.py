import psycopg2
import os

db_url = "postgresql://neondb_owner:npg_fh3GJr2iTRCW@ep-bitter-mode-aoi5d1e5-pooler.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

try:
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    
    # 1. Check if bot_id column exists
    cur.execute("""
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='daily_metrics' AND column_name='bot_id'
    """)
    has_bot_id = cur.fetchone()
    
    if has_bot_id:
        print("bot_id column found. Deleting duplicate bot_id = 2 records to clean up metrics...")
        # Delete rows for bot_id = 2 to ensure we don't have duplicate dates
        cur.execute("DELETE FROM daily_metrics WHERE bot_id = 2")
        conn.commit()
        
    print("Dropping existing daily_metrics primary key / unique constraints...")
    # Re-establish clean primary key constraint on trading_date only
    cur.execute("ALTER TABLE daily_metrics DROP CONSTRAINT IF EXISTS daily_metrics_pkey")
    cur.execute("ALTER TABLE daily_metrics DROP CONSTRAINT IF EXISTS daily_metrics_trading_date_bot_id_key")
    conn.commit()
    
    print("Re-creating primary key constraint on trading_date...")
    # Delete any duplicate trading_date if somehow still present
    cur.execute("""
        DELETE FROM daily_metrics a USING daily_metrics b 
        WHERE a.updated_at < b.updated_at AND a.trading_date = b.trading_date
    """)
    conn.commit()
    
    cur.execute("ALTER TABLE daily_metrics ADD CONSTRAINT daily_metrics_pkey PRIMARY KEY (trading_date)")
    conn.commit()
    print("daily_metrics primary key restored to (trading_date) successfully!")
    
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error resetting daily_metrics constraint: {e}")
