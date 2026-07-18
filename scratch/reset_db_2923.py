import database
import datetime

conn = database.get_connection()
cur = conn.cursor()

# Reset bot_state
cur.execute("""
    UPDATE bot_state 
    SET initial_balance = 2923.88, 
        equity = 2923.88, 
        max_equity_peak = 2923.88, 
        mt5_login = 0, 
        overall_drawdown = 0.00 
    WHERE id = 1
""")

# Reset daily_metrics for today (2026-07-18)
today = datetime.date(2026, 7, 18)
cur.execute("""
    UPDATE daily_metrics 
    SET start_equity = 2923.88, 
        current_equity = 2923.88, 
        max_drawdown_percent = 0.00 
    WHERE trading_date = %s
""", (today,))

conn.commit()
cur.close()
conn.close()
print("Database successfully reset to 2923.88 balance!")
