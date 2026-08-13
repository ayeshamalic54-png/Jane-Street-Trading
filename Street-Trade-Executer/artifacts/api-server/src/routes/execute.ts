import { Router } from "express";
import { db } from "@workspace/db";
import { tradeCommandsTable } from "@workspace/db";
import { ExecuteTradeBody } from "@workspace/api-zod";
import { eq } from "drizzle-orm";

const router = Router();

router.post("/execute-trade", async (req, res) => {
  try {
    const parsed = ExecuteTradeBody.safeParse(req.body);
    if (!parsed.success) {
      res.status(400).json({ error: "Invalid request", details: parsed.error.flatten() });
      return;
    }

    const { symbol, direction, lots, slPips, tpPips, comment } = parsed.data;

    const [cmd] = await db
      .insert(tradeCommandsTable)
      .values({
        symbol: symbol.toUpperCase(),
        direction,
        lots: lots.toString(),
        slPips: slPips?.toString() ?? null,
        tpPips: tpPips?.toString() ?? null,
        comment: comment ?? `Manual ${direction} ${symbol}`,
        status: "PENDING",
      })
      .returning();

    res.json({
      commandId: cmd!.id,
      symbol: cmd!.symbol,
      direction: cmd!.direction,
      lots: Number(cmd!.lots),
      status: cmd!.status,
      message: `Trade command queued — bot will execute within 2-3 seconds when online`,
    });
  } catch (err) {
    req.log.error({ err }, "Failed to queue trade command");
    res.status(500).json({ error: "Failed to queue trade command" });
  }
});

router.get("/commands/pending", async (req, res) => {
  try {
    const rows = await db
      .select()
      .from(tradeCommandsTable)
      .where(eq(tradeCommandsTable.status, "PENDING"))
      .limit(10);

    res.json(
      rows.map((c) => ({
        id: c.id,
        symbol: c.symbol,
        direction: c.direction,
        lots: Number(c.lots),
        slPips: c.slPips != null ? Number(c.slPips) : null,
        tpPips: c.tpPips != null ? Number(c.tpPips) : null,
        comment: c.comment ?? null,
        status: c.status,
        createdAt: c.createdAt?.toISOString() ?? new Date().toISOString(),
      }))
    );
  } catch (err) {
    req.log.error({ err }, "Failed to get pending commands");
    res.status(500).json({ error: "Failed to get pending commands" });
  }
});

router.post("/commands/:id/ack", async (req, res) => {
  try {
    const id = parseInt(req.params["id"]!);
    const { status, errorMsg } = req.body as { status: "EXECUTED" | "FAILED"; errorMsg?: string };

    await db
      .update(tradeCommandsTable)
      .set({
        status,
        executedAt: new Date(),
        errorMsg: errorMsg ?? null,
      })
      .where(eq(tradeCommandsTable.id, id));

    res.json({ ok: true });
  } catch (err) {
    req.log.error({ err }, "Failed to ack command");
    res.status(500).json({ error: "Failed to ack command" });
  }
});

export default router;
