import { Router } from "express";
import { db } from "@workspace/db";
import { botStateTable } from "@workspace/db";
import { UpdateConfigBody } from "@workspace/api-zod";
import { sql } from "drizzle-orm";
import { ensureSessionGuardColumns, extractSessionGuardFields } from "../lib/sessionGuard";
import { broadcastDashboardNow } from "../lib/ws";

const router = Router();

function parseSessionHour(fallback: number, ...vals: unknown[]): number {
  for (const v of vals) {
    if (v === undefined || v === null || v === "") continue;
    const n = Number(v);
    if (Number.isFinite(n)) return ((n % 24) + 24) % 24;
  }
  return fallback;
}

router.get("/config", async (req, res) => {
  try {
    await ensureSessionGuardColumns();
    const rows = await db.select().from(botStateTable).limit(1);
    const state = rows[0];
    const pair = state?.activePair ?? "EURUSD/GBPUSD";
    const parts = pair.split("/");

    return res.json({
      activePair: pair,
      symbolA: parts[0] ?? "EURUSD",
      symbolB: parts[1] ?? "GBPUSD",
      zEntryThreshold: Number(state?.zEntryThreshold ?? 2.0),
      maxDailyTrades: Number(state?.maxTrades ?? 3),
      maxDailyLossPercent: 2.8,
      requireSmcConfluence: state?.smcEnabled ?? true,
      slPips: Number(state?.slPips ?? 10),
      tpPips: Number(state?.tpPips ?? 20),
      smcEnabled: state?.smcEnabled ?? true,
      autoExecute: state?.autoExecute ?? true,
      cryptoEnabled: state?.cryptoEnabled ?? true,
      metalsEnabled: state?.metalsEnabled ?? true,
      forexEnabled: state?.forexEnabled ?? true,
      indicesEnabled: state?.indicesEnabled ?? true,
      stocksEnabled: state?.stocksEnabled ?? true,
      riskLimitsEnabled: state?.riskLimitsEnabled ?? true,
      knifeProtectionEnabled: state?.knifeProtectionEnabled ?? true,
      obiEnabled: state?.obiEnabled ?? true,
      volatilityFilterEnabled: state?.volatilityFilterEnabled ?? true,
      defaultLots: Number(state?.defaultLots ?? 0.01),
      initialBalance: Number(state?.initialBalance ?? 100000.00),
      haltDrawdownLimit: Number(state?.haltDrawdownLimit ?? (state as any)?.halt_drawdown_limit ?? 0.83),
      maxDrawdownLimit: Number(state?.maxDrawdownLimit ?? (state as any)?.max_drawdown_limit ?? 3.30),
      ...extractSessionGuardFields(state),
    });
  } catch (err) {
    console.error("Failed to get config", err);
    return res.status(500).json({ error: "Failed to get config" });
  }
});

