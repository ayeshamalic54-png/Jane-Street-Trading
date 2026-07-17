import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM signals LIMIT 1")
    colnames = [desc[0] for desc in cur.description]
    print("signals columns:", colnames)
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
