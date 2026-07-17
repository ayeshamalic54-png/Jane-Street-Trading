import os

backtest_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "trading-dashboard", "src", "pages", "backtest.tsx")

with open(backtest_path, "r", encoding="utf-8") as f:
    content = f.read()

# Define isReadOnly inside Backtest() component
old_init = "  const { toast } = useToast();"
new_init = """  const { toast } = useToast();
  const isReadOnly = localStorage.getItem("wasee_role") === "user";"""

content = content.replace(old_init, new_init)

# Update disabled prop of run button
old_btn = 'disabled={loading}'
new_btn = 'disabled={loading || isReadOnly}'

content = content.replace(old_btn, new_btn)

with open(backtest_path, "w", encoding="utf-8") as f:
    f.write(content)
print("backtest.tsx updated with isReadOnly disabled states.")