router.post("/config", async (req, res) => {
  try {
    await ensureSessionGuardColumns();
    const parsed = UpdateConfigBody.safeParse(req.body);
    const bodyObj = req.body || {};

    const rows = await db.select().from(botStateTable).limit(1);
    const state = rows[0];
    const curSess = extractSessionGuardFields(state);

    const { activePair, slPips, tpPips, zEntryThreshold, smcEnabled, autoExecute, cryptoEnabled, metalsEnabled, forexEnabled, riskLimitsEnabled, defaultLots, maxDailyTrades, initialBalance, knifeProtectionEnabled, obiEnabled, volatilityFilterEnabled } = (parsed.success ? parsed.data : bodyObj) as any;
    const indicesEnabled = bodyObj.indicesEnabled !== undefined ? Boolean(bodyObj.indicesEnabled) : (state?.indicesEnabled ?? true);
    const stocksEnabled = bodyObj.stocksEnabled !== undefined ? Boolean(bodyObj.stocksEnabled) : ((state as any)?.stocks_enabled ?? true);

    const haltLimit = bodyObj.haltDrawdownLimit !== undefined ? Number(bodyObj.haltDrawdownLimit) : (bodyObj.halt_drawdown_limit !== undefined ? Number(bodyObj.halt_drawdown_limit) : Number(state?.haltDrawdownLimit ?? (state as any)?.halt_drawdown_limit ?? 0.83));
    const maxLimit = bodyObj.maxDrawdownLimit !== undefined ? Number(bodyObj.maxDrawdownLimit) : (bodyObj.max_drawdown_limit !== undefined ? Number(bodyObj.max_drawdown_limit) : Number(state?.maxDrawdownLimit ?? (state as any)?.max_drawdown_limit ?? 3.30));

    const sessEnabled = bodyObj.sessionGuardEnabled !== undefined ? Boolean(bodyObj.sessionGuardEnabled) : (bodyObj.session_guard_enabled !== undefined ? Boolean(bodyObj.session_guard_enabled) : curSess.sessionGuardEnabled);
    const sessStart = parseSessionHour(curSess.sessionStartHour, bodyObj.sessionStartHour, bodyObj.session_start_hour);
    const sessEnd = parseSessionHour(curSess.sessionEndHour, bodyObj.sessionEndHour, bodyObj.session_end_hour);
    const sess2Enabled = bodyObj.session2Enabled !== undefined ? Boolean(bodyObj.session2Enabled) : (bodyObj.session2_enabled !== undefined ? Boolean(bodyObj.session2_enabled) : curSess.session2Enabled);
    const sess2Start = parseSessionHour(curSess.session2StartHour, bodyObj.session2StartHour, bodyObj.session2_start_hour);
    const sess2End = parseSessionHour(curSess.session2EndHour, bodyObj.session2EndHour, bodyObj.session2_end_hour);

    const pairToSave = activePair || state?.activePair || "EURUSD/GBPUSD";
    let parts: string[] = ["EURUSD", "GBPUSD"];
    if (pairToSave !== "ALL") {
      parts = pairToSave.split("/");
      if (parts.length !== 2 || !parts[0] || !parts[1]) {
        return res.status(400).json({ error: "activePair must be SYMBOL_A/SYMBOL_B or ALL" });
      }
    }

    const autoExec = autoExecute !== undefined ? Boolean(autoExecute) : (state?.autoExecute ?? true);
    const cryptoExec = cryptoEnabled !== undefined ? Boolean(cryptoEnabled) : (state?.cryptoEnabled ?? true);
    const metalsExec = metalsEnabled !== undefined ? Boolean(metalsEnabled) : (state?.metalsEnabled ?? true);
    const forexExec = forexEnabled !== undefined ? Boolean(forexEnabled) : (state?.forexEnabled ?? true);
    const indicesExec = indicesEnabled !== undefined ? Boolean(indicesEnabled) : (state?.indicesEnabled ?? true);
    const stocksExec = stocksEnabled !== undefined ? Boolean(stocksEnabled) : ((state as any)?.stocks_enabled ?? true);
    const riskLimits = riskLimitsEnabled !== undefined ? Boolean(riskLimitsEnabled) : (state?.riskLimitsEnabled ?? true);
    const knifeExec = knifeProtectionEnabled !== undefined ? Boolean(knifeProtectionEnabled) : (state?.knifeProtectionEnabled ?? true);
    const obiExec = obiEnabled !== undefined ? Boolean(obiEnabled) : (state?.obiEnabled ?? true);
    const volExec = volatilityFilterEnabled !== undefined ? Boolean(volatilityFilterEnabled) : (state?.volatilityFilterEnabled ?? true);
    const zEntry = zEntryThreshold !== undefined ? Number(zEntryThreshold) : Number(state?.zEntryThreshold ?? 2.0);
    const defLots = defaultLots !== undefined ? Number(defaultLots) : Number(state?.defaultLots ?? 0.01);
    const slVal = slPips !== undefined ? Number(slPips) : Number(state?.slPips ?? 10);
    const tpVal = tpPips !== undefined ? Number(tpPips) : Number(state?.tpPips ?? 20);
    const smcVal = smcEnabled !== undefined ? Boolean(smcEnabled) : (state?.smcEnabled ?? true);
    const maxTradesVal = maxDailyTrades !== undefined ? Number(maxDailyTrades) : Number(state?.maxTrades ?? 3);
    const initBalVal = initialBalance !== undefined ? Number(initialBalance) : Number(state?.initialBalance ?? 100000);

    await db.execute(
      sql`INSERT INTO bot_state (id, active_pair, sl_pips, tp_pips, z_entry_threshold, smc_enabled, auto_execute, crypto_enabled, metals_enabled, forex_enabled, indices_enabled, stocks_enabled, risk_limits_enabled, default_lots, max_trades, system_status, updated_at, initial_balance, max_equity_peak, knife_protection_enabled, obi_enabled, volatility_filter_enabled, halt_drawdown_limit, max_drawdown_limit, session_guard_enabled, session_start_hour, session_end_hour, session2_enabled, session2_start_hour, session2_end_hour)
          SELECT 1, ${pairToSave}, ${slVal.toString()}, ${tpVal.toString()}, ${zEntry.toString()}, ${smcVal}, ${autoExec}, ${cryptoExec}, ${metalsExec}, ${forexExec}, ${indicesExec}, ${stocksExec}, ${riskLimits}, ${defLots.toString()}, ${maxTradesVal}, 'BOT OFFLINE', NOW(), ${initBalVal.toString()}, ${initBalVal.toString()}, ${knifeExec}, ${obiExec}, ${volExec}, ${haltLimit.toString()}, ${maxLimit.toString()}, ${sessEnabled}, ${sessStart}, ${sessEnd}, ${sess2Enabled}, ${sess2Start}, ${sess2End}
          WHERE NOT EXISTS (SELECT 1 FROM bot_state)`
    );

    await db.execute(
      sql`UPDATE bot_state
          SET active_pair  = ${pairToSave},
              sl_pips      = ${slVal.toString()},
              tp_pips      = ${tpVal.toString()},
              z_entry_threshold = ${zEntry.toString()},
              smc_enabled  = ${smcVal},
              auto_execute = ${autoExec},
              crypto_enabled = ${cryptoExec},
              metals_enabled = ${metalsExec},
              forex_enabled = ${forexExec},
              indices_enabled = ${indicesExec},
              stocks_enabled  = ${stocksExec},
              risk_limits_enabled = ${riskLimits},
              knife_protection_enabled = ${knifeExec},
              obi_enabled = ${obiExec},
              volatility_filter_enabled = ${volExec},
              default_lots = ${defLots.toString()},
              max_trades   = ${maxTradesVal},
              halt_drawdown_limit = ${haltLimit.toString()},
              max_drawdown_limit = ${maxLimit.toString()},
              session_guard_enabled = ${sessEnabled},
              session_start_hour    = ${sessStart},
              session_end_hour      = ${sessEnd},
              session2_enabled      = ${sess2Enabled},
              session2_start_hour   = ${sess2Start},
              session2_end_hour     = ${sess2End},
              updated_at   = NOW()
          WHERE id = (SELECT MIN(id) FROM bot_state)`
    );

    void broadcastDashboardNow();
    const updated = (await db.select().from(botStateTable).limit(1))[0];
    const updatedPair = updated?.activePair ?? activePair;
    const updatedParts = updatedPair.split("/");

    return res.json({
      activePair: updatedPair,
      symbolA: updatedParts[0] ?? parts[0],
      symbolB: updatedParts[1] ?? parts[1],
      zEntryThreshold: Number(updated?.zEntryThreshold ?? zEntry),
      maxDailyTrades: Number(updated?.maxTrades ?? maxDailyTrades ?? 3),
      maxDailyLossPercent: 2.8,
      requireSmcConfluence: updated?.smcEnabled ?? true,
      slPips: Number(updated?.slPips ?? slPips ?? 10),
      tpPips: Number(updated?.tpPips ?? tpPips ?? 20),
      smcEnabled: updated?.smcEnabled ?? true,
      autoExecute: updated?.autoExecute ?? autoExec,
      cryptoEnabled: updated?.cryptoEnabled ?? cryptoExec,
      metalsEnabled: updated?.metalsEnabled ?? metalsExec,
      forexEnabled: updated?.forexEnabled ?? forexExec,
      indicesEnabled: updated?.indicesEnabled ?? indicesExec,
      stocksEnabled: updated?.stocksEnabled ?? stocksExec,
      riskLimitsEnabled: updated?.riskLimitsEnabled ?? riskLimits,
      knifeProtectionEnabled: updated?.knifeProtectionEnabled ?? knifeExec,
      obiEnabled: updated?.obiEnabled ?? obiExec,
      volatilityFilterEnabled: updated?.volatilityFilterEnabled ?? volExec,
      defaultLots: Number(updated?.defaultLots ?? defLots),
      initialBalance: Number(updated?.initialBalance ?? initialBalance ?? 100000),
      haltDrawdownLimit: haltLimit,
      maxDrawdownLimit: maxLimit,
      ...extractSessionGuardFields({
        sessionGuardEnabled: sessEnabled,
        sessionStartHour: sessStart,
        sessionEndHour: sessEnd,
        session2Enabled: sess2Enabled,
        session2StartHour: sess2Start,
        session2EndHour: sess2End,
      }),
    });
  } catch (err) {
    console.error("Failed to update config", err);
    return res.status(500).json({ error: "Failed to update config" });
  }
});

