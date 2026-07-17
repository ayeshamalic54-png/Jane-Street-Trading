import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace 31.0 with 35.0 in the hold time check
old_check = "if elapsed < 31.0:"
new_check = "if elapsed < 35.0:"

content = content.replace(old_check, new_check)

# Replace the log message
old_log = 'logger.info(f"Exit deferred for signal_id {sig_id} to satisfy 31s minimum hold time (FundedNext compliance).")'
new_log = 'logger.info(f"Exit deferred for signal_id {sig_id} to satisfy 35s minimum hold time (FundedNext compliance).")'

content = content.replace(old_log, new_log)

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Updated main.py minimum hold time safety to 35 seconds.")
