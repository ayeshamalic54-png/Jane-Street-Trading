import os

dashboard_api_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "api-server", "src", "routes", "dashboard.ts")

with open(dashboard_api_path, "r", encoding="utf-8") as f:
    content = f.read()

target = 'db.select().from(botStateTable).limit(1),'
replacement = 'db.select().from(botStateTable).where(eq(botStateTable.id, 1)).limit(1),'

if target in content:
    content = content.replace(target, replacement)
    print("dashboard.ts query updated to strictly filter by id = 1.")
else:
    print("Target query not found in dashboard.ts!")

with open(dashboard_api_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
