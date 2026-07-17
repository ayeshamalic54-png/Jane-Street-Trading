import os

config_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "trading-dashboard", "src", "pages", "config.tsx")

with open(config_path, "r", encoding="utf-8") as f:
    content = f.read()

# Locate the hardcoded bottom preview block and replace it with dynamic form.watch values
old_preview = """                  <div className="pt-2 border-t border-border space-y-2 text-xs text-muted-foreground">
                    <div className="flex justify-between"><span>Z-Score Entry</span><span className="font-mono text-foreground">±{config.zEntryThreshold.toFixed(2)}σ</span></div>
                    <div className="flex justify-between"><span>Max Daily Trades</span><span className="font-mono text-foreground">3</span></div>
                    <div className="flex justify-between"><span>Risk Per Trade</span><span className="font-mono text-foreground">1% equity</span></div>
                    <div className="flex justify-between"><span>Execution Model</span><span className="font-mono text-foreground">3-Part TP ladder</span></div>
                  </div>"""

new_preview = """                  <div className="pt-2 border-t border-border space-y-2 text-xs text-muted-foreground">
                    <div className="flex justify-between"><span>Z-Score Entry</span><span className="font-mono text-foreground">±{Number(form.watch("zEntryThreshold") ?? 2.0).toFixed(2)}σ</span></div>
                    <div className="flex justify-between"><span>Max Daily Trades</span><span className="font-mono text-foreground">{form.watch("maxDailyTrades") ?? 3}</span></div>
                    <div className="flex justify-between"><span>Risk Per Trade</span><span className="font-mono text-foreground">1% equity</span></div>
                    <div className="flex justify-between"><span>Execution Model</span><span className="font-mono text-foreground">3-Part TP ladder</span></div>
                  </div>"""

if old_preview in content:
    content = content.replace(old_preview, new_preview)
    print("config.tsx bottom preview section updated with dynamic form bindings.")
else:
    print("old_preview target not found in config.tsx!")

with open(config_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
