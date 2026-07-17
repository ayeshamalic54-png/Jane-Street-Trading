import os

app_tsx_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "trading-dashboard", "src", "App.tsx")

with open(app_tsx_path, "r", encoding="utf-8") as f:
    content = f.read()

# Add import statement
old_import = 'import NotFound from "@/pages/not-found";'
new_import = """import NotFound from "@/pages/not-found";
import Backup from "@/pages/backup";"""

content = content.replace(old_import, new_import)

# Add Route statement
old_route = '<Route path="/backtest" component={Backtest} />'
new_route = """<Route path="/backtest" component={Backtest} />
        <Route path="/backup" component={Backup} />"""

content = content.replace(old_route, new_route)

with open(app_tsx_path, "w", encoding="utf-8") as f:
    f.write(content)
print("App.tsx updated to register the Backup route.")
