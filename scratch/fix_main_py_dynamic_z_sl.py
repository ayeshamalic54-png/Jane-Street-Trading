import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """        # Check standard Z-score exit conditions if time exit didn't trigger
        if not exit_triggered:
            if is_buy_spread:
                if z_score >= z_ex_val:
                    exit_triggered = True
                    exit_reason = f"Z_TP_REVERSION (z={z_score:.2f} >= {z_ex_val})"
                elif z_score <= -z_sl_val:
                    exit_triggered = True
                    exit_reason = f"Z_STOP_LOSS (z={z_score:.2f} <= {-z_sl_val})"
            else:
                if z_score <= -z_ex_val:
                    exit_triggered = True
                    exit_reason = f"Z_TP_REVERSION (z={z_score:.2f} <= {-z_ex_val})"
                elif z_score >= z_sl_val:
                    exit_triggered = True
                    exit_reason = f"Z_STOP_LOSS (z={z_score:.2f} >= {z_sl_val})"""

replacement = """        # Check standard Z-score exit conditions if time exit didn't trigger
        if not exit_triggered:
            entry_z = 0.0
            try:
                db_conn = get_connection()
                db_cur = db_conn.cursor()
                db_cur.execute("SELECT z_score FROM signals WHERE id = %s", (int(sig_id),))
                row_z = db_cur.fetchone()
                if row_z:
                    entry_z = float(row_z[0])
                db_cur.close()
                db_conn.close()
            except Exception as e_z:
                logger.error(f"Error fetching entry Z-score: {e_z}")

            if is_buy_spread:
                if z_score >= z_ex_val:
                    exit_triggered = True
                    exit_reason = f"Z_TP_REVERSION (z={z_score:.2f} >= {z_ex_val})"
                else:
                    dynamic_z_sl = -max(z_sl_val, abs(entry_z) + 1.0)
                    if z_score <= dynamic_z_sl:
                        exit_triggered = True
                        exit_reason = f"Z_STOP_LOSS (z={z_score:.2f} <= {dynamic_z_sl:.2f}, entry_z={entry_z:.2f})"
            else:
                if z_score <= -z_ex_val:
                    exit_triggered = True
                    exit_reason = f"Z_TP_REVERSION (z={z_score:.2f} <= {-z_ex_val})"
                else:
                    dynamic_z_sl = max(z_sl_val, abs(entry_z) + 1.0)
                    if z_score >= dynamic_z_sl:
                        exit_triggered = True
                        exit_reason = f"Z_STOP_LOSS (z={z_score:.2f} >= {dynamic_z_sl:.2f}, entry_z={entry_z:.2f})\""""

# Let's clean the replacement string to remove the trailing quote that was escaped or wrong
replacement = replacement.rstrip('"')

if target in content:
    content = content.replace(target, replacement)
    print("Replacement successful.")
else:
    print("Target not found!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
