import os

routes_config_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "api-server", "src", "routes", "config.ts")

with open(routes_config_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update GET /config response to return initialBalance
old_get_resp = """      defaultLots: Number(state?.defaultLots ?? 0.01),
    });"""

new_get_resp = """      defaultLots: Number(state?.defaultLots ?? 0.01),
      initialBalance: Number(state?.initialBalance ?? 100000.00),
    });"""

content = content.replace(old_get_resp, new_get_resp)

# 2. Update POST /config destructuring to retrieve initialBalance
old_post_destruct = """    const { activePair, slPips, tpPips, zEntryThreshold, smcEnabled, autoExecute, cryptoEnabled, metalsEnabled, forexEnabled, indicesEnabled, riskLimitsEnabled, defaultLots, maxDailyTrades } = parsed.data;"""

new_post_destruct = """    const { activePair, slPips, tpPips, zEntryThreshold, smcEnabled, autoExecute, cryptoEnabled, metalsEnabled, forexEnabled, indicesEnabled, riskLimitsEnabled, defaultLots, maxDailyTrades, initialBalance } = parsed.data;"""

content = content.replace(old_post_destruct, new_post_destruct)

# 3. Update POST /config INSERT query to insert initial_balance and max_equity_peak
old_insert = """    await db.execute(
      sql`INSERT INTO bot_state (id, active_pair, sl_pips, tp_pips, z_entry_threshold, smc_enabled, auto_execute, crypto_enabled, metals_enabled, forex_enabled, indices_enabled, risk_limits_enabled, default_lots, max_trades, system_status, updated_at)
          SELECT 1, ${activePair}, ${(slPips ?? 10).toString()}, ${(tpPips ?? 20).toString()}, ${zEntry.toString()}, ${smcEnabled ?? true}, ${autoExec}, ${cryptoExec}, ${metalsExec}, ${forexExec}, ${indicesExec}, ${riskLimits}, ${defLots.toString()}, ${maxDailyTrades ?? 3}, 'BOT OFFLINE', NOW()
          WHERE NOT EXISTS (SELECT 1 FROM bot_state)`
    );"""

new_insert = """    await db.execute(
      sql`INSERT INTO bot_state (id, active_pair, sl_pips, tp_pips, z_entry_threshold, smc_enabled, auto_execute, crypto_enabled, metals_enabled, forex_enabled, indices_enabled, risk_limits_enabled, default_lots, max_trades, system_status, updated_at, initial_balance, max_equity_peak)
          SELECT 1, ${activePair}, ${(slPips ?? 10).toString()}, ${(tpPips ?? 20).toString()}, ${zEntry.toString()}, ${smcEnabled ?? true}, ${autoExec}, ${cryptoExec}, ${metalsExec}, ${forexExec}, ${indicesExec}, ${riskLimits}, ${defLots.toString()}, ${maxDailyTrades ?? 3}, 'BOT OFFLINE', NOW(), ${(initialBalance ?? 100000).toString()}, ${(initialBalance ?? 100000).toString()}
          WHERE NOT EXISTS (SELECT 1 FROM bot_state)`
    );"""

content = content.replace(old_insert, new_insert)

# 4. Update POST /config UPDATE query to update initial_balance and reset max_equity_peak
old_update = """    await db.execute(
      sql`UPDATE bot_state
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
          WHERE id = (SELECT MIN(id) FROM bot_state)`
    );"""

new_update = """    await db.execute(
      sql`UPDATE bot_state
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
              initial_balance = ${(initialBalance ?? 100000).toString()},
              max_equity_peak = ${(initialBalance ?? 100000).toString()},
              updated_at   = NOW()
          WHERE id = (SELECT MIN(id) FROM bot_state)`
    );"""

content = content.replace(old_update, new_update)

# 5. Update POST /config response values
old_post_resp = """      defaultLots: Number(updated?.defaultLots ?? defLots),
    });"""

new_post_resp = """      defaultLots: Number(updated?.defaultLots ?? defLots),
      initialBalance: Number(updated?.initialBalance ?? initialBalance ?? 100000),
    });"""

content = content.replace(old_post_resp, new_post_resp)

# Also fix TS7030 error in config.ts catch block if any (by adding return before res.status(500))
content = content.replace("res.status(500).json({ error: \"Failed to get config\" });", "return res.status(500).json({ error: \"Failed to get config\" });")
content = content.replace("res.status(500).json({ error: \"Failed to update config\" });", "return res.status(500).json({ error: \"Failed to update config\" });")

with open(routes_config_path, "w", encoding="utf-8") as f:
    f.write(content)
print("config.ts API route updated with initialBalance columns mapping.")
