import datetime
import time
import psycopg2
import sys
import os

# Add parent path to import main
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main

# Mock close_single_trade to record invocations instead of calling MT5 API
closed_tickets = []
def mock_close_single_trade(symbol, ticket, volume, order_type):
    print(f"[MOCK CLOSE] Ticket: {ticket} | Symbol: {symbol} | Lots: {volume}")
    closed_tickets.append(ticket)
    return True

main.close_single_trade = mock_close_single_trade

def run_test():
    print("=== Testing 35-Second Hold Time Safety ===")
    
    db_url = "postgresql://neondb_owner:npg_fh3GJr2iTRCW@ep-bitter-mode-aoi5d1e5-pooler.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    
    # Clean up any existing test trades/signals
    cur.execute("DELETE FROM trades WHERE comment LIKE 'TestHold%'")
    cur.execute("DELETE FROM signals WHERE id = 99999")
    conn.commit()
    
    # Insert dummy signal to satisfy foreign key constraint
    cur.execute(
        """
        INSERT INTO signals (id, symbol_a, symbol_b, price_a, price_b, beta, alpha, z_score, obi, action)
        VALUES (99999, 'EURUSD', 'GBPUSD', 1.1400, 1.3400, 1.0, 0.0, 0.0, 0.0, 'BUY')
        """
    )
    conn.commit()
    
    # Test Case 1: Trade is 10 seconds old (less than 35s limit) -> Exit MUST be deferred
    print("\n--- Test Case 1: 10 Seconds Old Trade (Less than 35s) ---")
    closed_tickets.clear()
    
    now = datetime.datetime.now()
    entry_time_young = now - datetime.timedelta(seconds=10)
    
    # Insert mock Leg A and Leg B open trades
    ticket_a = 9999901
    ticket_b = 9999902
    signal_id = 99999
    
    cur.execute(
        """
        INSERT INTO trades (ticket, symbol, order_type, lots, entry_price, entry_time, status, comment, signal_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s),
               (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (ticket_a, "EURUSD", "BUY", "0.10", "1.1400", entry_time_young, "OPEN", "TestHoldA", signal_id,
         ticket_b, "GBPUSD", "SELL", "0.10", "1.3400", entry_time_young, "OPEN", "TestHoldB", signal_id)
    )
    conn.commit()
    
    # Call exit manager with a Z-score that triggers TP exit (e.g. z = 5.0)
    # This should trigger the exit but defer it because of the 35s hold limit
    main.manage_spread_positions("EURUSD", "GBPUSD", z_score=5.0)
    
    print(f"Closed tickets during Test 1: {closed_tickets}")
    if ticket_a not in closed_tickets and ticket_b not in closed_tickets:
        print("PASS: Exit deferred correctly for test tickets!")
    else:
        print("FAIL: Exit was NOT deferred for test tickets!")
        # Clean up before exit
        cur.execute("DELETE FROM trades WHERE comment LIKE 'TestHold%'")
        cur.execute("DELETE FROM signals WHERE id = 99999")
        conn.commit()
        sys.exit(1)
        
    # Clean up Test Case 1 trades
    cur.execute("DELETE FROM trades WHERE comment LIKE 'TestHold%'")
    conn.commit()
    
    # Test Case 2: Trade is 40 seconds old (greater than 35s limit) -> Exit MUST execute
    print("\n--- Test Case 2: 40 Seconds Old Trade (Greater than 35s) ---")
    closed_tickets.clear()
    
    entry_time_old = now - datetime.timedelta(seconds=40)
    
    cur.execute(
        """
        INSERT INTO trades (ticket, symbol, order_type, lots, entry_price, entry_time, status, comment, signal_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s),
               (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (ticket_a, "EURUSD", "BUY", "0.10", "1.1400", entry_time_old, "OPEN", "TestHoldA", signal_id,
         ticket_b, "GBPUSD", "SELL", "0.10", "1.3400", entry_time_old, "OPEN", "TestHoldB", signal_id)
    )
    conn.commit()
    
    # Call exit manager with a Z-score that triggers TP exit (z = 5.0)
    # This should trigger and immediately execute the exit
    main.manage_spread_positions("EURUSD", "GBPUSD", z_score=5.0)
    
    print(f"Closed tickets during Test 2: {closed_tickets}")
    if ticket_a in closed_tickets and ticket_b in closed_tickets:
        print("PASS: Exit executed correctly for test tickets!")
    else:
        print("FAIL: Exit did not execute for test tickets!")
        # Clean up before exit
        cur.execute("DELETE FROM trades WHERE comment LIKE 'TestHold%'")
        cur.execute("DELETE FROM signals WHERE id = 99999")
        conn.commit()
        sys.exit(1)
        
    # Clean up all mock trades and signals at the end
    cur.execute("DELETE FROM trades WHERE comment LIKE 'TestHold%'")
    cur.execute("DELETE FROM signals WHERE id = 99999")
    conn.commit()
    
    cur.close()
    conn.close()
    print("\n=== All Hold Time Safety Tests Passed Successfully! ===")

if __name__ == "__main__":
    run_test()
