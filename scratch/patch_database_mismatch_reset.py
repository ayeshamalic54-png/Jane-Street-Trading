import os

db_path = os.path.join(os.path.dirname(__file__), "..", "database.py")

with open(db_path, "r", encoding="utf-8") as f:
    content = f.read()

# Target block to replace in update_bot_state function
old_block = """        # 3. Detect if a new account has been attached
        if terminal_active and mt5_login_val > 0 and mt5_login_val != saved_login:
            # Sync to the new account's metrics!
            print(f"New MT5 account detected: {mt5_login_val}. Resetting initial_balance and max_equity_peak to current equity: ${equity:.2f}")
            initial_balance_val = float(equity)
            max_equity_peak_val = float(equity)
            saved_login = mt5_login_val"""

new_block = """        # 3. Detect if a new account has been attached OR if there is a mismatch on 0 active trades today
        trades_today_val = int(trades_today)
        # Check if there are active positions in the database
        cur.execute("SELECT COUNT(*) FROM trades WHERE status = 'OPEN'")
        open_trades_count = cur.fetchone()[0] or 0
        has_positions = (open_trades_count > 0) or (float(floating_profit) != 0.0)

        login_changed = (mt5_login_val > 0 and mt5_login_val != saved_login)
        mismatch_reset = (mt5_login_val > 0 and mt5_login_val == saved_login and trades_today_val == 0 and not has_positions and abs(initial_balance_val - float(equity)) > 0.01)

        if terminal_active and (login_changed or mismatch_reset):
            print(f"Syncing account metrics: Resetting initial_balance and max_equity_peak to current equity: ${equity:.2f} (login_changed={login_changed}, mismatch_reset={mismatch_reset})")
            initial_balance_val = float(equity)
            max_equity_peak_val = float(equity)
            if login_changed:
                saved_login = mt5_login_val"""

if old_block in content:
    content = content.replace(old_block, new_block)
    print("update_bot_state mismatch_reset logic successfully patched.")
else:
    print("old_block target not found in database.py!")

with open(db_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
