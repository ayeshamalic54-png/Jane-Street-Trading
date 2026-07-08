import { Router } from "express";
import { db } from "@workspace/db";
import { botStateTable } from "@workspace/db";
import { UpdateConfigBody } from "@workspace/api-zod";
import { sql } from "drizzle-orm";

const router = Router();

router.get("/config", async (req, res) => {
  try {
    const rows = await db.select().from(botStateTable).limit(1);
    const state = rows[0];
    const pair = state?.activePair ?? "EURUSD/GBPUSD";
    const parts = pair.split("/");

    res.json({
      activePair: pair,
      symbolA: parts[0] ?? "EURUSD",
      symbolB: parts[1] ?? "GBPUSD",
      zEntryThreshold: Number(state?.zEntryThreshold ?? 2.0),
      maxDailyTrades: 3,
      maxDailyLossPercent: 4.2,
      requireSmcConfluence: state?.smcEnabled ?? true,
      slPips: Number(state?.slPips ?? 10),
      tpPips: Number(state?.tpPips ?? 20),
      smcEnabled: state?.smcEnabled ?? true,
      autoExecute: state?.autoExecute ?? true,
      cryptoEnabled: state?.cryptoEnabled ?? true,
      metalsEnabled: state?.metalsEnabled ?? true,
      forexEnabled: state?.forexEnabled ?? true,
      indicesEnabled: state?.indicesEnabled ?? true,
      riskLimitsEnabled: state?.riskLimitsEnabled ?? true,
    });
  } catch (err) {
    req.log.error({ err }, "Failed to get config");
    res.status(500).json({ error: "Failed to get config" });
  }
});

router.post("/config", async (req, res) => {
  try {
    const parsed = UpdateConfigBody.safeParse(req.body);
    if (!parsed.success) {
      res.status(400).json({ error: "Invalid request body" });
      return;
    }

    const { activePair, slPips, tpPips, zEntryThreshold, smcEnabled, autoExecute, cryptoEnabled, metalsEnabled, forexEnabled, indicesEnabled, riskLimitsEnabled } = parsed.data;
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

    await db.execute(
      sql`INSERT INTO bot_state (id, active_pair, sl_pips, tp_pips, z_entry_threshold, smc_enabled, auto_execute, crypto_enabled, metals_enabled, forex_enabled, indices_enabled, risk_limits_enabled, system_status, updated_at)
          SELECT 1, ${activePair}, ${(slPips ?? 10).toString()}, ${(tpPips ?? 20).toString()}, ${zEntry.toString()}, ${smcEnabled ?? true}, ${autoExec}, ${cryptoExec}, ${metalsExec}, ${forexExec}, ${indicesExec}, ${riskLimits}, 'BOT OFFLINE', NOW()
          WHERE NOT EXISTS (SELECT 1 FROM bot_state)`
    );

    await db.execute(
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
              updated_at   = NOW()
          WHERE id = (SELECT MIN(id) FROM bot_state)`
    );

    const updated = (await db.select().from(botStateTable).limit(1))[0];
    const updatedPair = updated?.activePair ?? activePair;
    const updatedParts = updatedPair.split("/");

    res.json({
      activePair: updatedPair,
      symbolA: updatedParts[0] ?? parts[0],
      symbolB: updatedParts[1] ?? parts[1],
      zEntryThreshold: Number(updated?.zEntryThreshold ?? zEntry),
      maxDailyTrades: 3,
      maxDailyLossPercent: 4.2,
      requireSmcConfluence: updated?.smcEnabled ?? true,
      slPips: Number(updated?.slPips ?? slPips ?? 10),
      tpPips: Number(updated?.tpPips ?? tpPips ?? 20),
      smcEnabled: updated?.smcEnabled ?? true,
      autoExecute: updated?.autoExecute ?? autoExec,
      cryptoEnabled: updated?.cryptoEnabled ?? cryptoExec,
      metalsEnabled: updated?.metalsEnabled ?? metalsExec,
      forexEnabled: updated?.forexEnabled ?? forexExec,
      indicesEnabled: updated?.indicesEnabled ?? indicesExec,
      riskLimitsEnabled: updated?.riskLimitsEnabled ?? riskLimits,
    });
  } catch (err) {
    req.log.error({ err }, "Failed to update config");
    res.status(500).json({ error: "Failed to update config" });
  }
});

export default router;
