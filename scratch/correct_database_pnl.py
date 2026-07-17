import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    
    # Update ZECUSDT trades to show the actual stop loss price and loss instead of 0.00
    cur.execute("""
        UPDATE trades 
        SET close_price = 572.26, profit = -1.07 
        WHERE ticket IN (803400921901, 803400921935, 803400921958)
    """)
    
    # Update XRPUSDT hedge leg to show its actual price and minimal profit/loss
    cur.execute("""
        UPDATE trades 
        SET close_price = 1.10845, profit = -0.15 
        WHERE ticket = 153858157405
    """)
    
    conn.commit()
    print("Database PnL correction committed successfully.")
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
