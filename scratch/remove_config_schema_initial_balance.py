import os

config_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "trading-dashboard", "src", "pages", "config.tsx")

with open(config_path, "r", encoding="utf-8") as f:
    content = f.read()

# Remove initialBalance from configSchema
content = content.replace("  initialBalance: z.coerce.number().min(100).max(10000000),\n", "")
# Remove initialBalance from defaultValues
content = content.replace("      initialBalance: 100000,\n", "")
# Remove initialBalance from values
content = content.replace("          initialBalance: (config as any).initialBalance ?? 100000,\n", "")

with open(config_path, "w", encoding="utf-8") as f:
    f.write(content)
print("config.tsx cleaned from initialBalance form schema & states.")
