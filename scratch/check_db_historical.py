import sys
import os
import psycopg2
from psycopg2.extras import RealDictCursor

sys.path.append(r"G:\google antigravity\jane_street_trading_system")
from database import get_connection

print("=== CHECKING NEON POSTGRES DATABASE FOR HISTORICAL CANDLES & TRADES ===")

try:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")
    tables = [r['table_name'] for r in cur.fetchall()]
    print("Database Tables:", tables)
    
    for t in ['trades', 'signals', 'daily_metrics', 'smc_telemetry']:
        if t in tables:
            cur.execute(f"SELECT COUNT(*) as cnt FROM {t};")
            count = cur.fetchone()['cnt']
            print(f"\nTable '{t}': {count} total rows")
            
            if count > 0:
                cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name='{t}';")
                cols = [c['column_name'] for c in cur.fetchall()]
                print(f"Columns in '{t}':", cols)
                
                # Get date range
                time_col = 'entry_time' if 'entry_time' in cols else ('created_at' if 'created_at' in cols else cols[0])
                cur.execute(f"SELECT MIN({time_col}) as min_t, MAX({time_col}) as max_t FROM {t};")
                range_res = cur.fetchone()
                print(f"Date Range in '{t}': {range_res['min_t']} to {range_res['max_t']}")
                
    cur.close()
    conn.close()
except Exception as e:
    print("Database error:", e)
