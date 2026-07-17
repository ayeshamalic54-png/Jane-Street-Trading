import os

risk_path = os.path.join(os.path.dirname(__file__), "..", "risk_safeguards.py")

with open(risk_path, "r", encoding="utf-8") as f:
    content = f.read()

target_get = """def get_or_create_daily_start_equity(current_equity):
    \"\"\"
    Retrieves the starting equity for the current day from a local JSON file.
    If it doesn't exist or date mismatches, initializes it with the current equity.
    \"\"\"
    today_str = datetime.date.today().isoformat()
    start_equity = current_equity
    
    # Try reading from local file first
    if os.path.exists(DAILY_START_EQUITY_FILE):
        try:
            with open(DAILY_START_EQUITY_FILE, "r") as f:
                data = json.load(f)
                if data.get("date") == today_str:
                    start_equity = float(data.get("start_equity", current_equity))
                    
                    # Smart Reset: If no trades have been taken today, OR if equity changed by > 15%, reset it
                    trades_today = get_trades_count_today()
                    is_huge_change = start_equity > 0 and (abs(start_equity - current_equity) / start_equity > 0.15)
                    if (trades_today == 0 or is_huge_change) and abs(start_equity - current_equity) > 0.01:
                        start_equity = current_equity
                        with open(DAILY_START_EQUITY_FILE, "w") as wf:
                            json.dump({"date": today_str, "start_equity": start_equity}, wf)
                        logger.info(f"Daily start equity reset locally to: ${start_equity:.2f}")
                    return start_equity
        except Exception as e:
            logger.error(f"Error reading daily start equity file: {e}")
            
    # If file doesn't exist or date mismatch, create new daily record locally
    try:
        with open(DAILY_START_EQUITY_FILE, "w") as f:
            json.dump({"date": today_str, "start_equity": current_equity}, f)
        logger.info(f"Initialized new daily trading session locally. Starting equity: ${current_equity:.2f}")
    except Exception as e:
        logger.error(f"Error writing daily start equity file: {e}")
        
    return current_equity"""

replacement_get = """def get_or_create_daily_start_equity(current_equity, account_id=None):
    \"\"\"
    Retrieves the starting equity for the current day from a local JSON file.
    If it doesn't exist, date mismatches, or account_id mismatches, initializes it with the current equity.
    \"\"\"
    today_str = datetime.date.today().isoformat()
    start_equity = current_equity
    
    # Try reading from local file first
    if os.path.exists(DAILY_START_EQUITY_FILE):
        try:
            with open(DAILY_START_EQUITY_FILE, "r") as f:
                data = json.load(f)
                file_date = data.get("date")
                file_acc_id = data.get("account_id")
                
                # Reset if date mismatches OR account_id mismatches (if account_id is provided)
                if file_date == today_str and (account_id is None or file_acc_id == account_id):
                    start_equity = float(data.get("start_equity", current_equity))
                    
                    # Smart Reset: If no trades have been taken today, OR if equity changed by > 15%, reset it
                    trades_today = get_trades_count_today()
                    is_huge_change = start_equity > 0 and (abs(start_equity - current_equity) / start_equity > 0.15)
                    if (trades_today == 0 or is_huge_change) and abs(start_equity - current_equity) > 0.01:
                        start_equity = current_equity
                        with open(DAILY_START_EQUITY_FILE, "w") as wf:
                            json.dump({"date": today_str, "start_equity": start_equity, "account_id": account_id}, wf)
                        logger.info(f"Daily start equity reset locally to: ${start_equity:.2f}")
                    return start_equity
        except Exception as e:
            logger.error(f"Error reading daily start equity file: {e}")
            
    # If file doesn't exist or date/account mismatch, create new daily record locally
    try:
        with open(DAILY_START_EQUITY_FILE, "w") as f:
            json.dump({"date": today_str, "start_equity": current_equity, "account_id": account_id}, f)
        logger.info(f"Initialized new daily trading session locally. Starting equity: ${current_equity:.2f} for account {account_id}")
    except Exception as e:
        logger.error(f"Error writing daily start equity file: {e}")
        
    return current_equity"""

target_check = """def check_drawdown_limit(current_equity):
    \"\"\"
    Checks if the daily drawdown limit has been breached.
    Calculates drawdown strictly based on the local platform's equity.
    Returns: (is_breached, daily_loss_percent)
    \"\"\"
    global _last_metrics_update_time
    
    start_equity = get_or_create_daily_start_equity(current_equity)"""

replacement_check = """def check_drawdown_limit(current_equity, account_id=None):
    \"\"\"
    Checks if the daily drawdown limit has been breached.
    Calculates drawdown strictly based on the local platform's equity.
    Returns: (is_breached, daily_loss_percent)
    \"\"\"
    global _last_metrics_update_time
    
    start_equity = get_or_create_daily_start_equity(current_equity, account_id=account_id)"""

if target_get in content:
    content = content.replace(target_get, replacement_get)
    print("get_or_create_daily_start_equity replacement successful.")
else:
    print("get_or_create_daily_start_equity target not found!")

if target_check in content:
    content = content.replace(target_check, replacement_check)
    print("check_drawdown_limit replacement successful.")
else:
    print("check_drawdown_limit target not found!")

with open(risk_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
