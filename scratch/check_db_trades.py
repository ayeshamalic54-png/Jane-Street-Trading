import psycopg2

db_url = "postgresql://neondb_owner:npg_fh3GJr2iTRCW@ep-bitter-mode-aoi5d1e5-pooler.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

try:
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    
    # 1. Print bot_state
    cur.execute("SELECT * FROM bot_state")
    colnames = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    print("=== BOT STATE ===")
    for r in rows:
        print(dict(zip(colnames, r)))
        
    # 2. Print recent trades
    cur.execute("SELECT * FROM trades ORDER BY entry_time DESC LIMIT 50")
    colnames_t = [desc[0] for desc in cur.description]
    trades = cur.fetchall()
    print("\n=== RECENT DB TRADES ===")
    for t in trades:
        trade_dict = dict(zip(colnames_t, t))
        print(f"Ticket: {trade_dict['ticket']} | Symbol: {trade_dict['symbol']} | Type: {trade_dict['order_type']} | Lots: {trade_dict['lots']} | Entry: {trade_dict['entry_price']} | Profit: {trade_dict['profit']} | Status: {trade_dict['status']} | Comment: {trade_dict['comment']} | Time: {trade_dict['entry_time']}")
        
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error querying database: {e}")
