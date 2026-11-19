import { WebSocketServer, WebSocket } from "ws";
import type http from "http";
import { db } from "@workspace/db";
import { botStateTable, tradesTable, fvgZonesTable, scannedAssetsTable, smcTelemetryTable } from "@workspace/db";
import { desc, eq } from "drizzle-orm";
import { logger } from "./logger";
import { ensureSessionGuardColumns, extractSessionGuardFields } from "./sessionGuard";
import { buildEnrichedScannedAssets, formatSmcTelemetryPayload } from "./smcTelemetrySummary";

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
  await ensureSessionGuardColumns();
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

  // Bot state & SMC Telemetry fetched fresh (every 1s)
  const [botStateRows, scannedAssetsRows, smcTelRows] = await Promise.all([
    db.select().from(botStateTable).where(eq(botStateTable.id, 1)).limit(1),
    db.select().from(scannedAssetsTable).orderBy(desc(scannedAssetsTable.winRate)),
    db.select().from(smcTelemetryTable).orderBy(desc(smcTelemetryTable.updatedAt)),
  ]);

  const botState = botStateRows[0];
  const forexOn = botState?.forexEnabled ?? true;
  const metalsOn = botState?.metalsEnabled ?? true;
  const indicesOn = botState?.indicesEnabled ?? true;
  const stocksOn = botState?.stocksEnabled ?? true;

  const isSymbolEnabled = (sym: string) => {
    const s = (sym || "").toUpperCase();
    if (s.includes("USDT") || s.includes("US500") || s.includes("SPX")) return false;
    if (s.includes("XAU") || s.includes("XAG") || s.includes("XPT") || s.includes("XPD")) return metalsOn;
    if (s.includes("AAPL") || s.includes("MSFT") || s.includes("GOOGL") || s.includes("TSLA") || s.includes("NVDA") || s.includes("AMD") || s.includes("META") || s.includes("AMZN")) return stocksOn;
    if (["US30", "DJ30", "WS30", "DOW", "DJI", "NAS100", "US100", "NDX", "GER30", "UK100", "USTEC"].some((k) => s.includes(k))) return indicesOn;
    return forexOn;
  };

  const enabledTelRows = (smcTelRows || []).filter((r: any) => isSymbolEnabled(r.symbolPair));
  const smcTelemetryAll: Record<string, any> = {};
  for (const r of enabledTelRows) {
    const formatted = formatSmcTelemetryPayload(r);
    if (formatted) smcTelemetryAll[r.symbolPair] = formatted;
  }
  const telRow = enabledTelRows[0] ?? smcTelRows[0];
  const smcTelemetryPayload = formatSmcTelemetryPayload(telRow);

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
      entryPrice: Number(t.entryPrice),
      current: Number(t.closePrice ?? t.entryPrice),
      profit: Number(t.profit ?? 0),
      comment: t.comment ?? "",
      sl: t.sl != null ? Number(t.sl) : 0,
      tp: t.tp != null ? Number(t.tp) : 0,
    }));

  const rawPair = botState?.activePair ?? "EURUSD/GBPUSD";
  const pairSymA = (rawPair.split(/[\/\s]/)[0] || "").toUpperCase();
  const isRawPairEnabled = isSymbolEnabled(pairSymA);

  let effectiveCurrentPair = rawPair;
  if (!isRawPairEnabled) {
    if (metalsOn) effectiveCurrentPair = "XAUUSD/XAGUSD";
    else if (indicesOn) effectiveCurrentPair = "US30/NAS100";
    else if (stocksOn) effectiveCurrentPair = "AAPL/MSFT";
    else if (forexOn) effectiveCurrentPair = "EURUSD/GBPUSD";
  }

  const activeZones = (cachedZoneRows || [])
    .filter((z: any) => isSymbolEnabled(z.symbol))
    .map((z: any) => {
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
    currentPair: effectiveCurrentPair,
    lastUpdate: botState?.updatedAt?.toISOString() ?? null,
    equity: Number(botState?.equity ?? 0),
    drawdownPercent: Number(botState?.drawdownPercent ?? 0),
    floatingProfit: Number(botState?.floatingProfit ?? 0),
    zScore: Number(botState?.zScore ?? 0),
    hedgeRatio: Number(botState?.hedgeRatio ?? 0),
    obiA: Number(botState?.obiA ?? 0),
    obiB: Number(botState?.obiB ?? 0),
    tradesToday: botState?.tradesToday ?? 0,
    maxTrades: Number(botState?.maxTrades ?? 3),
    initialBalance: Number(botState?.initialBalance ?? 100000.00),
    overallDrawdown: Number(botState?.overallDrawdown ?? 0.00),
    maxEquityPeak: Number(botState?.maxEquityPeak ?? 0.00),
    mt5Login: botState?.mt5Login ?? 0,
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
    scannedAssets: buildEnrichedScannedAssets(scannedAssetsRows || [], smcTelRows || [], isSymbolEnabled),
    botOnline: isOnline,
    autoExecute: botState?.autoExecute ?? true,
    cryptoEnabled: botState?.cryptoEnabled ?? true,
    metalsEnabled: botState?.metalsEnabled ?? true,
    forexEnabled: botState?.forexEnabled ?? true,
    indicesEnabled: botState?.indicesEnabled ?? true,
    stocksEnabled: botState?.stocksEnabled ?? true,
    halt_drawdown_limit: Number(botState?.haltDrawdownLimit ?? (botState as any)?.halt_drawdown_limit ?? 0.83),
    max_drawdown_limit: Number(botState?.maxDrawdownLimit ?? (botState as any)?.max_drawdown_limit ?? 3.30),
    ...extractSessionGuardFields(botState),
    smcTelemetry: smcTelemetryPayload,
    smcTelemetryAll,
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

export function broadcastDashboardNow() {
  return broadcastAll();
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
