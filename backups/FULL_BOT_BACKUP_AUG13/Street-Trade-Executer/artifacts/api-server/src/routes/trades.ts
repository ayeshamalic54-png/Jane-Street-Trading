import { Router } from "express";
import { db } from "@workspace/db";
import { tradesTable } from "@workspace/db";
import { desc } from "drizzle-orm";
import { GetTradesQueryParams } from "@workspace/api-zod";

const router = Router();

router.get("/trades", async (req, res) => {
  try {
    const parsed = GetTradesQueryParams.safeParse(req.query);
    const limit = parsed.success ? (parsed.data.limit ?? 50) : 50;
    const status = parsed.success ? (parsed.data.status ?? "ALL") : "ALL";

    const rows = await db
      .select()
      .from(tradesTable)
      .orderBy(desc(tradesTable.entryTime))
      .limit(limit);

    const filtered = status === "ALL" ? rows : rows.filter((r) => r.status === status);

    res.json(
      filtered.map((t) => ({
        ticket: Number(t.ticket),
        symbol: t.symbol,
        orderType: t.orderType,
        lots: Number(t.lots),
        entryPrice: Number(t.entryPrice),
        closePrice: t.closePrice != null ? Number(t.closePrice) : null,
        profit: t.profit != null ? Number(t.profit) : null,
        entryTime: t.entryTime.toISOString(),
        closeTime: t.closeTime?.toISOString() ?? null,
        status: t.status,
        comment: t.comment ?? null,
      }))
    );
  } catch (err) {
    req.log.error({ err }, "Failed to get trades");
    res.status(500).json({ error: "Failed to get trades" });
  }
});

export default router;
