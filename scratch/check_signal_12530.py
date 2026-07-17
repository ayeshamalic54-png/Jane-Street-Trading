import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM signals WHERE id = 12530")
    colnames = [desc[0] for desc in cur.description]
    row = cur.fetchone()
    print("=== SIGNAL 12530 ===")
    if row:
        for col, val in zip(colnames, row):
            print(f"{col}: {val}")
    else:
        print("Signal 12530 not found.")
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
