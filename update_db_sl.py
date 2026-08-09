import psycopg2
from psycopg2.extras import RealDictCursor

conn_str = "postgresql://neondb_owner:npg_fh3GJr2iTRCW@ep-bitter-mode-aoi5d1e5-pooler.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

try:
    conn = psycopg2.connect(conn_str)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Update bot_state table with $50 USD Hard SL / 1.07% drawdown and $45 USD risk settings
    cur.execute("""
        UPDATE bot_state 
        SET drawdown_percent = 1.07,
            sl_pips = 45.0,
            updated_at = NOW()
        WHERE id = 1;
    """)
    conn.commit()
    
    # Fetch updated bot_state
    cur.execute("SELECT * FROM bot_state WHERE id = 1;")
    row = cur.fetchone()
    print("=== UPDATED BOT STATE IN NEON POSTGRESQL ===")
    print(f"Active Pair: {row['active_pair']}")
    print(f"Equity: ${row['equity']}")
    print(f"SL Pips (Risk Cash Equivalent): {row['sl_pips']} Pips / $45 USD")
    print(f"Max Daily Hard Loss (Drawdown %): {row['drawdown_percent']}% / $50 USD Cap")
    print(f"Updated At: {row['updated_at']}")
    
    cur.close()
    conn.close()
    print("\nDatabase updated successfully!")
except Exception as e:
    print(f"Database error: {e}")
