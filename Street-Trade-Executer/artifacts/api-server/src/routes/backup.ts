import { Router } from "express";
import { db } from "@workspace/db";
import { botStateTable, tradesTable, signalsTable, fvgZonesTable, scannedAssetsTable, dailyMetricsTable } from "@workspace/db";

const router = Router();

router.get("/backup/export", async (req, res) => {
  try {
    const [botState, trades, signals, fvgZones, scannedAssets, dailyMetrics] = await Promise.all([
      db.select().from(botStateTable),
      db.select().from(tradesTable),
      db.select().from(signalsTable),
      db.select().from(fvgZonesTable),
      db.select().from(scannedAssetsTable),
      db.select().from(dailyMetricsTable),
    ]);

    const backupData = {
      version: 1,
      timestamp: new Date().toISOString(),
      botState,
      trades,
      signals,
      fvgZones,
      scannedAssets,
      dailyMetrics
    };

    res.setHeader("Content-Disposition", "attachment; filename=jane_street_backup.json");
    res.setHeader("Content-Type", "application/json");
    return res.send(JSON.stringify(backupData, null, 2));
  } catch (err) {
    req.log.error({ err }, "Failed to export backup");
    return res.status(500).json({ error: "Failed to export backup" });
  }
});

router.post("/backup/import", async (req, res) => {
  try {
    const backupData = req.body;
    if (!backupData || backupData.version !== 1) {
      return res.status(400).json({ error: "Invalid backup file format or missing version" });
    }

    const { botState, trades, signals, fvgZones, scannedAssets, dailyMetrics } = backupData;

    // Purge tables in correct relational order
    await db.delete(tradesTable);
    await db.delete(signalsTable);
    await db.delete(fvgZonesTable);
    await db.delete(scannedAssetsTable);
    await db.delete(dailyMetricsTable);
    await db.delete(botStateTable);

    // Re-insert data
    if (botState && botState.length > 0) {
      await db.insert(botStateTable).values(botState);
    }
    if (signals && signals.length > 0) {
      await db.insert(signalsTable).values(signals);
    }
    if (trades && trades.length > 0) {
      await db.insert(tradesTable).values(trades);
    }
    if (fvgZones && fvgZones.length > 0) {
      await db.insert(fvgZonesTable).values(fvgZones);
    }
    if (scannedAssets && scannedAssets.length > 0) {
      await db.insert(scannedAssetsTable).values(scannedAssets);
    }
    if (dailyMetrics && dailyMetrics.length > 0) {
      await db.insert(dailyMetricsTable).values(dailyMetrics);
    }

    return res.json({ success: true, message: "Backup restored successfully!" });
  } catch (err) {
    req.log.error({ err }, "Failed to restore backup");
    return res.status(500).json({ error: "Failed to restore backup" });
  }
});

export default router;
