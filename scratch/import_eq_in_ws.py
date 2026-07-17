import os

ws_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "api-server", "src", "lib", "ws.ts")

with open(ws_path, "r", encoding="utf-8") as f:
    content = f.read()

old_import = 'import { desc } from "drizzle-orm";'
new_import = 'import { desc, eq } from "drizzle-orm";'

if old_import in content:
    content = content.replace(old_import, new_import)
    print("eq imported successfully in ws.ts.")
else:
    print("old_import target not found in ws.ts!")

with open(ws_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
