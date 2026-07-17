import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    
    # Restore UNIUSDT and NEARUSDT trades to OPEN status
    cur.execute("""
        UPDATE trades 
        SET status = 'OPEN', close_price = NULL, close_time = NULL, profit = NULL 
        WHERE ticket IN (31996419737, 34220584761)
    """)
    conn.commit()
    print(f"Successfully restored {cur.rowcount} trades to OPEN status.")
    
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error restoring trades: {e}")
