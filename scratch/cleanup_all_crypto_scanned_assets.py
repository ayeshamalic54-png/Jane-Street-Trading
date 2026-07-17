import psycopg2

db_url = "postgresql://neondb_owner:npg_fh3GJr2iTRCW@ep-bitter-mode-aoi5d1e5-pooler.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

try:
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    
    print("Purging all crypto pairs from scanned_assets table in database...")
    cur.execute("DELETE FROM scanned_assets WHERE symbol_pair LIKE '%USDT%'")
    conn.commit()
    print("Successfully purged crypto scanned assets!")
    
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
