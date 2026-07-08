import { pool } from "@workspace/db";
import { logger } from "./logger";

export async function initDb(): Promise<void> {
  const statements = [
    `CREATE TABLE IF NOT EXISTS bot_state (
      id SERIAL PRIMARY KEY,
      active_pair VARCHAR(50) NOT NULL DEFAULT 'EURUSD/GBPUSD',
      system_status VARCHAR(50) NOT NULL DEFAULT 'BOT OFFLINE',
      equity NUMERIC(15, 2) DEFAULT 0,
      drawdown_percent NUMERIC(5, 2) DEFAULT 0,
      floating_profit NUMERIC(15, 2) DEFAULT 0,
      z_score NUMERIC(10, 4) DEFAULT 0,
      hedge_ratio NUMERIC(10, 4) DEFAULT 0,
      obi_a NUMERIC(10, 4) DEFAULT 0,
      obi_b NUMERIC(10, 4) DEFAULT 0,
      trades_today INTEGER DEFAULT 0,
      sl_pips NUMERIC(6, 1) DEFAULT 10,
      smc_enabled BOOLEAN DEFAULT TRUE,
      auto_execute BOOLEAN DEFAULT TRUE,
      crypto_enabled BOOLEAN DEFAULT TRUE,
      metals_enabled BOOLEAN DEFAULT TRUE,
      forex_enabled BOOLEAN DEFAULT TRUE,
      indices_enabled BOOLEAN DEFAULT TRUE,
      risk_limits_enabled BOOLEAN DEFAULT TRUE,
      last_heartbeat TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )`,
    `CREATE TABLE IF NOT EXISTS trades (
      ticket BIGINT PRIMARY KEY,
      symbol VARCHAR(50) NOT NULL,
      order_type VARCHAR(10) NOT NULL,
      lots NUMERIC(10, 2) NOT NULL,
      entry_price NUMERIC(15, 5) NOT NULL,
      close_price NUMERIC(15, 5),
      profit NUMERIC(15, 2),
      entry_time TIMESTAMP NOT NULL,
      close_time TIMESTAMP,
      status VARCHAR(20) DEFAULT 'OPEN',
      comment VARCHAR(100),
      signal_id INTEGER REFERENCES signals(id)
    )`,
    `CREATE TABLE IF NOT EXISTS signals (
      id SERIAL PRIMARY KEY,
      timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      symbol_a VARCHAR(50) NOT NULL,
      symbol_b VARCHAR(50) NOT NULL,
      price_a NUMERIC(15, 5) NOT NULL,
      price_b NUMERIC(15, 5) NOT NULL,
      beta NUMERIC(15, 5) NOT NULL,
      alpha NUMERIC(15, 5) NOT NULL,
      z_score NUMERIC(10, 4) NOT NULL,
      obi NUMERIC(10, 4) NOT NULL,
      action VARCHAR(20) NOT NULL
    )`,
    `CREATE TABLE IF NOT EXISTS fvg_zones (
      id SERIAL PRIMARY KEY,
      symbol VARCHAR(50) NOT NULL,
      zone_type VARCHAR(30) NOT NULL,
      low_price NUMERIC(15, 5) NOT NULL,
      high_price NUMERIC(15, 5) NOT NULL,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )`,
    `CREATE TABLE IF NOT EXISTS daily_metrics (
      trading_date DATE PRIMARY KEY,
      start_equity NUMERIC(15, 2) NOT NULL,
      current_equity NUMERIC(15, 2) NOT NULL,
      max_drawdown_percent NUMERIC(5, 2) DEFAULT 0.00,
      trades_today INTEGER DEFAULT 0,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )`,
    `CREATE TABLE IF NOT EXISTS trade_commands (
      id SERIAL PRIMARY KEY,
      symbol VARCHAR(20) NOT NULL,
      direction VARCHAR(10) NOT NULL,
      lots NUMERIC(10, 2) NOT NULL,
      sl_pips NUMERIC(6, 1),
      tp_pips NUMERIC(6, 1),
      comment VARCHAR(100),
      status VARCHAR(20) DEFAULT 'PENDING',
      executed_at TIMESTAMP,
      error_msg TEXT,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )`,
    `CREATE TABLE IF NOT EXISTS manual_commands (
      id SERIAL PRIMARY KEY,
      symbol VARCHAR(20) NOT NULL,
      direction VARCHAR(10) NOT NULL,
      lots NUMERIC(10, 2) NOT NULL,
      sl_pips NUMERIC(6, 1),
      tp_pips NUMERIC(6, 1),
      comment VARCHAR(100),
      status VARCHAR(20) DEFAULT 'PENDING',
      error_msg TEXT,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )`,
    `CREATE TABLE IF NOT EXISTS scanned_assets (
      symbol_pair VARCHAR(100) PRIMARY KEY,
      price_a NUMERIC(15, 5),
      price_b NUMERIC(15, 5),
      win_rate NUMERIC(5, 2),
      z_score NUMERIC(10, 4),
      action VARCHAR(20),
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )`,
  ];

  const client = await pool.connect();
  try {
    for (const sql of statements) {
      await client.query(sql);
    }
    logger.info("Database tables ready");
  } catch (err) {
    logger.error({ err }, "Failed to initialize database tables");
    throw err;
  } finally {
    client.release();
  }
}
