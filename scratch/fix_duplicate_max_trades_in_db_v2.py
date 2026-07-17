import os

db_index_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "lib", "db", "src", "index.ts")

with open(db_index_path, "r", encoding="utf-8") as f:
    content = f.read()

# Locate scanned_assets block and remove maxTrades from it
old_scanned_assets = """export const scannedAssetsTable = pgTable("scanned_assets", {
  symbolPair: varchar("symbol_pair", { length: 100 }).primaryKey(),
  priceA: numeric("price_a", { precision: 15, scale: 5 }),
  priceB: numeric("price_b", { precision: 15, scale: 5 }),
  winRate: numeric("win_rate", { precision: 5, scale: 2 }),
  zScore: numeric("z_score", { precision: 10, scale: 4 }),
  action: varchar("action", { length: 20 }),
  updatedAt: timestamp("updated_at").defaultNow(),
  maxTrades: integer("max_trades").default(3),
});"""

new_scanned_assets = """export const scannedAssetsTable = pgTable("scanned_assets", {
  symbolPair: varchar("symbol_pair", { length: 100 }).primaryKey(),
  priceA: numeric("price_a", { precision: 15, scale: 5 }),
  priceB: numeric("price_b", { precision: 15, scale: 5 }),
  winRate: numeric("win_rate", { precision: 5, scale: 2 }),
  zScore: numeric("z_score", { precision: 10, scale: 4 }),
  action: varchar("action", { length: 20 }),
  updatedAt: timestamp("updated_at").defaultNow(),
});"""

content = content.replace(old_scanned_assets, new_scanned_assets)

with open(db_index_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Duplicate maxTrades column removed from scannedAssetsTable in index.ts.")
