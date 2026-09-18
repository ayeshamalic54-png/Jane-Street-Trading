import sqlite3
import pandas as pd
import glob

db_files = glob.glob("**/*.db", recursive=True) + glob.glob("*.db")
print("Found DB files:", db_files)

for db_path in db_files:
    try:
        conn = sqlite3.connect(db_path)
        tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table';", conn)
        print(f"\n--- Database: {db_path} ---")
        print("Tables:", tables['name'].tolist())
        
        if 'trades' in tables['name'].values:
            df_t = pd.read_sql("SELECT * FROM trades ORDER BY id DESC LIMIT 5", conn)
            print("\nRecent Trades:")
            print(df_t[['id', 'symbol', 'action', 'entry_price', 'sl_price', 'tp_price', 'status', 'created_at']] if not df_t.empty else "No trades")
            
        if 'signals' in tables['name'].values:
            df_s = pd.read_sql("SELECT * FROM signals ORDER BY id DESC LIMIT 5", conn)
            print("\nRecent Signals:")
            print(df_s[['id', 'symbol_a', 'action', 'price_a', 'created_at']] if not df_s.empty else "No signals")

        if 'smc_telemetry' in tables['name'].values:
            df_tel = pd.read_sql("SELECT * FROM smc_telemetry ORDER BY id DESC LIMIT 5", conn)
            print("\nRecent SMC Telemetry:")
            print(df_tel if not df_tel.empty else "No telemetry")
            
        conn.close()
    except Exception as e:
        print(f"Error reading {db_path}: {e}")
