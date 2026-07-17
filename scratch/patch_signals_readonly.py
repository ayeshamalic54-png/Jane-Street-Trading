import os

signals_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "trading-dashboard", "src", "pages", "signals.tsx")

with open(signals_path, "r", encoding="utf-8") as f:
    content = f.read()

# Define isReadOnly inside Signals()
old_init = "  const { toast } = useToast();"
new_init = """  const { toast } = useToast();
  const isReadOnly = localStorage.getItem("wasee_role") === "user";"""

content = content.replace(old_init, new_init)

# Update disabled prop for EXECUTE button
old_btn = """                            size="sm"
                            className="bg-emerald-600 hover:bg-emerald-500 text-white font-mono text-[10px] font-bold h-7 px-2"
                            disabled={executeTrade.isPending}"""

new_btn = """                            size="sm"
                            className="bg-emerald-600 hover:bg-emerald-500 text-white font-mono text-[10px] font-bold h-7 px-2"
                            disabled={executeTrade.isPending || isReadOnly}"""

content = content.replace(old_btn, new_btn)

with open(signals_path, "w", encoding="utf-8") as f:
    f.write(content)
print("signals.tsx updated with isReadOnly checks.")
