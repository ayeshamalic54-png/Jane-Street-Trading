import os

layout_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "trading-dashboard", "src", "components", "layout.tsx")

with open(layout_path, "r", encoding="utf-8") as f:
    content = f.read()

# Add Database icon import
old_imports = """  Play,
  LogOut,
  Menu,
  X,"""

new_imports = """  Play,
  LogOut,
  Menu,
  X,
  Database,"""

content = content.replace(old_imports, new_imports)

# Add Backup to navItems
old_nav_items = """    { href: "/backtest", label: "Backtesting", icon: Play },
    { href: "/config", label: "Config", icon: Settings },"""

new_nav_items = """    { href: "/backtest", label: "Backtesting", icon: Play },
    { href: "/config", label: "Config", icon: Settings },
    { href: "/backup", label: "Backup", icon: Database },"""

content = content.replace(old_nav_items, new_nav_items)

with open(layout_path, "w", encoding="utf-8") as f:
    f.write(content)
print("layout.tsx updated with Backup sidebar navigation link.")
