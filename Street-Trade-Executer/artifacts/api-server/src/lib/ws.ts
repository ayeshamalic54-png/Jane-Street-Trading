import { WebSocketServer, WebSocket } from "ws";
import type http from "http";
import { db } from "@workspace/db";
import { botStateTable, tradesTable, fvgZonesTable, scannedAssetsTable } from "@workspace/db";
import { desc } from "drizzle-orm";
import { logger } from "./logger";

let wss: WebSocketServer | null = null;

const ZONE_META: Record<string, { label: string; bullish: boolean }> = {
  bullish_ob:      { label: "OB",      bullish: true },
  bearish_ob:      { label: "OB",      bullish: false },
  bullish_fvg:     { label: "FVG",     bullish: true },
  bearish_fvg:     { label: "FVG",     bullish: false },
  bullish_breaker: { label: "BREAKER", bullish: true },
  bearish_breaker: { label: "BREAKER", bullish: false },
  bullish_ifvg:    { label: "iFVG",    bullish: true },
  bearish_ifvg:    { label: "iFVG",    bullish: false },
};

export function initWsServer(server: http.Server) {
  wss = new WebSocketServer({ server, path: "/api/ws" });

  wss.on("connection", (ws) => {
    logger.info("WS client connected");
    ws.on("close", () => logger.info("WS client disconnected"));
    ws.on("error", (err) => logger.warn({ err }, "WS client error"));
    void sendSnapshot(ws);
  });

  setInterval(() => { void broadcastAll(); }, 1000);
  logger.info("WebSocket server active on /api/ws — broadcasting every 1s");
}

let cachedRecentTrades: any = null;
let lastTradesFetch = 0;

let cachedZoneRows: any = null;
let lastZonesFetch = 0;

async function buildDashboardPayload() {
  const now = Date.now();

  // Fetch recent trades every 3 seconds
  if (!cachedRecentTrades || now - lastTradesFetch > 3000) {
    cachedRecentTrades = await db.select().from(tradesTable).orderBy(desc(tradesTable.entryTime)).limit(5);
    lastTradesFetch = now;
  }

  // Fetch FVG zones every 10 seconds
  if (!cachedZoneRows || now - lastZonesFetch > 10000) {
    cachedZoneRows = await db.select().from(fvgZonesTable).orderBy(desc(fvgZonesTable.updatedAt)).limit(30);
    lastZonesFetch = now;
  }

  // Bot state is always fetched fresh (every 1s) to show live Z-score
  const [botStateRows, scannedAssetsRows] = await Promise.all([
    db.select().from(botStateTable).limit(1),
    db.select().from(scannedAssetsTable).orderBy(desc(scannedAssetsTable.winRate)),
  ]);

  const botState = botStateRows[0];
  const isOnline =
    botState?.lastHeartbeat != null &&
    Date.now() - new Date(botState.lastHeartbeat).getTime() < 30_000;

  const openPositions = cachedRecentTrades
    .filter((t: any) => t.status === "OPEN")
    .map((t: any) => ({
      ticket: Number(t.ticket),
      symbol: t.symbol,
      type: t.orderType,
      lots: Number(t.lots),
      entry: Number(t.entryPrice),
      current: Number(t.closePrice ?? t.entryPrice),
      profit: Number(t.profit ?? 0),
      comment: t.comment ?? "",
    }));

  const activeZones = cachedZoneRows.map((z: any) => {
    const meta = ZONE_META[z.zoneType] ?? { label: z.zoneType.toUpperCase(), bullish: true };
    const dir = meta.bullish ? "BULLISH" : "BEARISH";
    return {
      type: `${dir}_${meta.label}`,
      label: `${meta.bullish ? "🟢" : "🔴"} ${meta.label} · ${z.symbol}`,
      range: `${Number(z.lowPrice).toFixed(5)}–${Number(z.highPrice).toFixed(5)}`,
    };
  });

  return {
    systemStatus: botState?.systemStatus ?? "BOT OFFLINE",
    currentPair: botState?.activePair ?? "EURUSD/GBPUSD",
    lastUpdate: botState?.updatedAt?.toISOString() ?? null,
    equity: Number(botState?.equity ?? 0),
    drawdownPercent: Number(botState?.drawdownPercent ?? 0),
    floatingProfit: Number(botState?.floatingProfit ?? 0),
    zScore: Number(botState?.zScore ?? 0),
    hedgeRatio: Number(botState?.hedgeRatio ?? 0),
    obiA: Number(botState?.obiA ?? 0),
    obiB: Number(botState?.obiB ?? 0),
    tradesToday: botState?.tradesToday ?? 0,
    maxTrades: 3,
    activePositions: openPositions,
    recentTrades: cachedRecentTrades.map((t: any) => ({
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
    })),
    activeZones,
    scannedAssets: scannedAssetsRows.map((s: any) => ({
      symbolPair: s.symbolPair,
      priceA: Number(s.priceA ?? 0),
      priceB: Number(s.priceB ?? 0),
      winRate: Number(s.winRate ?? 50.0),
      zScore: Number(s.zScore ?? 0),
      action: s.action ?? "NONE",
    })),
    botOnline: isOnline,
    autoExecute: botState?.autoExecute ?? true,
  };
}

async function sendSnapshot(ws: WebSocket) {
  if (ws.readyState !== WebSocket.OPEN) return;
  try {
    const data = await buildDashboardPayload();
    ws.send(JSON.stringify({ type: "dashboard", data }));
  } catch (err) {
    logger.warn({ err }, "WS snapshot error");
  }
}

async function broadcastAll() {
  if (!wss) return;
  const clients = [...wss.clients].filter((c) => c.readyState === WebSocket.OPEN);
  if (!clients.length) return;
  try {
    const data = await buildDashboardPayload();
    const msg = JSON.stringify({ type: "dashboard", data });
    clients.forEach((c) => c.send(msg));
  } catch (err) {
    logger.warn({ err }, "WS broadcast error");
  }
}
