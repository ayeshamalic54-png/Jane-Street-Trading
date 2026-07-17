import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
    """)
    print("=== TABLES IN DB ===")
    for r in cur.fetchall():
        print(r[0])
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
