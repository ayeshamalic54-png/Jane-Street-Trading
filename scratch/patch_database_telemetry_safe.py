import os

db_path = os.path.join(os.path.dirname(__file__), "..", "database.py")

with open(db_path, "r", encoding="utf-8") as f:
    content = f.read()

# Define the new robust update_bot_state function that automatically tracks and calculates overall drawdown and gain
new_fn = """def update_bot_state(active_pair, system_status, equity, drawdown_percent,
                     floating_profit, z_score, hedge_ratio, obi_a, obi_b,
                     trades_today, sl_pips=10.0):
    \"\"\"
    Upserts live bot telemetry into bot_state table.
    Tracks overall drawdown, max equity peak, and resets metrics if a new MT5 account is attached.
    \"\"\"
    query = \"\"\"
        INSERT INTO bot_state (
            id, active_pair, system_status, equity, drawdown_percent,
            floating_profit, z_score, hedge_ratio, obi_a, obi_b,
            trades_today, sl_pips, last_heartbeat, updated_at,
            initial_balance, overall_drawdown, max_equity_peak, mt5_login
        )
        VALUES (
            1, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s, %s, %s, %s
        )
        ON CONFLICT (id) DO UPDATE SET
            system_status      = EXCLUDED.system_status,
            equity             = EXCLUDED.equity,
            drawdown_percent   = EXCLUDED.drawdown_percent,
            floating_profit    = EXCLUDED.floating_profit,
            z_score            = EXCLUDED.z_score,
            hedge_ratio        = EXCLUDED.hedge_ratio,
            obi_a              = EXCLUDED.obi_a,
            obi_b              = EXCLUDED.obi_b,
            trades_today       = EXCLUDED.trades_today,
            initial_balance    = EXCLUDED.initial_balance,
            overall_drawdown   = EXCLUDED.overall_drawdown,
            max_equity_peak    = EXCLUDED.max_equity_peak,
            mt5_login          = EXCLUDED.mt5_login,
            last_heartbeat     = CURRENT_TIMESTAMP,
            updated_at         = CURRENT_TIMESTAMP
    \"\"\"
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # 1. Fetch current login info from MT5
        import MetaTrader5 as mt5
        mt5_login_val = 0
        terminal_active = False
        try:
            acc_info = mt5.account_info()
            if acc_info:
                mt5_login_val = int(acc_info.login)
                terminal_active = True
        except Exception:
            pass

        # 2. Query current saved overall metrics from DB
        cur.execute("SELECT initial_balance, max_equity_peak, mt5_login FROM bot_state WHERE id = 1")
        row = cur.fetchone()

        initial_balance_val = float(equity)
        max_equity_peak_val = float(equity)
        saved_login = 0

        if row:
            initial_balance_val = float(row[0] or equity)
            max_equity_peak_val = float(row[1] or equity)
            saved_login = int(row[2] or 0)

        # 3. Detect if a new account has been attached
        if terminal_active and mt5_login_val > 0 and mt5_login_val != saved_login:
            # Sync to the new account's metrics!
            print(f"New MT5 account detected: {mt5_login_val}. Resetting initial_balance and max_equity_peak to current equity: ${equity:.2f}")
            initial_balance_val = float(equity)
            max_equity_peak_val = float(equity)
            saved_login = mt5_login_val

        # 4. Update peak equity if exceeded
        if float(equity) > max_equity_peak_val:
            max_equity_peak_val = float(equity)

        # 5. Calculate overall drawdown from peak
        overall_drawdown_val = 0.00
        if max_equity_peak_val > 0.0:
            overall_drawdown_val = ((max_equity_peak_val - float(equity)) / max_equity_peak_val) * 100.0
            overall_drawdown_val = max(0.00, overall_drawdown_val)

        cur.execute(query, (
            str(active_pair), str(system_status),
            float(equity), float(drawdown_percent),
            float(floating_profit), float(z_score),
            float(hedge_ratio), float(obi_a), float(obi_b),
            int(trades_today), float(sl_pips),
            float(initial_balance_val), float(overall_drawdown_val),
            float(max_equity_peak_val), int(saved_login)
        ))
        conn.commit()
        cur.close()
    except Exception as e:
        print(f"Error updating bot_state: {e}")
    finally:
        if conn:
            conn.close()"""

old_fn_start = "def update_bot_state("
next_def = "def get_auto_execute"

start_idx = content.find(old_fn_start)
end_idx = content.find(next_def)

if start_idx != -1 and end_idx != -1:
    content = content[:start_idx] + new_fn + "\n\n" + content[end_idx:]
    print("database.py updated cleanly and non-destructively.")
else:
    print("Could not locate update_bot_state function bounds in database.py!")

with open(db_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
