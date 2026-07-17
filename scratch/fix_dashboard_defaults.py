import os

dash_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "trading-dashboard", "src", "pages", "dashboard.tsx")

with open(dash_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace destructuring block with clean defaults to satisfy strict null/undefined checks
old_block = """    botOnline,
    autoExecute,
    initialBalance,
    overallDrawdown,
    maxEquityPeak,
    mt5Login,
  } = dashboard;"""

new_block = """    botOnline,
    autoExecute,
    initialBalance = 100000.00,
    overallDrawdown = 0.00,
    maxEquityPeak = 0.00,
    mt5Login = 0,
  } = dashboard;"""

if old_block in content:
    content = content.replace(old_block, new_block)
    print("dashboard.tsx destructuring defaults updated.")
else:
    print("old_block target not found in dashboard.tsx!")

with open(dash_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
