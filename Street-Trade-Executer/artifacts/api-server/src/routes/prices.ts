import { Router } from "express";
import { db } from "@workspace/db";
import { scannedAssetsTable } from "@workspace/db";

const router = Router();

const FOREX_SYMBOLS = [
  { display: "EURUSD", base: "EUR" },
  { display: "GBPUSD", base: "GBP" },
  { display: "USDJPY", base: "USD", quote: "JPY" },
  { display: "USDCHF", base: "USD", quote: "CHF" },
  { display: "AUDUSD", base: "AUD" },
  { display: "NZDUSD", base: "NZD" },
  { display: "USDCAD", base: "USD", quote: "CAD" },
  { display: "EURGBP", base: "EUR", quote: "GBP" },
  { display: "EURJPY", base: "EUR", quote: "JPY" },
  { display: "GBPJPY", base: "GBP", quote: "JPY" },
];

async function fetchBinanceFuturesPrices(): Promise<Array<{
  symbol: string;
  price: number;
  change24h: number | null;
  changePct24h: number | null;
  category: string;
  source: string;
  updatedAt: string;
}>> {
  const result: Array<{
    symbol: string;
    price: number;
    change24h: number | null;
    changePct24h: number | null;
    category: string;
    source: string;
    updatedAt: string;
  }> = [];
  try {
    const resp = await fetch(
      "https://fapi.binance.com/fapi/v1/ticker/24hr",
      { signal: AbortSignal.timeout(6000) }
    );
    if (!resp.ok) return result;
    const data = (await resp.json()) as Array<{
      symbol: string;
      lastPrice: string;
      priceChange: string;
      priceChangePercent: string;
    }>;
    const nowStr = new Date().toISOString();
    for (const item of data) {
      if (item.symbol.endsWith("USDT")) {
        result.push({
          symbol: item.symbol,
          price: parseFloat(item.lastPrice) || 0,
          change24h: parseFloat(item.priceChange) || null,
          changePct24h: parseFloat(item.priceChangePercent) || null,
          category: "crypto",
          source: "Binance Futures",
          updatedAt: nowStr,
        });
      }
    }
  } catch {
    // silent fallback
  }
  return result;
}

async function fetchForexPrices(): Promise<Map<string, number>> {
  const result = new Map<string, number>();
  try {
    const resp = await fetch(
      "https://api.frankfurter.app/latest?from=USD&to=EUR,GBP,JPY,CHF,AUD,NZD,CAD",
      { signal: AbortSignal.timeout(4000) }
    );
    if (!resp.ok) return result;
    const data = (await resp.json()) as { rates: Record<string, number> };
    const rates = data.rates;
    result.set("EURUSD", rates["EUR"] ? rates["EUR"] : 0);
    result.set("GBPUSD", rates["GBP"] ? rates["GBP"] : 0);
    result.set("USDJPY", rates["JPY"] ?? 0);
    result.set("USDCHF", rates["CHF"] ?? 0);
    result.set("AUDUSD", rates["AUD"] ? rates["AUD"] : 0);
    result.set("NZDUSD", rates["NZD"] ? rates["NZD"] : 0);
    result.set("USDCAD", rates["CAD"] ?? 0);
    if (rates["EUR"] && rates["GBP"]) result.set("EURGBP", rates["GBP"] / rates["EUR"]);
    if (rates["EUR"] && rates["JPY"]) result.set("EURJPY", rates["JPY"] / rates["EUR"]);
    if (rates["GBP"] && rates["JPY"]) result.set("GBPJPY", rates["JPY"] / rates["GBP"]);
  } catch {
    // silent fallback
  }
  return result;
}

