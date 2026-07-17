import psycopg2

db_url = "postgresql://neondb_owner:npg_fh3GJr2iTRCW@ep-bitter-mode-aoi5d1e5-pooler.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

try:
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute("SELECT * FROM bot_state")
    colnames = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    print("Columns:", colnames)
    for r in rows:
        print("Values:", r)
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
