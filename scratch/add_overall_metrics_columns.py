import os

db_index_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "lib", "db", "src", "index.ts")

with open(db_index_path, "r", encoding="utf-8") as f:
    content = f.read()

# Add initialBalance, overallDrawdown, maxEquityPeak, mt5Login columns to botStateTable schema
old_definition = '  adminPassword: varchar("admin_password", { length: 100 }).default("AWais1133@"),'
new_definition = """  adminPassword: varchar("admin_password", { length: 100 }).default("AWais1133@"),
  initialBalance: numeric("initial_balance", { precision: 15, scale: 2 }).default("100000.00"),
  overallDrawdown: numeric("overall_drawdown", { precision: 5, scale: 2 }).default("0.00"),
  maxEquityPeak: numeric("max_equity_peak", { precision: 15, scale: 2 }).default("0.00"),
  mt5Login: integer("mt5_login").default(0),"""

if old_definition in content:
    content = content.replace(old_definition, new_definition)
    print("overall metrics columns added to bot_state schema.")
else:
    print("old_definition target not found in index.ts!")

with open(db_index_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
