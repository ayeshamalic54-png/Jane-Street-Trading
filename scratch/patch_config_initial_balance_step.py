import os

config_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "trading-dashboard", "src", "pages", "config.tsx")

with open(config_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace the input element for initialBalance to add step="0.01"
old_field = """                  <FormField
                    control={form.control}
                    name="initialBalance"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Initial Account Balance ($)</FormLabel>
                        <FormControl>
                          <Input type="number" min="100" {...field} className="font-mono border-border bg-background" />
                        </FormControl>"""

new_field = """                  <FormField
                    control={form.control}
                    name="initialBalance"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Initial Account Balance ($)</FormLabel>
                        <FormControl>
                          <Input type="number" step="0.01" min="100" {...field} className="font-mono border-border bg-background" />
                        </FormControl>"""

if old_field in content:
    content = content.replace(old_field, new_field)
    print("Added step=\"0.01\" to initialBalance input field in config.tsx.")
else:
    print("old_field target not found in config.tsx!")

with open(config_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
