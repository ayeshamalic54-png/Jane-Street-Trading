import os

db_index_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "lib", "db", "src", "index.ts")

with open(db_index_path, "r", encoding="utf-8") as f:
    content = f.read()

# Locate fvg_zones and daily_metrics blocks and remove maxTrades only from them
# Let's replace the exact blocks to be extremely safe

old_fvg_zones = """export const fvgZonesTable = pgTable("fvg_zones", {
  id: serial("id").primaryKey(),
  symbol: varchar("symbol", { length: 50 }).notNull(),
  zoneType: varchar("zone_type", { length: 30 }).notNull(),
  lowPrice: numeric("low_price", { precision: 15, scale: 5 }).notNull(),
  highPrice: numeric("high_price", { precision: 15, scale: 5 }).notNull(),
  updatedAt: timestamp("updated_at").defaultNow(),
  maxTrades: integer("max_trades").default(3),
});"""

new_fvg_zones = """export const fvgZonesTable = pgTable("fvg_zones", {
  id: serial("id").primaryKey(),
  symbol: varchar("symbol", { length: 50 }).notNull(),
  zoneType: varchar("zone_type", { length: 30 }).notNull(),
  lowPrice: numeric("low_price", { precision: 15, scale: 5 }).notNull(),
  highPrice: numeric("high_price", { precision: 15, scale: 5 }).notNull(),
  updatedAt: timestamp("updated_at").defaultNow(),
});"""

content = content.replace(old_fvg_zones, new_fvg_zones)

old_daily_metrics = """export const dailyMetricsTable = pgTable("daily_metrics", {
  tradingDate: date("trading_date").primaryKey(),
  startEquity: numeric("start_equity", { precision: 15, scale: 2 }).notNull(),
  currentEquity: numeric("current_equity", { precision: 15, scale: 2 }).notNull(),
  maxDrawdownPercent: numeric("max_drawdown_percent", { precision: 5, scale: 2 }).default("0"),
  tradesToday: integer("trades_today").default(0),
  updatedAt: timestamp("updated_at").defaultNow(),
  maxTrades: integer("max_trades").default(3),
});"""

new_daily_metrics = """export const dailyMetricsTable = pgTable("daily_metrics", {
  tradingDate: date("trading_date").primaryKey(),
  startEquity: numeric("start_equity", { precision: 15, scale: 2 }).notNull(),
  currentEquity: numeric("current_equity", { precision: 15, scale: 2 }).notNull(),
  maxDrawdownPercent: numeric("max_drawdown_percent", { precision: 5, scale: 2 }).default("0"),
  tradesToday: integer("trades_today").default(0),
  updatedAt: timestamp("updated_at").defaultNow(),
});"""

content = content.replace(old_daily_metrics, new_daily_metrics)

with open(db_index_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Duplicate maxTrades columns removed from index.ts.")
