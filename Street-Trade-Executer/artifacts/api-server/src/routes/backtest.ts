import { Router } from "express";
import { OhlcBar, SYMBOL_SPECS, resolveSymbolSpec, runSmcBacktest } from "../lib/smcEngine";

const router = Router();

async function fetchYahooOhlc(ticker: string, interval: "5m" | "15m", range: "5d" | "1mo"): Promise<OhlcBar[]> {
  const hosts = ["query1.finance.yahoo.com", "query2.finance.yahoo.com"];
  let lastError = "Unknown fetch error";

  for (const host of hosts) {
    try {
      const url = `https://${host}/v8/finance/chart/${encodeURIComponent(ticker)}?interval=${interval}&range=${range}`;
      const res = await fetch(url, {
        headers: { "User-Agent": "Mozilla/5.0" },
        signal: AbortSignal.timeout(10000),
      });
      if (!res.ok) {
        lastError = `Market feed returned HTTP ${res.status}`;
        continue;
      }
      const json = (await res.json()) as any;
      const result = json?.chart?.result?.[0];
      if (!result) {
        lastError = json?.chart?.error?.description || "Empty market feed response";
        continue;
      }

      const ts: Array<number | null> = result.timestamp || [];
      const q = result.indicators?.quote?.[0] || {};
      const opens: Array<number | null> = q.open || [];
      const highs: Array<number | null> = q.high || [];
      const lows: Array<number | null> = q.low || [];
      const closes: Array<number | null> = q.close || [];

      const bars: OhlcBar[] = [];
      const len = Math.min(ts.length, opens.length, highs.length, lows.length, closes.length);
      for (let i = 0; i < len; i++) {
        const t = ts[i];
        const o = opens[i];
        const h = highs[i];
        const l = lows[i];
        const c = closes[i];
        if (
          typeof t === "number" &&
          typeof o === "number" &&
          typeof h === "number" &&
          typeof l === "number" &&
          typeof c === "number" &&
          Number.isFinite(o) &&
          Number.isFinite(h) &&
          Number.isFinite(l) &&
          Number.isFinite(c) &&
          o > 0 &&
          h > 0 &&
          l > 0 &&
          c > 0 &&
          h >= l
        ) {
          bars.push({ time: t * 1000, open: o, high: h, low: l, close: c });
        }
      }
      if (bars.length >= 30) {
        return bars;
      }
      lastError = `Insufficient valid ${interval} candles (${bars.length})`;
    } catch (err) {
      lastError = (err as Error).message;
    }
  }
  throw new Error(`Failed to fetch ${ticker} (${interval}): ${lastError}`);
}

router.get("/backtest/symbols", (_req, res) => {
  const symbols = Object.values(SYMBOL_SPECS).map((s) => ({
    symbol: s.symbol,
    label: s.label,
    category: s.category,
    digits: s.digits,
    defaultMaxSlDist: s.defaultMaxSlDist,
  }));
  res.json({ symbols });
});

router.post("/backtest", async (req, res) => {
  try {
    const rawSymbol = String(req.body?.symbol ?? req.body?.symbolA ?? "XAUUSD");
    const spec = resolveSymbolSpec(rawSymbol);

    const lookbackDays = Math.min(30, Math.max(3, Number(req.body?.lookbackDays ?? 14) || 14));
    const lotSize = Math.min(10, Math.max(0.01, Number(req.body?.lotSize ?? 0.07) || 0.07));
    const initialBalance = Math.max(100, Number(req.body?.initialBalance ?? 10000) || 10000);
    const maxSlDist = Math.max(
      spec.digits <= 3 ? 0.05 : 0.0005,
      Number(req.body?.maxSlDist ?? spec.defaultMaxSlDist) || spec.defaultMaxSlDist
    );
    const minRrr = Math.min(5.0, Math.max(1.0, Number(req.body?.minRrr ?? 1.85) || 1.85));
    const sessionFilterEnabled = req.body?.sessionFilterEnabled !== undefined ? Boolean(req.body.sessionFilterEnabled) : true;
    const breakevenEnabled = req.body?.breakevenEnabled !== undefined ? Boolean(req.body.breakevenEnabled) : true;
    const smartRiskCapEnabled = req.body?.smartRiskCapEnabled !== undefined ? Boolean(req.body.smartRiskCapEnabled) : true;

    const range: "5d" | "1mo" = lookbackDays <= 5 ? "5d" : "1mo";
    const [m5Bars, m15Bars] = await Promise.all([
      fetchYahooOhlc(spec.yahooTicker, "5m", range),
      fetchYahooOhlc(spec.yahooTicker, "15m", "1mo"),
    ]);

    if (m5Bars.length < 100 || m15Bars.length < 30) {
      res.status(400).json({ error: `Insufficient historical OHLC candles for ${spec.symbol}` });
      return;
    }

    const latestMs = m5Bars[m5Bars.length - 1]!.time;
    const warmupFloor = m5Bars[Math.min(60, m5Bars.length - 1)]!.time;
    const requestedStart = latestMs - lookbackDays * 24 * 3600 * 1000;
    const startTimeMs = lookbackDays >= 28 ? warmupFloor : Math.max(warmupFloor, requestedStart);

    const results = runSmcBacktest({
      spec,
      m5Bars,
      m15Bars,
      startTimeMs,
      initialBalance,
      lotSize,
      maxSlDist,
      minRrr,
      sessionFilterEnabled,
      breakevenEnabled,
      smartRiskCapEnabled,
      riskCapUsd: 52.0,
      beTriggerUsd: 50.0,
    });

    res.json({
      ...results,
      lookbackDays,
      lotSize,
      maxSlDist,
      minRrr,
      sessionFilterEnabled,
      breakevenEnabled,
      smartRiskCapEnabled,
      barsScannedM5: m5Bars.length,
      barsScannedM15: m15Bars.length,
    });
  } catch (err) {
    req.log?.error?.({ err }, "Failed to run Pure SMC backtest");
    const msg = (err as Error).message || "Backtest failed";
    const isValidation = msg.includes("Crypto") || msg.includes("Unsupported");
    res.status(isValidation ? 400 : 500).json({ error: msg });
  }
});

export default router;
