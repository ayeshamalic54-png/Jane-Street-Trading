import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

# Locate the drawdown bypass block and remove the demo check to enforce automatic exits on demo challenge accounts
old_block = """            if is_limit_breached:
                if is_demo:
                    logger.info(f"Daily drawdown limit breached ({daily_loss_p:.2f}%), but bypassing because account is DEMO.")
                    is_halted = False
                elif not RISK_LIMITS_ENABLED:
                    logger.info(f"Daily drawdown limit breached ({daily_loss_p:.2f}%), but bypassing because Risk Limits are disabled.")
                    is_halted = False
                else:
                    is_halted = True
            else:
                is_halted = False"""

new_block = """            if is_limit_breached:
                if not RISK_LIMITS_ENABLED:
                    logger.info(f"Daily drawdown limit breached ({daily_loss_p:.2f}%), but bypassing because Risk Limits are disabled.")
                    is_halted = False
                else:
                    is_halted = True
            else:
                is_halted = False"""

if old_block in content:
    content = content.replace(old_block, new_block)
    print("Demo drawdown bypass removed. Safeguards will now always enforce auto-close if enabled.")
else:
    print("old_block not found in main.py!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
