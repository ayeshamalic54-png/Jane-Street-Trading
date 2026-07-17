import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """            # Calculate daily drawdown using the correct equity (only if equity > 0.0)
            if current_equity > 0.0:
                is_limit_breached, daily_loss_p = check_drawdown_limit(current_equity)
                if is_crypto_vps:
                    is_limit_breached = False  # Bypass daily drawdown limit check for Crypto VPS
            else:
                is_limit_breached, daily_loss_p = False, 0.0"""

replacement = """            # Calculate daily drawdown using the correct equity (only if equity > 0.0)
            if current_equity > 0.0:
                acc_id = acc_info.login if acc_info else ("binance" if is_crypto_vps else None)
                is_limit_breached, daily_loss_p = check_drawdown_limit(current_equity, account_id=acc_id)
                if is_crypto_vps:
                    is_limit_breached = False  # Bypass daily drawdown limit check for Crypto VPS
            else:
                is_limit_breached, daily_loss_p = False, 0.0"""

if target in content:
    content = content.replace(target, replacement)
    print("Replacement successful.")
else:
    print("Target not found!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