router.post("/toggle-risk-limits", async (req, res) => {
  try {
    const body = req.body || {};
    const haltLimit = body.halt_drawdown_limit !== undefined ? Number(body.halt_drawdown_limit) : (body.haltDrawdownLimit !== undefined ? Number(body.haltDrawdownLimit) : 0.80);
    const maxLimit = body.max_drawdown_limit !== undefined ? Number(body.max_drawdown_limit) : (body.maxDrawdownLimit !== undefined ? Number(body.maxDrawdownLimit) : 3.30);
    const riskEnabled = body.risk_limits_enabled !== undefined ? Boolean(body.risk_limits_enabled) : true;

    await db.execute(
      sql`UPDATE bot_state
          SET halt_drawdown_limit = ${haltLimit.toString()},
              max_drawdown_limit  = ${maxLimit.toString()},
              risk_limits_enabled = ${riskEnabled},
              updated_at          = NOW()
          WHERE id = (SELECT MIN(id) FROM bot_state)`
    );

    return res.json({ status: "success", halt_drawdown_limit: haltLimit, max_drawdown_limit: maxLimit });
  } catch (err) {
    return res.status(500).json({ error: "Failed to update drawdown limits" });
  }
});

router.post("/toggle-session-guard", async (req, res) => {
  try {
    await ensureSessionGuardColumns();
    const rows = await db.select().from(botStateTable).limit(1);
    const curSess = extractSessionGuardFields(rows[0]);
    const body = req.body || {};

    const enabled = body.enabled !== undefined ? Boolean(body.enabled) : (body.sessionGuardEnabled !== undefined ? Boolean(body.sessionGuardEnabled) : curSess.sessionGuardEnabled);
    const startHour = parseSessionHour(curSess.sessionStartHour, body.start_hour, body.startHour, body.sessionStartHour);
    const endHour = parseSessionHour(curSess.sessionEndHour, body.end_hour, body.endHour, body.sessionEndHour);
    const session2Enabled = body.session2_enabled !== undefined ? Boolean(body.session2_enabled) : (body.session2Enabled !== undefined ? Boolean(body.session2Enabled) : curSess.session2Enabled);
    const session2StartHour = parseSessionHour(curSess.session2StartHour, body.session2_start_hour, body.session2StartHour);
    const session2EndHour = parseSessionHour(curSess.session2EndHour, body.session2_end_hour, body.session2EndHour);

    await db.execute(
      sql`UPDATE bot_state
          SET session_guard_enabled = ${enabled},
              session_start_hour    = ${startHour},
              session_end_hour      = ${endHour},
              session2_enabled      = ${session2Enabled},
              session2_start_hour   = ${session2StartHour},
              session2_end_hour     = ${session2EndHour},
              updated_at            = NOW()
          WHERE id = (SELECT MIN(id) FROM bot_state)`
    );

    void broadcastDashboardNow();
    return res.json({
      status: "success",
      enabled,
      start_hour: startHour,
      end_hour: endHour,
      ...extractSessionGuardFields({
        sessionGuardEnabled: enabled,
        sessionStartHour: startHour,
        sessionEndHour: endHour,
        session2Enabled,
        session2StartHour,
        session2EndHour,
      }),
    });
  } catch (err) {
    console.error("Failed to toggle session guard", err);
    return res.status(500).json({ error: "Failed to toggle session guard" });
  }
});


