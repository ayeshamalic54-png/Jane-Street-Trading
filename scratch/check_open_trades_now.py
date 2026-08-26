import sys
sys.path.append(r'G:\google antigravity\jane_street_trading_system')
from database import get_connection

conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT ticket, symbol, order_type, lots, entry_price, status, comment FROM trades WHERE status = 'OPEN'")
rows = cur.fetchall()
print(f"TOTAL OPEN TRADES IN DATABASE: {len(rows)}")
for r in rows:
    print(r)
cur.close()
conn.close()
