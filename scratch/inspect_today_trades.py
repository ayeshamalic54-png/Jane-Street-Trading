import psycopg2

db_url = "postgresql://neondb_owner:npg_fh3GJr2iTRCW@ep-bitter-mode-aoi5d1e5-pooler.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
conn = psycopg2.connect(db_url)
cur = conn.cursor()

cur.execute("SELECT ticket, symbol, order_type, lots, profit, entry_time, comment FROM trades WHERE status = 'CLOSED'")
rows = cur.fetchall()
print("Today's closed trades in DB:")
for r in rows:
    print(r)

cur.close()
conn.close()