// ── MASTER BOT ENGINE ON/OFF CONTROL ─────────────────────────────
router.post("/bot/control", async (req, res) => {
  try {
    const isRunning = Boolean(req.body.isRunning);
    const statusTxt = isRunning ? "RUNNING (Active)" : "ENGINE STOPPED 🛑 (Standby)";
    if (isRunning) {
      await db.execute(sql`
        UPDATE bot_state
        SET is_bot_running = TRUE,
            auto_execute   = TRUE,
            system_status  = ${statusTxt},
            updated_at     = NOW()
        WHERE id = (SELECT MIN(id) FROM bot_state)
      `);
    } else {
      await db.execute(sql`
        UPDATE bot_state
        SET is_bot_running = FALSE,
            system_status  = ${statusTxt},
            updated_at     = NOW()
        WHERE id = (SELECT MIN(id) FROM bot_state)
      `);
    }
    return res.json({ status: "success", isRunning, systemStatus: statusTxt });
  } catch (err) {
    console.error("Failed to update bot control:", err);
    return res.status(500).json({ error: "Failed to update bot control" });
  }
});

// ── MT5 ACCOUNTS REGISTRY & REAL-TIME SWITCHER ────────────────────
router.get("/mt5/accounts", async (req, res) => {
  try {
    const result = await db.execute(sql`
      SELECT id, login, server, account_name, account_type, is_active, balance, equity, currency, company, updated_at
      FROM mt5_accounts
      ORDER BY is_active DESC, updated_at DESC;
    `);
    const rows = (result as any).rows || [];
    return res.json({ accounts: rows });
  } catch (err) {
    console.error("Failed to fetch mt5 accounts:", err);
    return res.status(500).json({ error: "Failed to fetch mt5 accounts" });
  }
});

