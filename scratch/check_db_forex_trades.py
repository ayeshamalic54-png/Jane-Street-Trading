import psycopg2

db_url = "postgresql://neondb_owner:npg_fh3GJr2iTRCW@ep-bitter-mode-aoi5d1e5-pooler.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

try:
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    
    # Query only Forex / Metals / Indices trades (not ending in USDT)
    cur.execute("SELECT * FROM trades WHERE symbol NOT LIKE '%USDT' ORDER BY entry_time DESC LIMIT 100")
    colnames_t = [desc[0] for desc in cur.description]
    trades = cur.fetchall()
    print("=== RECENT FOREX / METALS / INDICES DB TRADES ===")
    if not trades:
        print("No Forex trades found in DB.")
    else:
        for t in trades:
            trade_dict = dict(zip(colnames_t, t))
            print(f"Ticket: {trade_dict['ticket']} | Symbol: {trade_dict['symbol']} | Type: {trade_dict['order_type']} | Lots: {trade_dict['lots']} | Entry: {trade_dict['entry_price']} | Close: {trade_dict['close_price']} | Profit: {trade_dict['profit']} | Status: {trade_dict['status']} | Comment: {trade_dict['comment']} | Time: {trade_dict['entry_time']}")
            
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error querying database: {e}")
