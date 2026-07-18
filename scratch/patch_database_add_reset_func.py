import os

db_path = os.path.join(os.path.dirname(__file__), "..", "database.py")

with open(db_path, "r", encoding="utf-8") as f:
    content = f.read()

reset_func_code = """
def reset_database_metrics_for_new_account(login_id, equity):
    \"\"\"
    Force-updates the database metrics (both bot_state and daily_metrics for today)
    to match the new connected account's starting balance.
    \"\"\"
    import datetime
    today = datetime.date.today()
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # 1. Update bot_state
        cur.execute(\"\"\"
            UPDATE bot_state 
            SET initial_balance = %s, max_equity_peak = %s, mt5_login = %s, equity = %s 
            WHERE id = 1
        \"\"\", (float(equity), float(equity), int(login_id), float(equity)))
        
        # 2. Update or Insert daily_metrics for today
        cur.execute("SELECT 1 FROM daily_metrics WHERE trading_date = %s", (today,))
        if cur.fetchone():
            cur.execute(\"\"\"
                UPDATE daily_metrics 
                SET start_equity = %s, current_equity = %s, max_drawdown_percent = 0.00 
                WHERE trading_date = %s
            \"\"\", (float(equity), float(equity), today))
        else:
            cur.execute(\"\"\"
                INSERT INTO daily_metrics (trading_date, start_equity, current_equity, max_drawdown_percent, trades_today)
                VALUES (%s, %s, %s, 0.0, 0)
            \"\"\", (today, float(equity), float(equity)))
            
        conn.commit()
        cur.close()
        print(f"Successfully reset database metrics for new account {login_id} (Equity: ${equity:.2f})")
    except Exception as e:
        print(f"Error resetting database metrics for new account: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
            
    # Also invalidate the local safeguards caches
    try:
        import risk_safeguards
        risk_safeguards._cached_start_equity = float(equity)
        risk_safeguards._cached_start_equity_date = today
        risk_safeguards._cached_last_login = int(login_id)
    except Exception as ex:
        print(f"Error updating risk_safeguards cache: {ex}")

"""

target = 'if __name__ == "__main__":'
if target in content:
    content = content.replace(target, reset_func_code + target)
    print("reset_database_metrics_for_new_account successfully added to database.py.")
else:
    print("Target not found in database.py!")

with open(db_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
