import os

rs_path = os.path.join(os.path.dirname(__file__), "..", "risk_safeguards.py")

with open(rs_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """def get_or_create_daily_start_equity(current_equity, account_id=None):
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

replacement = """def get_or_create_daily_start_equity(current_equity, account_id=None):
    \"\"\"
    Retrieves the starting equity for the current day from a local JSON file.
    If it doesn't exist, date mismatches, or account_id mismatches, initializes it with the current equity.
    \"\"\"
    today_str = datetime.date.today().isoformat()
    start_equity = current_equity
    
    # Use account-specific filename to prevent collision between Forex and Crypto bots
    suffix = f"_{account_id}" if account_id is not None else ""
    filename = f"daily_start_equity{suffix}.json"
    
    # Try reading from local file first
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
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
                        with open(filename, "w") as wf:
                            json.dump({"date": today_str, "start_equity": start_equity, "account_id": account_id}, wf)
                        logger.info(f"Daily start equity reset locally to: ${start_equity:.2f} for account {account_id}")
                    return start_equity
        except Exception as e:
            logger.error(f"Error reading daily start equity file: {e}")
            
    # If file doesn't exist or date/account mismatch, create new daily record locally
    try:
        with open(filename, "w") as f:
            json.dump({"date": today_str, "start_equity": current_equity, "account_id": account_id}, f)
        logger.info(f"Initialized new daily trading session locally. Starting equity: ${current_equity:.2f} for account {account_id}")
    except Exception as e:
        logger.error(f"Error writing daily start equity file: {e}")
        
    return current_equity"""

if target in content:
    content = content.replace(target, replacement)
    print("Replacement successful.")
else:
    print("Target not found!")

with open(rs_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
