import os

db_index_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "lib", "db", "src", "index.ts")

with open(db_index_path, "r", encoding="utf-8") as f:
    content = f.read()

# Add adminUsername and adminPassword columns to botStateTable schema
old_definition = '  maxTrades: integer("max_trades").default(3),'
new_definition = """  maxTrades: integer("max_trades").default(3),
  adminUsername: varchar("admin_username", { length: 50 }).default("wasee"),
  adminPassword: varchar("admin_password", { length: 100 }).default("AWais1133@"),"""

if old_definition in content:
    content = content.replace(old_definition, new_definition)
    print("admin columns added to bot_state schema.")
else:
    print("old_definition target not found in index.ts!")

with open(db_index_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