router.get("/prices", async (req, res) => {
  try {
    const category = (req.query["category"] as string) ?? "all";
    const prices: Array<{
      symbol: string;
      price: number;
      change24h: number | null;
      changePct24h: number | null;
      category: string;
      source: string;
      updatedAt: string;
    }> = [];

    const seenSymbols = new Set<string>();

    // 1. Fetch live prices from database scanned_assets
    try {
      const dbAssets = await db.select().from(scannedAssetsTable);
      for (const asset of dbAssets) {
        const parts = asset.symbolPair.split('/');
        if (parts.length === 2) {
          const priceA = Number(asset.priceA ?? 0);
          const priceB = Number(asset.priceB ?? 0);
          
          // Determine categories
          const getCategoryOfSymbol = (sym: string): string => {
            const s = sym.toUpperCase();
            if (s.endsWith("USDT") || ["BTC", "ETH", "SOL", "BNB", "AVAX", "XRP", "ADA", "DOGE", "MATIC"].some(x => s.includes(x))) return "crypto";
            if (s.includes("XAU") || s.includes("XAG")) return "metals";
            if (["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMD", "META", "AMZN"].some(x => s.includes(x))) return "stocks";
            if (["US500", "US30", "NAS100", "GER30", "UK100", "SPX", "DJI", "NDX"].some(x => s.includes(x))) return "indices";
            return "forex";
          };

          const catA = getCategoryOfSymbol(parts[0]);
          const catB = getCategoryOfSymbol(parts[1]);

          const pushSymbol = (sym: string, price: number, cat: string) => {
            if (price > 0 && !seenSymbols.has(sym)) {
              if (category === "all" || category === cat || (category === "stocks" && cat === "indices")) {
                prices.push({
                  symbol: sym,
                  price,
                  change24h: null,
                  changePct24h: null,
                  category: cat === "indices" ? "stocks" : cat, // Frontend expects 'stocks' category for indices
                  source: "MT5-Live",
                  updatedAt: asset.updatedAt?.toISOString() ?? new Date().toISOString(),
                });
                seenSymbols.add(sym);
              }
            }
          };

          pushSymbol(parts[0], priceA, catA);
          pushSymbol(parts[1], priceB, catB);
        }
      }
    } catch (dbErr) {
      // silent fallback
    }

    // 2. Fallbacks for remaining symbols if category matches
    if (category === "all" || category === "crypto") {
      const cryptoFutures = await fetchBinanceFuturesPrices();
      for (const item of cryptoFutures) {
        if (!seenSymbols.has(item.symbol)) {
          prices.push(item);
          seenSymbols.add(item.symbol);
        }
      }
    }

    if (category === "all" || category === "metals") {
      if (!seenSymbols.has("XAUUSD") || !seenSymbols.has("XAGUSD")) {
        let goldPrice = 0;
        let silverPrice = 0;
        let goldUpdatedAt = new Date().toISOString();
        let silverUpdatedAt = new Date().toISOString();

        try {
          const goldResp = await fetch("https://api.gold-api.com/price/XAU", { signal: AbortSignal.timeout(4000) });
          if (goldResp.ok) {
            const goldData = (await goldResp.json()) as { price: number; updatedAt?: string };
            goldPrice = Number(goldData.price);
            if (goldData.updatedAt) goldUpdatedAt = goldData.updatedAt;
          }
        } catch {}

        try {
          const silverResp = await fetch("https://api.gold-api.com/price/XAG", { signal: AbortSignal.timeout(4000) });
          if (silverResp.ok) {
            const silverData = (await silverResp.json()) as { price: number; updatedAt?: string };
            silverPrice = Number(silverData.price);
            if (silverData.updatedAt) silverUpdatedAt = silverData.updatedAt;
          }
        } catch {}

        if (!seenSymbols.has("XAUUSD") && goldPrice > 0) {
          prices.push({
            symbol: "XAUUSD",
            price: goldPrice,
            change24h: null,
            changePct24h: null,
            category: "metals",
            source: "GoldAPI",
            updatedAt: goldUpdatedAt,
          });
          seenSymbols.add("XAUUSD");
        }
        if (!seenSymbols.has("XAGUSD") && silverPrice > 0) {
          prices.push({
            symbol: "XAGUSD",
            price: silverPrice,
            change24h: null,
            changePct24h: null,
            category: "metals",
            source: "GoldAPI",
            updatedAt: silverUpdatedAt,
          });
          seenSymbols.add("XAGUSD");
        }
      }
    }

    if (category === "all" || category === "forex") {
      const symbolsNeeded = FOREX_SYMBOLS.filter(s => !seenSymbols.has(s.display));
      if (symbolsNeeded.length > 0) {
        const forexData = await fetchForexPrices();
        for (const { display } of symbolsNeeded) {
          const price = forexData.get(display) ?? 0;
          if (price > 0) {
            prices.push({
              symbol: display,
              price,
              change24h: null,
              changePct24h: null,
              category: "forex",
              source: "Frankfurter",
              updatedAt: new Date().toISOString(),
            });
            seenSymbols.add(display);
          }
        }
      }
    }

    if (category === "all" || category === "stocks") {
      // No mock stock fallback to ensure 100% real live data
    }

    res.json(prices);
  } catch (err) {
    req.log.error({ err }, "Failed to fetch prices");
    res.status(500).json({ error: "Failed to fetch prices" });
  }
});

export default router;
