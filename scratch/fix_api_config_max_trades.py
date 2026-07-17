import os

config_api_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "api-server", "src", "routes", "config.ts")

with open(config_api_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update GET config response
old_get = """      zEntryThreshold: Number(state?.zEntryThreshold ?? 2.0),
      maxDailyTrades: 3,
      maxDailyLossPercent: 4.2,"""

new_get = """      zEntryThreshold: Number(state?.zEntryThreshold ?? 2.0),
      maxDailyTrades: Number(state?.maxTrades ?? 3),
      maxDailyLossPercent: 2.8,"""

content = content.replace(old_get, new_get)

# 2. Update POST config destructuring and variables
old_post_vars = """    const { activePair, slPips, tpPips, zEntryThreshold, smcEnabled, autoExecute, cryptoEnabled, metalsEnabled, forexEnabled, indicesEnabled, riskLimitsEnabled, defaultLots } = parsed.data;
    const parts = activePair.split("/");
    if (parts.length !== 2 || !parts[0] || !parts[1]) {
      res.status(400).json({ error: "activePair must be SYMBOL_A/SYMBOL_B" });
      return;
    }

    const autoExec = autoExecute ?? true;
    const cryptoExec = cryptoEnabled ?? true;
    const metalsExec = metalsEnabled ?? true;
    const forexExec = forexEnabled ?? true;
    const indicesExec = indicesEnabled ?? true;
    const riskLimits = riskLimitsEnabled ?? true;
    const zEntry = zEntryThreshold ?? 2.0;
    const defLots = defaultLots ?? 0.01;"""

new_post_vars = """    const { activePair, slPips, tpPips, zEntryThreshold, smcEnabled, autoExecute, cryptoEnabled, metalsEnabled, forexEnabled, indicesEnabled, riskLimitsEnabled, defaultLots, maxDailyTrades } = parsed.data;
    const parts = activePair.split("/");
    if (parts.length !== 2 || !parts[0] || !parts[1]) {
      res.status(400).json({ error: "activePair must be SYMBOL_A/SYMBOL_B" });
      return;
    }

    const autoExec = autoExecute ?? true;
    const cryptoExec = cryptoEnabled ?? true;
    const metalsExec = metalsEnabled ?? true;
    const forexExec = forexEnabled ?? true;
    const indicesExec = indicesEnabled ?? true;
    const riskLimits = riskLimitsEnabled ?? true;
    const zEntry = zEntryThreshold ?? 2.0;
    const defLots = defaultLots ?? 0.01;"""

content = content.replace(old_post_vars, new_post_vars)

# 3. Update SQL INSERT and UPDATE in POST
old_sql_insert = """      sql`INSERT INTO bot_state (id, active_pair, sl_pips, tp_pips, z_entry_threshold, smc_enabled, auto_execute, crypto_enabled, metals_enabled, forex_enabled, indices_enabled, risk_limits_enabled, default_lots, system_status, updated_at)
          SELECT 1, ${activePair}, ${(slPips ?? 10).toString()}, ${(tpPips ?? 20).toString()}, ${zEntry.toString()}, ${smcEnabled ?? true}, ${autoExec}, ${cryptoExec}, ${metalsExec}, ${forexExec}, ${indicesExec}, ${riskLimits}, ${defLots.toString()}, 'BOT OFFLINE', NOW()
          WHERE NOT EXISTS (SELECT 1 FROM bot_state)`"""

new_sql_insert = """      sql`INSERT INTO bot_state (id, active_pair, sl_pips, tp_pips, z_entry_threshold, smc_enabled, auto_execute, crypto_enabled, metals_enabled, forex_enabled, indices_enabled, risk_limits_enabled, default_lots, max_trades, system_status, updated_at)
          SELECT 1, ${activePair}, ${(slPips ?? 10).toString()}, ${(tpPips ?? 20).toString()}, ${zEntry.toString()}, ${smcEnabled ?? true}, ${autoExec}, ${cryptoExec}, ${metalsExec}, ${forexExec}, ${indicesExec}, ${riskLimits}, ${defLots.toString()}, ${maxDailyTrades ?? 3}, 'BOT OFFLINE', NOW()
          WHERE NOT EXISTS (SELECT 1 FROM bot_state)`"""

content = content.replace(old_sql_insert, new_sql_insert)

old_sql_update = """      sql`UPDATE bot_state
          SET active_pair  = ${activePair},
              sl_pips      = ${(slPips ?? 10).toString()},
              tp_pips      = ${(tpPips ?? 20).toString()},
              z_entry_threshold = ${zEntry.toString()},
              smc_enabled  = ${smcEnabled ?? true},
              auto_execute = ${autoExec},
              crypto_enabled = ${cryptoExec},
              metals_enabled = ${metalsExec},
              forex_enabled = ${forexExec},
              indices_enabled = ${indicesExec},
              risk_limits_enabled = ${riskLimits},
              default_lots = ${defLots.toString()},
              updated_at   = NOW()
          WHERE id = (SELECT MIN(id) FROM bot_state)`"""

new_sql_update = """      sql`UPDATE bot_state
          SET active_pair  = ${activePair},
              sl_pips      = ${(slPips ?? 10).toString()},
              tp_pips      = ${(tpPips ?? 20).toString()},
              z_entry_threshold = ${zEntry.toString()},
              smc_enabled  = ${smcEnabled ?? true},
              auto_execute = ${autoExec},
              crypto_enabled = ${cryptoExec},
              metals_enabled = ${metalsExec},
              forex_enabled = ${forexExec},
              indices_enabled = ${indicesExec},
              risk_limits_enabled = ${riskLimits},
              default_lots = ${defLots.toString()},
              max_trades   = ${maxDailyTrades ?? 3},
              updated_at   = NOW()
          WHERE id = (SELECT MIN(id) FROM bot_state)`"""

content = content.replace(old_sql_update, new_sql_update)

# 4. Update POST response JSON
old_post_res = """      zEntryThreshold: Number(updated?.zEntryThreshold ?? zEntry),
      maxDailyTrades: 3,
      maxDailyLossPercent: 4.2,"""

new_post_res = """      zEntryThreshold: Number(updated?.zEntryThreshold ?? zEntry),
      maxDailyTrades: Number(updated?.maxTrades ?? maxDailyTrades ?? 3),
      maxDailyLossPercent: 2.8,"""

content = content.replace(old_post_res, new_post_res)

with open(config_api_path, "w", encoding="utf-8") as f:
    f.write(content)
print("api-server config route updated.")
