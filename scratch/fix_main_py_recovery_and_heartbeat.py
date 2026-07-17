import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Heartbeat update
target_hb = 'cur.execute("UPDATE bot_state SET last_heartbeat = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = 1")'
replacement_hb = 'cur.execute("UPDATE bot_state SET last_heartbeat = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id IN (1, 2)")'

if target_hb in content:
    content = content.replace(target_hb, replacement_hb)
    print("Heartbeat replacement successful.")
else:
    print("Heartbeat target not found!")

# 2. Active symbol recovery
target_rec = """            S_A = GLOBAL_CONFIG["SYMBOL_A"]
            S_B = GLOBAL_CONFIG["SYMBOL_B"]
            current_pair_context = f"{S_A}/{S_B}"""

replacement_rec = """            S_A = GLOBAL_CONFIG["SYMBOL_A"]
            S_B = GLOBAL_CONFIG["SYMBOL_B"]
            current_pair_context = f"{S_A}/{S_B}"
            
            # ── ACTIVE SYMBOL RECOVERY ──
            try:
                db_conn_rec = get_connection()
                db_cur_rec = db_conn_rec.cursor()
                db_cur_rec.execute(
                    "SELECT signal_id FROM trades WHERE status = 'OPEN' AND signal_id IS NOT NULL ORDER BY entry_time DESC LIMIT 1"
                )
                open_sig_row = db_cur_rec.fetchone()
                if open_sig_row:
                    active_sig_id = int(open_sig_row[0])
                    db_cur_rec.execute(
                        "SELECT symbol_a, symbol_b FROM signals WHERE id = %s", (active_sig_id,)
                    )
                    sig_row = db_cur_rec.fetchone()
                    if sig_row:
                        rec_a, rec_b = sig_row[0], sig_row[1]
                        if S_A.upper() != rec_a.upper() or S_B.upper() != rec_b.upper():
                            logger.info(f"[SYMBOL RECOVERY] Active open position detected for {rec_a}/{rec_b}. Overriding active pair context.")
                            S_A = rec_a
                            S_B = rec_b
                            current_pair_context = f"{S_A}/{S_B}"
                db_cur_rec.close()
                db_conn_rec.close()
            except Exception as rec_err:
                logger.error(f"Error recovering active symbols: {rec_err}")"""

if target_rec in content:
    content = content.replace(target_rec, replacement_rec)
    print("Symbol recovery replacement successful.")
else:
    print("Symbol recovery target not found!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
