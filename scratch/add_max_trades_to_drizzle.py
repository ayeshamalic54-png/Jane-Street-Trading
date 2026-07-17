import os

schema_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "lib", "db", "src", "schema", "trading.ts")

with open(schema_path, "r", encoding="utf-8") as f:
    content = f.read()

target = '  updatedAt: timestamp("updated_at").defaultNow(),'
replacement = '  updatedAt: timestamp("updated_at").defaultNow(),\n  maxTrades: integer("max_trades").default(3),'

if target in content and 'maxTrades' not in content:
    content = content.replace(target, replacement)
    print("maxTrades column added to Drizzle schema.")
else:
    print("maxTrades target not found or already exists!")

with open(schema_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Schema updated.")
