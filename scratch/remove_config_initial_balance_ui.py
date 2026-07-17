import os

config_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "trading-dashboard", "src", "pages", "config.tsx")

with open(config_path, "r", encoding="utf-8") as f:
    content = f.read()

# Target FormField block for initialBalance
target_block = """                  <FormField
                    control={form.control}
                    name="initialBalance"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Initial Account Balance ($)</FormLabel>
                        <FormControl>
                          <Input type="number" step="0.01" min="100" {...field} className="font-mono border-border bg-background" />
                        </FormControl>
                        <FormDescription className="text-xs">
                          Starting balance of the attached prop firm or live trading account (e.g., 100000). Overall gains and drawdowns will start fresh from this balance.
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />"""

if target_block in content:
    content = content.replace(target_block, "")
    print("initialBalance FormField removed from config.tsx UI.")
else:
    # Try the old step-less version in case build was still running
    old_target_block = """                  <FormField
                    control={form.control}
                    name="initialBalance"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Initial Account Balance ($)</FormLabel>
                        <FormControl>
                          <Input type="number" min="100" {...field} className="font-mono border-border bg-background" />
                        </FormControl>
                        <FormDescription className="text-xs">
                          Starting balance of the attached prop firm or live trading account (e.g., 100000). Overall gains and drawdowns will start fresh from this balance.
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />"""
    if old_target_block in content:
        content = content.replace(old_target_block, "")
        print("initialBalance FormField (step-less) removed from config.tsx UI.")
    else:
        print("initialBalance FormField not found in config.tsx!")

with open(config_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
