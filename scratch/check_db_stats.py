import psycopg2

db_url = "postgresql://neondb_owner:npg_fh3GJr2iTRCW@ep-bitter-mode-aoi5d1e5-pooler.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

try:
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    
    # Total count
    cur.execute("SELECT COUNT(*) FROM trades")
    print(f"Total trades in DB: {cur.fetchone()[0]}")
    
    # Group by status
    cur.execute("SELECT status, COUNT(*) FROM trades GROUP BY status")
    print("Trades by status:", cur.fetchall())
    
    # Max entry time
    cur.execute("SELECT MAX(entry_time) FROM trades")
    print(f"Max entry time in DB: {cur.fetchone()[0]}")
    
    # Query trades where symbol is XAUUSD or GBPUSD or USDCHF from July 14, 15, 16
    cur.execute("SELECT * FROM trades WHERE entry_time >= '2026-07-14' AND symbol NOT LIKE '%USDT' ORDER BY entry_time DESC LIMIT 50")
    colnames_t = [desc[0] for desc in cur.description]
    trades = cur.fetchall()
    print("\n=== FOREX TRADES AFTER JULY 14 ===")
    for t in trades:
        trade_dict = dict(zip(colnames_t, t))
        print(f"Ticket: {trade_dict['ticket']} | Symbol: {trade_dict['symbol']} | Type: {trade_dict['order_type']} | Lots: {trade_dict['lots']} | Entry: {trade_dict['entry_price']} | Close: {trade_dict['close_price']} | Profit: {trade_dict['profit']} | Status: {trade_dict['status']} | Time: {trade_dict['entry_time']}")
        
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error querying database: {e}")
