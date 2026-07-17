import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace all occurrences of risk_pct=15.0 with risk_pct=2.0
target = "risk_pct=15.0"
replacement = "risk_pct=2.0"

if target in content:
    content = content.replace(target, replacement)
    print("Risk percentage reduced to 2.0%.")
else:
    print("Target not found!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
