import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    # Restore the UNI trade to OPEN
    cur.execute("UPDATE trades SET status = 'OPEN', close_price = NULL, close_time = NULL, profit = NULL WHERE ticket = 31997005084")
    print(f"Restored {cur.rowcount} UNIUSDT trade to OPEN.")
    conn.commit()
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error restoring trade: {e}")
