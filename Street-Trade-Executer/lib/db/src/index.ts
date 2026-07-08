import {
  pgTable,
  serial,
  varchar,
  numeric,
  boolean,
  timestamp,
  date,
  bigint,
  text,
  integer,
} from "drizzle-orm/pg-core";

export const botStateTable = pgTable("bot_state", {
  id: serial("id").primaryKey(),
  activePair: varchar("active_pair", { length: 50 }).notNull().default("EURUSD/GBPUSD"),
  systemStatus: varchar("system_status", { length: 50 }).notNull().default("BOT OFFLINE"),
  equity: numeric("equity", { precision: 15, scale: 2 }).default("0"),
  drawdownPercent: numeric("drawdown_percent", { precision: 5, scale: 2 }).default("0"),
  floatingProfit: numeric("floating_profit", { precision: 15, scale: 2 }).default("0"),
  zScore: numeric("z_score", { precision: 10, scale: 4 }).default("0"),
  hedgeRatio: numeric("hedge_ratio", { precision: 10, scale: 4 }).default("0"),
  obiA: numeric("obi_a", { precision: 10, scale: 4 }).default("0"),
  obiB: numeric("obi_b", { precision: 10, scale: 4 }).default("0"),
  tradesToday: integer("trades_today").default(0),
  slPips: numeric("sl_pips", { precision: 6, scale: 1 }).default("10"),
  tpPips: numeric("tp_pips", { precision: 6, scale: 1 }).default("20"),
  smcEnabled: boolean("smc_enabled").default(true),
  autoExecute: boolean("auto_execute").default(true),
  cryptoEnabled: boolean("crypto_enabled").default(true),
  metalsEnabled: boolean("metals_enabled").default(true),
  forexEnabled: boolean("forex_enabled").default(true),
  indicesEnabled: boolean("indices_enabled").default(true),
  riskLimitsEnabled: boolean("risk_limits_enabled").default(true),
  zEntryThreshold: numeric("z_entry_threshold", { precision: 4, scale: 2 }).default("2.00"),
  lastHeartbeat: timestamp("last_heartbeat"),
  updatedAt: timestamp("updated_at").defaultNow(),
});

export const tradesTable = pgTable("trades", {
  ticket: bigint("ticket", { mode: "number" }).primaryKey(),
  symbol: varchar("symbol", { length: 50 }).notNull(),
  orderType: varchar("order_type", { length: 10 }).notNull(),
  lots: numeric("lots", { precision: 10, scale: 2 }).notNull(),
  entryPrice: numeric("entry_price", { precision: 15, scale: 5 }).notNull(),
  closePrice: numeric("close_price", { precision: 15, scale: 5 }),
  profit: numeric("profit", { precision: 15, scale: 2 }),
  entryTime: timestamp("entry_time").notNull(),
  closeTime: timestamp("close_time"),
  status: varchar("status", { length: 20 }).default("OPEN"),
  comment: varchar("comment", { length: 100 }),
  signalId: integer("signal_id"),
});

export const signalsTable = pgTable("signals", {
  id: serial("id").primaryKey(),
  timestamp: timestamp("timestamp").defaultNow(),
  symbolA: varchar("symbol_a", { length: 50 }).notNull(),
  symbolB: varchar("symbol_b", { length: 50 }).notNull(),
  priceA: numeric("price_a", { precision: 15, scale: 5 }).notNull(),
  priceB: numeric("price_b", { precision: 15, scale: 5 }).notNull(),
  beta: numeric("beta", { precision: 15, scale: 5 }).notNull(),
  alpha: numeric("alpha", { precision: 15, scale: 5 }).notNull(),
  zScore: numeric("z_score", { precision: 10, scale: 4 }).notNull(),
  obi: numeric("obi", { precision: 10, scale: 4 }).notNull(),
  action: varchar("action", { length: 20 }).notNull(),
});

export const fvgZonesTable = pgTable("fvg_zones", {
  id: serial("id").primaryKey(),
  symbol: varchar("symbol", { length: 50 }).notNull(),
  zoneType: varchar("zone_type", { length: 30 }).notNull(),
  lowPrice: numeric("low_price", { precision: 15, scale: 5 }).notNull(),
  highPrice: numeric("high_price", { precision: 15, scale: 5 }).notNull(),
  updatedAt: timestamp("updated_at").defaultNow(),
});

export const dailyMetricsTable = pgTable("daily_metrics", {
  tradingDate: date("trading_date").primaryKey(),
  startEquity: numeric("start_equity", { precision: 15, scale: 2 }).notNull(),
  currentEquity: numeric("current_equity", { precision: 15, scale: 2 }).notNull(),
  maxDrawdownPercent: numeric("max_drawdown_percent", { precision: 5, scale: 2 }).default("0"),
  tradesToday: integer("trades_today").default(0),
  updatedAt: timestamp("updated_at").defaultNow(),
});

export const tradeCommandsTable = pgTable("trade_commands", {
  id: serial("id").primaryKey(),
  symbol: varchar("symbol", { length: 20 }).notNull(),
  direction: varchar("direction", { length: 10 }).notNull(),
  lots: numeric("lots", { precision: 10, scale: 2 }).notNull(),
  slPips: numeric("sl_pips", { precision: 6, scale: 1 }),
  tpPips: numeric("tp_pips", { precision: 6, scale: 1 }),
  comment: varchar("comment", { length: 100 }),
  status: varchar("status", { length: 20 }).default("PENDING"),
  executedAt: timestamp("executed_at"),
  errorMsg: text("error_msg"),
  createdAt: timestamp("created_at").defaultNow(),
});

export const scannedAssetsTable = pgTable("scanned_assets", {
  symbolPair: varchar("symbol_pair", { length: 100 }).primaryKey(),
  priceA: numeric("price_a", { precision: 15, scale: 5 }),
  priceB: numeric("price_b", { precision: 15, scale: 5 }),
  winRate: numeric("win_rate", { precision: 5, scale: 2 }),
  zScore: numeric("z_score", { precision: 10, scale: 4 }),
  action: varchar("action", { length: 20 }),
  updatedAt: timestamp("updated_at").defaultNow(),
});

import { drizzle } from "drizzle-orm/node-postgres";
import pg from "pg";

// Parse timestamp without timezone (type OID 1114) as UTC
pg.types.setTypeParser(1114, (str) => new Date(str + " UTC"));

const connectionString = process.env.DATABASE_URL;

export const pool = new pg.Pool({
  connectionString,
});

export const db = drizzle(pool);

