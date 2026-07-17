import os

config_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "trading-dashboard", "src", "pages", "config.tsx")

with open(config_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add initialBalance to configSchema validation
old_schema = """  defaultLots: z.coerce.number().min(0.001).max(500),
  maxDailyTrades: z.coerce.number().min(1).max(1000),
});"""

new_schema = """  defaultLots: z.coerce.number().min(0.001).max(500),
  maxDailyTrades: z.coerce.number().min(1).max(1000),
  initialBalance: z.coerce.number().min(100).max(10000000),
});"""

content = content.replace(old_schema, new_schema)

# 2. Add initialBalance to form default values
old_defaults = """      defaultLots: 0.01,
      maxDailyTrades: 3,
    },"""

new_defaults = """      defaultLots: 0.01,
      maxDailyTrades: 3,
      initialBalance: 100000,
    },"""

content = content.replace(old_defaults, new_defaults)

# 3. Add initialBalance to values mapping
old_values = """          defaultLots: (config as any).defaultLots ?? 0.01,
          maxDailyTrades: config.maxDailyTrades,
        }"""

new_values = """          defaultLots: (config as any).defaultLots ?? 0.01,
          maxDailyTrades: config.maxDailyTrades,
          initialBalance: (config as any).initialBalance ?? 100000,
        }"""

content = content.replace(old_values, new_values)

# 4. Add FormField for initialBalance inside Account Parameters card
old_form_field = """                  <FormField
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

new_form_field = """                  <FormField
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
                  />

                  <FormField
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

content = content.replace(old_form_field, new_form_field)

with open(config_path, "w", encoding="utf-8") as f:
    f.write(content)
print("config.tsx updated with initialBalance configuration field.")
