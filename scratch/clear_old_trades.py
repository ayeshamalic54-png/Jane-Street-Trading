import psycopg2
import datetime

db_url = "postgresql://neondb_owner:npg_fh3GJr2iTRCW@ep-bitter-mode-aoi5d1e5-pooler.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
conn = psycopg2.connect(db_url)
cur = conn.cursor()

today = datetime.date.today()
print(f"Today's date is: {today}")

# Inspect total trades count
cur.execute("SELECT COUNT(*) FROM trades")
total_count = cur.fetchone()[0]
print(f"Total trades in table currently: {total_count}")

# Inspect open trades (we must NOT delete open trades!)
cur.execute("SELECT COUNT(*) FROM trades WHERE status = 'OPEN'")
open_count = cur.fetchone()[0]
print(f"Active OPEN trades: {open_count}")

# Delete closed trades that entered before today
cur.execute(
    "DELETE FROM trades WHERE status = 'CLOSED' AND CAST(entry_time AS DATE) < %s",
    (today,)
)
deleted_count = cur.rowcount
conn.commit()

print(f"Deleted {deleted_count} closed trades entered before today.")

# Re-inspect to confirm counts
cur.execute("SELECT COUNT(*) FROM trades")
new_total_count = cur.fetchone()[0]
print(f"New total trades in table: {new_total_count}")

cur.close()
conn.close()
