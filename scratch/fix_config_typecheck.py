import os

config_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "trading-dashboard", "src", "pages", "config.tsx")

with open(config_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Remove useGetPrices for crypto
target_prices = """  const { data: prices } = useGetPrices({ category: "crypto" });
  const cryptoSymbols = prices ? Array.from(new Set(prices.map((p) => p.symbol))).sort() : [];"""

if target_prices in content:
    content = content.replace(target_prices, "")
    print("Removed crypto prices fetch in config.tsx")
else:
    # Try with single line spacing
    content = content.replace('  const { data: prices } = useGetPrices({ category: "crypto" });\n  const cryptoSymbols = prices ? Array.from(new Set(prices.map((p) => p.symbol))).sort() : [];', "")
    print("Removed crypto prices fetch (fallback) in config.tsx")

# 2. Locate the Pair grid block start and end to replace the entire activeCategory === "crypto" ternary structure
start_grid = content.find('{/* Pair grid */}')
if start_grid != -1:
    # Find the next 'activeCategory !== "custom" ? ('
    find_str = 'activeCategory !== "custom" ? ('
    find_idx = content.find(find_str, start_grid)
    if find_idx != -1:
        # We want to replace from after {/* Pair grid */} up to and including 'activeCategory !== "custom" ? ('
        # with just 'activeCategory !== "custom" ? ('
        prefix = content[:start_grid + len('{/* Pair grid */}') + 1]
        suffix = content[find_idx:]
        content = prefix + "{" + suffix
        print("Ternary prefix for activeCategory === 'crypto' removed.")

with open(config_path, "w", encoding="utf-8") as f:
    f.write(content)
print("config.tsx updated.")
