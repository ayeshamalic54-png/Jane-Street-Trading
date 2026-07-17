import os

dash_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "trading-dashboard", "src", "pages", "dashboard.tsx")

with open(dash_path, "r", encoding="utf-8") as f:
    content = f.read()

# Define isReadOnly inside Dashboard()
old_init = "  const { toast } = useToast();"
new_init = """  const { toast } = useToast();
  const isReadOnly = localStorage.getItem("wasee_role") === "user";"""

content = content.replace(old_init, new_init)

# Update Close All button disabled state
old_close_all_disabled = 'disabled={executeTrade.isPending || !botOnline}'
new_close_all_disabled = 'disabled={executeTrade.isPending || !botOnline || isReadOnly}'

# Note: since there are multiple identical "disabled={executeTrade.isPending || !botOnline}" in the code,
# replacing all occurrences will automatically patch:
# - main CLOSE ALL button
# - manual ONE-CLICK EXECUTE button
# - manual BUY button
# - manual SELL button
# - row-level Emergency Close button
# This is incredibly elegant and covers all target controls in a single replace!
content = content.replace(old_close_all_disabled, new_close_all_disabled)

with open(dash_path, "w", encoding="utf-8") as f:
    f.write(content)
print("dashboard.tsx updated with isReadOnly disabled states.")
