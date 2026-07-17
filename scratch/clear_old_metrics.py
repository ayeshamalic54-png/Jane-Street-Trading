import psycopg2
import datetime

db_url = "postgresql://neondb_owner:npg_fh3GJr2iTRCW@ep-bitter-mode-aoi5d1e5-pooler.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
conn = psycopg2.connect(db_url)
cur = conn.cursor()

today = datetime.date.today()
print(f"Today is: {today}")

# Inspect daily_metrics
cur.execute("SELECT trading_date, start_equity, current_equity, max_drawdown_percent, trades_today FROM daily_metrics ORDER BY trading_date DESC")
rows = cur.fetchall()
print("Current daily metrics rows:")
for r in rows:
    print(r)

# Delete rows older than today
cur.execute("DELETE FROM daily_metrics WHERE trading_date < %s", (today,))
deleted_count = cur.rowcount
conn.commit()

print(f"\nDeleted {deleted_count} historical daily metrics rows before today.")

# Re-inspect to confirm
cur.execute("SELECT trading_date, start_equity, current_equity, max_drawdown_percent, trades_today FROM daily_metrics ORDER BY trading_date DESC")
rows_after = cur.fetchall()
print("\nDaily metrics rows after deletion:")
for r in rows_after:
    print(r)

cur.close()
conn.close()
