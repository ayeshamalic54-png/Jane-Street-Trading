import os

config_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "trading-dashboard", "src", "pages", "config.tsx")

with open(config_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update configSchema
old_schema = '  defaultLots: z.coerce.number().min(0.001).max(500),'
new_schema = '  defaultLots: z.coerce.number().min(0.001).max(500),\n  maxDailyTrades: z.coerce.number().min(1).max(1000),'

if old_schema in content:
    content = content.replace(old_schema, new_schema)
    print("Schema updated in config.tsx.")
else:
    print("old_schema not found!")

# 2. Update defaultValues
old_defaults = '      defaultLots: 0.01,'
new_defaults = '      defaultLots: 0.01,\n      maxDailyTrades: 3,'

if old_defaults in content:
    content = content.replace(old_defaults, new_defaults)
    print("defaultValues updated in config.tsx.")
else:
    print("old_defaults not found!")

# 3. Update values
old_values = '          defaultLots: (config as any).defaultLots ?? 0.01,'
new_values = '          defaultLots: (config as any).defaultLots ?? 0.01,\n          maxDailyTrades: config.maxDailyTrades,'

if old_values in content:
    content = content.replace(old_values, new_values)
    print("values updated in config.tsx.")
else:
    print("old_values not found!")

# 4. Insert FormField after defaultLots FormField
old_field = """                  <FormField
                    control={form.control}
                    name="defaultLots"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Default Lot Size (Auto-Trade)</FormLabel>
                        <FormControl>
                          <Input type="number" step="0.01" min="0.001" {...field} className="font-mono border-border bg-background" />
                        </FormControl>
                        <FormDescription className="text-xs">
                          Fixed lot size used for all automatic spread trades. (e.g. 0.01 to risk minimum).
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />"""

new_field = """                  <FormField
                    control={form.control}
                    name="defaultLots"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Default Lot Size (Auto-Trade)</FormLabel>
                        <FormControl>
                          <Input type="number" step="0.01" min="0.001" {...field} className="font-mono border-border bg-background" />
                        </FormControl>
                        <FormDescription className="text-xs">
                          Fixed lot size used for all automatic spread trades. (e.g. 0.01 to risk minimum).
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="maxDailyTrades"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Max Daily Trades Limit</FormLabel>
                        <FormControl>
                          <Input type="number" min="1" {...field} className="font-mono border-border bg-background" />
                        </FormControl>
                        <FormDescription className="text-xs">
                          Maximum number of trades the bot can execute per day. (e.g., set to 100 for no daily limit warnings).
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />"""

if old_field in content:
    content = content.replace(old_field, new_field)
    print("FormField inserted in config.tsx.")
else:
    # Try alternate spacing/indentation
    content = content.replace(
        '                    name="defaultLots"\n                    render={({ field }) => (\n                      <FormItem>\n                        <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Default Lot Size (Auto-Trade)</FormLabel>\n                        <FormControl>\n                          <Input type="number" step="0.01" min="0.001" {...field} className="font-mono border-border bg-background" />\n                        </FormControl>\n                        <FormDescription className="text-xs">\n                          Fixed lot size used for all automatic spread trades. (e.g. 0.01 to risk minimum).\n                        </FormDescription>\n                        <FormMessage />\n                      </FormItem>\n                    )}\n                  />',
        '                    name="defaultLots"\n                    render={({ field }) => (\n                      <FormItem>\n                        <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Default Lot Size (Auto-Trade)</FormLabel>\n                        <FormControl>\n                          <Input type="number" step="0.01" min="0.001" {...field} className="font-mono border-border bg-background" />\n                        </FormControl>\n                        <FormDescription className="text-xs">\n                          Fixed lot size used for all automatic spread trades. (e.g. 0.01 to risk minimum).\n                        </FormDescription>\n                        <FormMessage />\n                      </FormItem>\n                    )}\n                  />\n\n                  <FormField\n                    control={form.control}\n                    name="maxDailyTrades"\n                    render={({ field }) => (\n                      <FormItem>\n                        <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Max Daily Trades Limit</FormLabel>\n                        <FormControl>\n                          <Input type="number" min="1" {...field} className="font-mono border-border bg-background" />\n                        </FormControl>\n                        <FormDescription className="text-xs">\n                          Maximum number of trades the bot can execute per day. (e.g., set to 100 for no daily limit warnings).\n                        </FormDescription>\n                        <FormMessage />\n                      </FormItem>\n                    )}\n                  />'
    )
    print("FormField inserted (fallback) in config.tsx.")

with open(config_path, "w", encoding="utf-8") as f:
    f.write(content)
print("config.tsx updated.")
