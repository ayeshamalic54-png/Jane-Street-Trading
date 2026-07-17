import os

rs_path = os.path.join(os.path.dirname(__file__), "..", "risk_safeguards.py")

with open(rs_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """    if daily_loss_percent >= MAX_DAILY_LOSS_PERCENT:
        logger.critical(f"DAILY LIMIT BREACHED: Drawdown is {daily_loss_percent:.2f}% (Limit: {MAX_DAILY_LOSS_PERCENT}%)")
        return True, daily_loss_percent"""

replacement = """    if daily_loss_percent >= MAX_DAILY_LOSS_PERCENT:
        is_crypto_vps = os.getenv("OVERRIDE_CRYPTO_ENABLED") == "True"
        if not is_crypto_vps:
            logger.critical(f"DAILY LIMIT BREACHED: Drawdown is {daily_loss_percent:.2f}% (Limit: {MAX_DAILY_LOSS_PERCENT}%)")
        else:
            logger.info(f"Daily drawdown is {daily_loss_percent:.2f}% (Limit: {MAX_DAILY_LOSS_PERCENT}%, Bypassed on Crypto VPS)")
        return True, daily_loss_percent"""

if target in content:
    content = content.replace(target, replacement)
    print("Replacement successful.")
else:
    print("Target not found!")

with open(rs_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
