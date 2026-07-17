import os

db_index_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "lib", "db", "src", "index.ts")

with open(db_index_path, "r", encoding="utf-8") as f:
    content = f.read()

target = '  updatedAt: timestamp("updated_at").defaultNow(),'
replacement = '  updatedAt: timestamp("updated_at").defaultNow(),\n  maxTrades: integer("max_trades").default(3),'

if target in content and 'maxTrades' not in content:
    content = content.replace(target, replacement)
    print("maxTrades added to lib/db/src/index.ts.")
else:
    print("Target not found or maxTrades already exists in index.ts!")

with open(db_index_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