router.post("/mt5/accounts", async (req, res) => {
  try {
    const { login, server, password, accountName, accountType } = req.body || {};
    if (!login || !server) {
      return res.status(400).json({ error: "Login and server are required" });
    }
    await db.execute(sql`
      INSERT INTO mt5_accounts (login, server, password, account_name, account_type, updated_at)
      VALUES (${Number(login)}, ${String(server)}, ${String(password || "")}, ${String(accountName || "MT5 Account")}, ${String(accountType || "REAL")}, NOW())
      ON CONFLICT (login) DO UPDATE SET
        server       = EXCLUDED.server,
        password     = CASE WHEN EXCLUDED.password IS NOT NULL AND EXCLUDED.password != '' THEN EXCLUDED.password ELSE mt5_accounts.password END,
        account_name = CASE WHEN EXCLUDED.account_name IS NOT NULL AND EXCLUDED.account_name != '' THEN EXCLUDED.account_name ELSE mt5_accounts.account_name END,
        account_type = EXCLUDED.account_type,
        updated_at   = NOW();
    `);
    return res.json({ status: "success", message: `Account #${login} registered successfully` });
  } catch (err) {
    console.error("Failed to register mt5 account:", err);
    return res.status(500).json({ error: "Failed to register account" });
  }
});

router.post("/mt5/switch", async (req, res) => {
  try {
    const { login } = req.body || {};
    if (!login) {
      return res.status(400).json({ error: "Login number is required" });
    }
    const targetLogin = Number(login);

    // Immediately restore saved equity/initial_balance/drawdown for target account so UI never flashes 0
    const [accStateRes, mt5AccRes, dailyRes] = await Promise.all([
      db.execute(sql`SELECT initial_balance, max_equity_peak, overall_drawdown FROM account_states WHERE mt5_login = ${targetLogin} LIMIT 1`),
      db.execute(sql`SELECT equity, balance FROM mt5_accounts WHERE login = ${targetLogin} LIMIT 1`),
      db.execute(sql`SELECT start_equity, current_equity, max_drawdown_percent, trades_today FROM daily_metrics WHERE mt5_login = ${targetLogin} AND trading_date = (NOW() AT TIME ZONE 'Asia/Karachi')::date LIMIT 1`),
    ]);

    const accRow = ((accStateRes as any).rows || [])[0];
    const mt5Row = ((mt5AccRes as any).rows || [])[0];
    const dmRow = ((dailyRes as any).rows || [])[0];

    const restoredEquity = mt5Row?.equity != null ? Number(mt5Row.equity) : (dmRow?.current_equity != null ? Number(dmRow.current_equity) : null);
    const restoredInitial = accRow?.initial_balance != null ? Number(accRow.initial_balance) : (mt5Row?.balance != null ? Number(mt5Row.balance) : null);
    const restoredPeak = accRow?.max_equity_peak != null ? Number(accRow.max_equity_peak) : restoredInitial;
    const restoredOverallDd =
      restoredInitial != null && restoredInitial > 0 && restoredEquity != null
        ? Number(Math.max(0, ((restoredInitial - restoredEquity) / restoredInitial) * 100).toFixed(2))
        : (accRow?.overall_drawdown != null ? Number(accRow.overall_drawdown) : null);
    const restoredDailyDd = dmRow?.max_drawdown_percent != null ? Number(dmRow.max_drawdown_percent) : null;
    const restoredTradesToday = dmRow?.trades_today != null ? Number(dmRow.trades_today) : null;

    await db.execute(sql`
      UPDATE bot_state
      SET target_login     = ${targetLogin},
          mt5_login        = ${targetLogin},
          equity           = COALESCE(${restoredEquity != null ? restoredEquity.toFixed(2) : null}::numeric, equity),
          initial_balance  = COALESCE(${restoredInitial != null ? restoredInitial.toFixed(2) : null}::numeric, initial_balance),
          max_equity_peak  = COALESCE(${restoredPeak != null ? restoredPeak.toFixed(2) : null}::numeric, max_equity_peak),
          overall_drawdown = COALESCE(${restoredOverallDd != null ? restoredOverallDd.toFixed(2) : null}::numeric, overall_drawdown),
          drawdown_percent = COALESCE(${restoredDailyDd != null ? restoredDailyDd.toFixed(2) : null}::numeric, drawdown_percent),
          trades_today     = COALESCE(${restoredTradesToday}::integer, trades_today),
          updated_at       = NOW()
      WHERE id = (SELECT MIN(id) FROM bot_state);
    `);
    await db.execute(sql`
      UPDATE mt5_accounts
      SET is_active = (login = ${targetLogin})
    `);
    void broadcastDashboardNow();
    return res.json({ status: "success", targetLogin, message: `Switch command queued for Account #${login}` });
  } catch (err) {
    console.error("Failed to queue account switch:", err);
    return res.status(500).json({ error: "Failed to queue account switch" });
  }
});

export default router;
