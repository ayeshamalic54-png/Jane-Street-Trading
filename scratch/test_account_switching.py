import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from database import get_connection, reset_database_metrics_for_new_account, update_bot_state

def run_test():
    print("=====================================================================")
    print(" STARTING SIMULATION: Testing Account Switch Persistence")
    print("=====================================================================")

    conn = get_connection()
    cur = conn.cursor()

    # 1. Clean test entries if they exist
    cur.execute("DELETE FROM account_states WHERE mt5_login IN (111111, 222222)")
    conn.commit()

    # --- SIMULATION STEP 1: Connect Account 111111 with $10,000 Equity ---
    print("\n--- STEP 1: Switching to Account 111111 (Equity: $10,000.00) ---")
    reset_database_metrics_for_new_account(111111, 10000.00)
    
    # Verify values in database for bot_state
    cur.execute("SELECT mt5_login, initial_balance, max_equity_peak, overall_drawdown FROM bot_state WHERE id = 1")
    row = cur.fetchone()
    print(f"Active in DB -> Login: {row[0]}, Start Balance: ${row[1]:.2f}, Peak: ${row[2]:.2f}, Overall DD: {row[3]:.2f}%")
    assert row[0] == 111111
    assert float(row[1]) == 10000.00
    assert float(row[2]) == 10000.00
    assert float(row[3]) == 0.00

    # --- SIMULATION STEP 2: Connect Account 222222 with $5,000 Equity ---
    print("\n--- STEP 2: Switching to Account 222222 (Equity: $5,000.00) ---")
    reset_database_metrics_for_new_account(222222, 5000.00)
    
    # Verify values in database
    cur.execute("SELECT mt5_login, initial_balance, max_equity_peak, overall_drawdown FROM bot_state WHERE id = 1")
    row = cur.fetchone()
    print(f"Active in DB -> Login: {row[0]}, Start Balance: ${row[1]:.2f}, Peak: ${row[2]:.2f}, Overall DD: {row[3]:.2f}%")
    assert row[0] == 222222
    assert float(row[1]) == 5000.00
    assert float(row[2]) == 5000.00
    assert float(row[3]) == 0.00

    # --- SIMULATION STEP 3: Switch back to Account 111111 (Current Equity: $9,800.00, Peak was $10,000) ---
    print("\n--- STEP 3: Switching BACK to Account 111111 (Equity dropped to $9,800.00) ---")
    reset_database_metrics_for_new_account(111111, 9800.00)
    
    # Verify saved state was restored instead of resetting initial_balance to $9,800.00
    cur.execute("SELECT mt5_login, initial_balance, max_equity_peak, overall_drawdown FROM bot_state WHERE id = 1")
    row = cur.fetchone()
    print(f"Active in DB -> Login: {row[0]}, Start Balance: ${row[1]:.2f} (Restored!), Peak: ${row[2]:.2f} (Restored!)")
    
    # Calculate drawdown using the restored peak of $10,000
    restored_start = float(row[1])
    restored_peak = float(row[2])
    restored_dd = ((restored_peak - 9800.00) / restored_peak) * 100.0
    print(f"Calculated Drawdown from Restored Peak: {restored_dd:.2f}%")
    
    assert row[0] == 111111
    assert restored_start == 10000.00
    assert restored_peak == 10000.00
    assert abs(restored_dd - 2.00) < 0.01

    # Cleanup test entries
    cur.execute("DELETE FROM account_states WHERE mt5_login IN (111111, 222222)")
    conn.commit()
    cur.close()
    conn.close()
    
    print("\n=====================================================================")
    print(" VERIFICATION SUCCESSFUL: Account metrics switch is 100% safe & robust!")
    print("=====================================================================")

if __name__ == "__main__":
    run_test()
