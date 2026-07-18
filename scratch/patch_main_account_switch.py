import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

# Target for initializing active_login_id
old_init = """    logger.info("Quantitative core pipeline active.")
    win_rate_loop_counter = 0
    SMC_ZONES_CACHE = {}
    smc_counter_cache = {}

    while True:"""

new_init = """    logger.info("Quantitative core pipeline active.")
    win_rate_loop_counter = 0
    SMC_ZONES_CACHE = {}
    smc_counter_cache = {}

    active_login_id = None
    try:
        from database import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT mt5_login FROM bot_state WHERE id = 1")
        row = cur.fetchone()
        if row and row[0]:
            active_login_id = int(row[0])
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error loading initial mt5_login from database: {e}")

    while True:"""

if old_init in content:
    content = content.replace(old_init, new_init)
    print("active_login_id initialization added successfully.")
else:
    print("old_init target not found in main.py!")

# Target for checking account switch in the loop
old_loop_check = """            acc_info = mt5.account_info()
            if acc_info is None:
                time.sleep(5)
                continue"""

new_loop_check = """            acc_info = mt5.account_info()
            if acc_info is None:
                time.sleep(5)
                continue

            current_login = int(acc_info.login)
            if active_login_id is not None and active_login_id != current_login:
                logger.info(f"Account switch detected: {active_login_id} -> {current_login}. Resetting metrics database records.")
                from database import reset_database_metrics_for_new_account
                reset_database_metrics_for_new_account(current_login, acc_info.equity)
            active_login_id = current_login"""

if old_loop_check in content:
    content = content.replace(old_loop_check, new_loop_check)
    print("active_login_id loop check added successfully.")
else:
    print("old_loop_check target not found in main.py!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
