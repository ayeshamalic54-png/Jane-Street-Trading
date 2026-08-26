import { Router } from "express";
import { db, pool, botStateTable, tradesTable, signalsTable, fvgZonesTable, scannedAssetsTable, dailyMetricsTable, tradeCommandsTable } from "@workspace/db";

const router = Router();

router.get("/backup/export", async (req, res) => {
  try {
    const [botState, trades, signals, fvgZones, scannedAssets, dailyMetrics, tradeCommands] = await Promise.all([
      db.select().from(botStateTable),
      db.select().from(tradesTable),
      db.select().from(signalsTable),
      db.select().from(fvgZonesTable),
      db.select().from(scannedAssetsTable),
      db.select().from(dailyMetricsTable),
      db.select().from(tradeCommandsTable),
    ]);

    const backupData = {
      version: 1,
      timestamp: new Date().toISOString(),
      botState,
      trades,
      signals,
      fvgZones,
      scannedAssets,
      dailyMetrics,
      tradeCommands,
    };

    res.setHeader("Content-Disposition", `attachment; filename=forex_system_backup_${Date.now()}.json`);
    res.setHeader("Content-Type", "application/json");
    return res.send(JSON.stringify(backupData, null, 2));
  } catch (err) {
    req.log.error({ err }, "Failed to export backup");
    return res.status(500).json({ error: "Failed to export backup" });
  }
});

router.post("/backup/import", async (req, res) => {
  try {
    let backupData = req.body;

    if (typeof backupData === "string") {
      backupData = JSON.parse(backupData);
    }
    if (backupData?.data && typeof backupData.data === "object") {
      backupData = backupData.data;
    }

    if (!backupData || (backupData.version !== 1 && !backupData.botState)) {
      return res.status(400).json({ error: "Invalid backup file format" });
    }

    const { botState, trades, signals, fvgZones, scannedAssets, dailyMetrics, tradeCommands } = backupData;

    // Purge existing tables in dependency order
    await db.delete(tradeCommandsTable);
    await db.delete(tradesTable);
    await db.delete(signalsTable);
    await db.delete(fvgZonesTable);
    await db.delete(scannedAssetsTable);
    await db.delete(dailyMetricsTable);
    await db.delete(botStateTable);

    // Sanitize and Insert botState
    if (Array.isArray(botState) && botState.length > 0) {
      const formattedBotState = botState.map((b: any) => ({
        ...b,
        id: Number(b.id),
        lastHeartbeat: b.lastHeartbeat ? new Date(b.lastHeartbeat) : null,
        updatedAt: b.updatedAt ? new Date(b.updatedAt) : new Date(),
      }));
      await db.insert(botStateTable).values(formattedBotState);
    }

    // Sanitize and Insert signals
    if (Array.isArray(signals) && signals.length > 0) {
      const formattedSignals = signals.map((s: any) => ({
        ...s,
        id: Number(s.id),
        timestamp: s.timestamp ? new Date(s.timestamp) : new Date(),
      }));
      await db.insert(signalsTable).values(formattedSignals);
    }

    // Sanitize and Insert trades
    if (Array.isArray(trades) && trades.length > 0) {
      const formattedTrades = trades.map((t: any) => ({
        ...t,
        ticket: Number(t.ticket),
        entryTime: t.entryTime ? new Date(t.entryTime) : new Date(),
        closeTime: t.closeTime ? new Date(t.closeTime) : null,
      }));
      await db.insert(tradesTable).values(formattedTrades);
    }

    // Sanitize and Insert fvgZones
    if (Array.isArray(fvgZones) && fvgZones.length > 0) {
      const formattedZones = fvgZones.map((z: any) => ({
        ...z,
        id: Number(z.id),
        createdAt: z.createdAt ? new Date(z.createdAt) : new Date(),
        updatedAt: z.updatedAt ? new Date(z.updatedAt) : new Date(),
      }));
      await db.insert(fvgZonesTable).values(formattedZones);
    }

    // Sanitize and Insert scannedAssets
    if (Array.isArray(scannedAssets) && scannedAssets.length > 0) {
      const formattedAssets = scannedAssets.map((a: any) => ({
        ...a,
        id: Number(a.id),
        updatedAt: a.updatedAt ? new Date(a.updatedAt) : new Date(),
      }));
      await db.insert(scannedAssetsTable).values(formattedAssets);
    }

    // Sanitize and Insert dailyMetrics
    if (Array.isArray(dailyMetrics) && dailyMetrics.length > 0) {
      const formattedMetrics = dailyMetrics.map((m: any) => ({
        ...m,
        id: Number(m.id),
        tradingDate: m.tradingDate ? String(m.tradingDate).split("T")[0] : String(new Date().toISOString().split("T")[0]),
        updatedAt: m.updatedAt ? new Date(m.updatedAt) : new Date(),
      }));
      await db.insert(dailyMetricsTable).values(formattedMetrics);
    }

    // Sanitize and Insert tradeCommands
    if (Array.isArray(tradeCommands) && tradeCommands.length > 0) {
      const formattedCmds = tradeCommands.map((c: any) => ({
        ...c,
        id: Number(c.id),
        createdAt: c.createdAt ? new Date(c.createdAt) : new Date(),
        executedAt: c.executedAt ? new Date(c.executedAt) : null,
      }));
      await db.insert(tradeCommandsTable).values(formattedCmds);
    }

    // Reset PostgreSQL auto-increment sequences so future entries don't throw unique constraint errors
    const resetSequences = [
      "SELECT setval('bot_state_id_seq', COALESCE((SELECT MAX(id) FROM bot_state), 1), false);",
      "SELECT setval('signals_id_seq', COALESCE((SELECT MAX(id) FROM signals), 1), false);",
      "SELECT setval('fvg_zones_id_seq', COALESCE((SELECT MAX(id) FROM fvg_zones), 1), false);",
      "SELECT setval('trade_commands_id_seq', COALESCE((SELECT MAX(id) FROM trade_commands), 1), false);"
    ];
    for (const query of resetSequences) {
      await pool.query(query);
    }

    return res.json({ success: true, message: "Backup restored successfully!" });
  } catch (err: any) {
    req.log.error({ err }, "Failed to restore backup");
    return res.status(500).json({ error: err?.message || "Failed to restore backup" });
  }
});

export default router;
