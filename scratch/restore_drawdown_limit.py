import os

safeguards_path = os.path.join(os.path.dirname(__file__), "..", "risk_safeguards.py")

with open(safeguards_path, "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("MAX_DAILY_LOSS_PERCENT = 2.8", "MAX_DAILY_LOSS_PERCENT = 4.2")

with open(safeguards_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Restored daily drawdown loss percent to 4.2% in risk_safeguards.py.")
