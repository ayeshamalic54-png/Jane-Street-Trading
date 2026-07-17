import os

config_route_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "api-server", "src", "routes", "config.ts")
dashboard_route_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "api-server", "src", "routes", "dashboard.ts")

# 1. Update config.ts
with open(config_route_path, "r", encoding="utf-8") as f:
    config_content = f.read()

# Make all res. calls have "return "
config_content = config_content.replace("    res.json({", "    return res.json({")
config_content = config_content.replace('      res.status(400).json({ error: "Invalid request body" });', '      return res.status(400).json({ error: "Invalid request body" });')
config_content = config_content.replace('      res.status(400).json({ error: "activePair must be SYMBOL_A/SYMBOL_B" });', '      return res.status(400).json({ error: "activePair must be SYMBOL_A/SYMBOL_B" });')
config_content = config_content.replace('    res.json({\n      activePair: updatedPair,', '    return res.json({\n      activePair: updatedPair,')

with open(config_route_path, "w", encoding="utf-8") as f:
    f.write(config_content)
print("config.ts response returns patched.")

# 2. Update dashboard.ts
with open(dashboard_route_path, "r", encoding="utf-8") as f:
    dash_content = f.read()

dash_content = dash_content.replace("    res.json({\n      systemStatus:", "    return res.json({\n      systemStatus:")

with open(dashboard_route_path, "w", encoding="utf-8") as f:
    f.write(dash_content)
print("dashboard.ts response returns patched.")
