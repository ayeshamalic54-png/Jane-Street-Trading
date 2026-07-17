import os

routes_index_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "api-server", "src", "routes", "index.ts")

with open(routes_index_path, "r", encoding="utf-8") as f:
    content = f.read()

# Add the router imports
old_imports = 'import backtestRouter from "./backtest";'
new_imports = """import backtestRouter from "./backtest";
import backupRouter from "./backup";
import authRouter from "./auth";"""

content = content.replace(old_imports, new_imports)

# Add the router usage calls
old_uses = 'router.use(backtestRouter);'
new_uses = """router.use(backtestRouter);
router.use(backupRouter);
router.use(authRouter);"""

content = content.replace(old_uses, new_uses)

with open(routes_index_path, "w", encoding="utf-8") as f:
    f.write(content)
print("index.ts updated with backup and auth routes.")
