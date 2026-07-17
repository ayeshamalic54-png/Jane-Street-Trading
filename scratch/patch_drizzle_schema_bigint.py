import os

db_schema_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "lib", "db", "src", "index.ts")

with open(db_schema_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace mt5Login: integer("mt5_login") with bigint
old_line = '  mt5Login: integer("mt5_login").default(0),'
new_line = '  mt5Login: bigint("mt5_login", { mode: "number" }).default(0),'

if old_line in content:
    content = content.replace(old_line, new_line)
    print("Drizzle schema updated: mt5Login changed to bigint.")
else:
    print("old_line target not found in Drizzle schema!")

with open(db_schema_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
