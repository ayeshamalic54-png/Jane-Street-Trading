import psycopg2

db_url = "postgresql://neondb_owner:npg_fh3GJr2iTRCW@ep-bitter-mode-aoi5d1e5-pooler.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

try:
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    
    print("Deleting bot_state records where id != 1 to prevent dashboard conflicts...")
    cur.execute("DELETE FROM bot_state WHERE id != 1")
    conn.commit()
    print("Successfully cleaned up duplicate bot_state records!")
    
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
