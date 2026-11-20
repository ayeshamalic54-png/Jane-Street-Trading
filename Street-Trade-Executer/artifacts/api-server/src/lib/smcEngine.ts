/**
 * Pure Rule-Based SMC / ICT 9-Condition Historical Simulation Engine
 * For Metals (XAUUSD, XAGUSD) & Forex ONLY — Zero Crypto, Zero Z-Score.
 * Mirrors live smc_indicators.py, smc_strategy_engine.py & execution_bot.py rules.
 */

export interface OhlcBar {
  time: number; // UTC ms
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface SymbolSpec {
  symbol: string;
  label: string;
  category: "metals" | "forex" | "indices";
  yahooTicker: string;
  digits: number;
  contractSize: number;
  isQuoteJpy: boolean;
  isQuoteCadOrChf: boolean;
  isEurGbp: boolean;
  defaultMaxSlDist: number;
  m5MinSlDist: number;
  m1MinSlDist: number;
  protectedAnchorEnabled: boolean;
  staleCloseCheck: boolean;
  fvgRefinedSlEnabled: boolean;
  m15MinAmp: number;
  m15TargetMinAmp: number;
  m5MinAmp: number;
  minStructDepth: number;
  minPenetration: number;
  reclaimMaxDip: number;
  minFvgGap: number;
  maxZoneDist: number;
  minObDisp: number;
  mitTol: number;
  wickBuf: number;
  closeTol: number;
  sweepMargin: number;
  maxChaseDist: number;
  targetMinMove: number;
  frontRunBuf: number;
  beBuffer: number;
}

const FOREX_STANDARD_BASE = {
  category: "forex" as const,
  digits: 5,
  contractSize: 100000,
  isQuoteJpy: false,
  isQuoteCadOrChf: false,
  isEurGbp: false,
  defaultMaxSlDist: 0.005, // 50 pips
  m5MinSlDist: 0.0012, // 12 pips noise floor
  m1MinSlDist: 0.0,
  protectedAnchorEnabled: false,
  staleCloseCheck: true,
  fvgRefinedSlEnabled: false,
  m15MinAmp: 0.002,
  m15TargetMinAmp: 0.0012,
  m5MinAmp: 0.00015,
  minStructDepth: 0.001,
  minPenetration: 0.00003,
  reclaimMaxDip: 0.0008,
  minFvgGap: 0.00018,
  maxZoneDist: 0.008,
  minObDisp: 0.00025,
  mitTol: 0.0001,
  wickBuf: 0.0004,
  closeTol: 0.00015,
  sweepMargin: 0.0004,
  maxChaseDist: 0.001,
  targetMinMove: 0.0005,
  frontRunBuf: 0.00035,
  beBuffer: 0.0002,
};

const FOREX_JPY_BASE = {
  category: "forex" as const,
  digits: 3,
  contractSize: 100000,
  isQuoteJpy: true,
  isQuoteCadOrChf: false,
  isEurGbp: false,
  defaultMaxSlDist: 0.5, // 50 pips JPY
  m5MinSlDist: 0.12, // 12 pips JPY noise floor
  m1MinSlDist: 0.0,
  protectedAnchorEnabled: false,
  staleCloseCheck: true,
  fvgRefinedSlEnabled: false,
  m15MinAmp: 0.2,
  m15TargetMinAmp: 0.12,
  m5MinAmp: 0.015,
  minStructDepth: 0.1,
  minPenetration: 0.003,
  reclaimMaxDip: 0.08,
  minFvgGap: 0.018,
  maxZoneDist: 0.8,
  minObDisp: 0.025,
  mitTol: 0.01,
  wickBuf: 0.04,
  closeTol: 0.015,
  sweepMargin: 0.04,
  maxChaseDist: 0.1,
  targetMinMove: 0.05,
  frontRunBuf: 0.035,
  beBuffer: 0.02,
};

export const SYMBOL_SPECS: Record<string, SymbolSpec> = {
  XAUUSD: {
    symbol: "XAUUSD",
    label: "Gold (XAU/USD)",
    category: "metals",
    yahooTicker: "GC=F",
    digits: 2,
    contractSize: 100,
    isQuoteJpy: false,
    isQuoteCadOrChf: false,
    isEurGbp: false,
    defaultMaxSlDist: 10.0,
    m5MinSlDist: 0.0,
    m1MinSlDist: 0.0,
    protectedAnchorEnabled: true,
    staleCloseCheck: false,
    fvgRefinedSlEnabled: false,
    m15MinAmp: 3.0,
    m15TargetMinAmp: 2.5,
    m5MinAmp: 1.25,
    minStructDepth: 1.5,
    minPenetration: 0.1,
    reclaimMaxDip: 1.5,
    minFvgGap: 0.4,
    maxZoneDist: 18.0,
    minObDisp: 0.8,
    mitTol: 0.2,
    wickBuf: 0.75,
    closeTol: 0.25,
    sweepMargin: 0.5,
    maxChaseDist: 2.0,
    targetMinMove: 1.5,
    frontRunBuf: 1.1,
    beBuffer: 0.25,
  },
  XAGUSD: {
    symbol: "XAGUSD",
    label: "Silver (XAG/USD)",
    category: "metals",
    yahooTicker: "SI=F",
    digits: 3,
    contractSize: 5000,
    isQuoteJpy: false,
    isQuoteCadOrChf: false,
    isEurGbp: false,
    defaultMaxSlDist: 0.5,
    m5MinSlDist: 0.0,
    m1MinSlDist: 0.0,
    protectedAnchorEnabled: false,
    staleCloseCheck: false,
    fvgRefinedSlEnabled: false,
    m15MinAmp: 0.25,
    m15TargetMinAmp: 0.2,
    m5MinAmp: 0.08,
    minStructDepth: 0.1,
    minPenetration: 0.01,
    reclaimMaxDip: 0.1,
    minFvgGap: 0.04,
    maxZoneDist: 2.0,
    minObDisp: 0.06,
    mitTol: 0.02,
    wickBuf: 0.06,
    closeTol: 0.02,
    sweepMargin: 0.04,
    maxChaseDist: 0.15,
    targetMinMove: 0.12,
    frontRunBuf: 0.08,
    beBuffer: 0.02,
  },
  US30: {
    symbol: "US30",
    label: "Dow Jones 30 (US30)",
    category: "indices",
    yahooTicker: "YM=F",
    digits: 2,
    contractSize: 1,
    isQuoteJpy: false,
    isQuoteCadOrChf: false,
    isEurGbp: false,
    defaultMaxSlDist: 105.0,
    m5MinSlDist: 38.0,
    m1MinSlDist: 38.0,
    protectedAnchorEnabled: true,
    staleCloseCheck: false,
    fvgRefinedSlEnabled: false,
    m15MinAmp: 25.5,
    m15TargetMinAmp: 21.25,
    m5MinAmp: 10.6,
    minStructDepth: 12.75,
    minPenetration: 0.85,
    reclaimMaxDip: 12.75,
    minFvgGap: 3.4,
    maxZoneDist: 153.0,
    minObDisp: 6.8,
    mitTol: 1.7,
    wickBuf: 6.5,
    closeTol: 2.15,
    sweepMargin: 4.25,
    maxChaseDist: 17.0,
    targetMinMove: 12.75,
    frontRunBuf: 9.35,
    beBuffer: 2.15,
  },
  NAS100: {
    symbol: "NAS100",
    label: "Nasdaq 100 (NAS100)",
    category: "indices",
    yahooTicker: "NQ=F",
    digits: 2,
    contractSize: 1,
    isQuoteJpy: false,
    isQuoteCadOrChf: false,
    isEurGbp: false,
    defaultMaxSlDist: 85.0,
    m5MinSlDist: 0.0,
    m1MinSlDist: 38.0,
    protectedAnchorEnabled: false,
    staleCloseCheck: true,
    fvgRefinedSlEnabled: true,
    m15MinAmp: 25.5,
    m15TargetMinAmp: 21.25,
    m5MinAmp: 10.6,
    minStructDepth: 12.75,
    minPenetration: 0.85,
    reclaimMaxDip: 12.75,
    minFvgGap: 3.4,
    maxZoneDist: 153.0,
    minObDisp: 6.8,
    mitTol: 1.7,
    wickBuf: 6.5,
    closeTol: 2.15,
    sweepMargin: 4.25,
    maxChaseDist: 17.0,
    targetMinMove: 12.75,
    frontRunBuf: 9.35,
    beBuffer: 2.15,
  },
  EURUSD: { symbol: "EURUSD", label: "EUR/USD", yahooTicker: "EURUSD=X", ...FOREX_STANDARD_BASE },
  GBPUSD: { symbol: "GBPUSD", label: "GBP/USD", yahooTicker: "GBPUSD=X", ...FOREX_STANDARD_BASE },
  AUDUSD: { symbol: "AUDUSD", label: "AUD/USD", yahooTicker: "AUDUSD=X", ...FOREX_STANDARD_BASE },
  NZDUSD: { symbol: "NZDUSD", label: "NZD/USD", yahooTicker: "NZDUSD=X", ...FOREX_STANDARD_BASE },
  USDCAD: { symbol: "USDCAD", label: "USD/CAD", yahooTicker: "USDCAD=X", ...FOREX_STANDARD_BASE, isQuoteCadOrChf: true },
  USDCHF: { symbol: "USDCHF", label: "USD/CHF", yahooTicker: "USDCHF=X", ...FOREX_STANDARD_BASE, isQuoteCadOrChf: true },
  EURGBP: { symbol: "EURGBP", label: "EUR/GBP", yahooTicker: "EURGBP=X", ...FOREX_STANDARD_BASE, isEurGbp: true },
  USDJPY: { symbol: "USDJPY", label: "USD/JPY", yahooTicker: "USDJPY=X", ...FOREX_JPY_BASE },
  EURJPY: { symbol: "EURJPY", label: "EUR/JPY", yahooTicker: "EURJPY=X", ...FOREX_JPY_BASE },
  GBPJPY: { symbol: "GBPJPY", label: "GBP/JPY", yahooTicker: "GBPJPY=X", ...FOREX_JPY_BASE },
};

const SYMBOL_ALIAS_MAP: Record<string, string> = {
  GOLD: "XAUUSD",
  SILVER: "XAGUSD",
  DJ30: "US30",
  WS30: "US30",
  DOW30: "US30",
  DJI: "US30",
  USTEC: "NAS100",
  US100: "NAS100",
  NDX: "NAS100",
  NDX100: "NAS100",
  NQ100: "NAS100",
};

const CRYPTO_KEYWORDS = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "MATIC", "USDT", "USDC", "SHIB", "LINK"];

export function resolveSymbolSpec(rawSymbol: string): SymbolSpec {
  const cleanedRaw = rawSymbol.trim().toUpperCase().split("/")[0].replace(/[^A-Z0-9]/g, "");
  const cleaned = SYMBOL_ALIAS_MAP[cleanedRaw] ?? cleanedRaw;
  // Allow explicit terminal specs (e.g. USDCAD) BEFORE keyword scan so "USDC" inside "USDCAD" never false-triggers
  const spec = cleaned ? SYMBOL_SPECS[cleaned] : undefined;
  if (spec) {
    return spec;
  }
  if (!cleaned || CRYPTO_KEYWORDS.some((kw) => cleaned.includes(kw))) {
    throw new Error(`Crypto symbols (${rawSymbol}) are disabled in this terminal. Select Metals (XAUUSD, XAGUSD), Indices (US30, NAS100), or Forex (EURUSD, GBPUSD, USDJPY).`);
  }
  throw new Error(`Unsupported symbol "${rawSymbol}". Allowed Metals, Indices & Forex: ${Object.keys(SYMBOL_SPECS).join(", ")}`);
}

export function priceDeltaToUsd(deltaPrice: number, exitPrice: number, lotSize: number, spec: SymbolSpec): number {
  const grossQuote = deltaPrice * spec.contractSize * lotSize;
  if (spec.isQuoteJpy) {
    // Convert quote JPY -> USD accurately (for USDJPY exitPrice is JPY per USD; for crosses ~155 fallback)
    const jpyRate = spec.symbol === "USDJPY" && exitPrice > 50 ? exitPrice : 155.0;
    return grossQuote / jpyRate;
  }
  if (spec.isQuoteCadOrChf && exitPrice > 0.2) {
    return grossQuote / exitPrice;
  }
  if (spec.isEurGbp) {
    return grossQuote * 1.27;
  }
  return grossQuote;
}

function getPktHourDecimal(utcMs: number): number {
  const pktMs = utcMs + 5 * 3600 * 1000;
  const d = new Date(pktMs);
  return d.getUTCHours() + d.getUTCMinutes() / 60;
}

export function isInPktKillzone(utcMs: number): boolean {
  const h = getPktHourDecimal(utcMs);
  return (h >= 12.0 && h < 16.0) || (h >= 18.0 && h < 22.0);
}

export function getPktSessionLabel(utcMs: number): string {
  const h = getPktHourDecimal(utcMs);
  if (h >= 12.0 && h < 16.0) return "London PKT";
  if (h >= 18.0 && h < 22.0) return "NY PKT";
  return "Off-Peak";
}

function getSwingPoints(
  bars: OhlcBar[],
  nLeft = 3,
  nRight = 3,
  minAmplitude = 0
): { highs: Array<[number, number]>; lows: Array<[number, number]> } {
  const n = bars.length;
  if (n < nLeft + nRight + 1) return { highs: [], lows: [] };
  const sh: Array<[number, number]> = [];
  const sl: Array<[number, number]> = [];

  for (let i = nLeft; i < n - nRight; i++) {
    let isSh = true;
    let isSl = true;
    for (let j = 1; j <= nLeft; j++) {
      if (bars[i]!.high <= bars[i - j]!.high) isSh = false;
      if (bars[i]!.low >= bars[i - j]!.low) isSl = false;
    }
    for (let j = 1; j <= nRight; j++) {
      if (bars[i]!.high <= bars[i + j]!.high) isSh = false;
      if (bars[i]!.low >= bars[i + j]!.low) isSl = false;
    }
    if (isSh && minAmplitude > 0) {
      let baseLow = Infinity;
      for (let k = i - nLeft; k <= i + nRight; k++) {
        if (bars[k]!.low < baseLow) baseLow = bars[k]!.low;
      }
      if (bars[i]!.high - baseLow < minAmplitude) isSh = false;
    }
    if (isSh) sh.push([bars[i]!.high, i]);

    if (isSl && minAmplitude > 0) {
      let baseHigh = -Infinity;
      for (let k = i - nLeft; k <= i + nRight; k++) {
        if (bars[k]!.high > baseHigh) baseHigh = bars[k]!.high;
      }
      if (baseHigh - bars[i]!.low < minAmplitude) isSl = false;
    }
    if (isSl) sl.push([bars[i]!.low, i]);
  }
  return { highs: sh, lows: sl };
}

function detectMarketStructure(dfM15: OhlcBar[], spec: SymbolSpec): "BULLISH" | "BEARISH" | "NEUTRAL" {
  if (dfM15.length < 5) return "NEUTRAL";
  let { highs, lows } = getSwingPoints(dfM15, 3, 3, spec.m15MinAmp);
  if (highs.length < 2 || lows.length < 2) {
    ({ highs, lows } = getSwingPoints(dfM15, 2, 2, spec.m15MinAmp * 0.65));
  }
  if (highs.length < 2 || lows.length < 2) {
    ({ highs, lows } = getSwingPoints(dfM15, 2, 2, 0));
  }
  if (highs.length < 2 || lows.length < 2) return "NEUTRAL";

  const hasHh = highs[highs.length - 1]![0] > highs[highs.length - 2]![0];
  const hasHl = lows[lows.length - 1]![0] > lows[lows.length - 2]![0];
  const hasLh = highs[highs.length - 1]![0] < highs[highs.length - 2]![0];
  const hasLl = lows[lows.length - 1]![0] < lows[lows.length - 2]![0];

  const currClose = dfM15[dfM15.length - 1]!.close;
  const [lastShVal, lastShIdx] = highs[highs.length - 1]!;
  const [lastSlVal, lastSlIdx] = lows[lows.length - 1]!;

  let lastBullBos = -1;
  for (let k = lastShIdx + 1; k < dfM15.length; k++) {
    if (dfM15[k]!.close > lastShVal) lastBullBos = k;
  }
  let lastBearBos = -1;
  for (let k = lastSlIdx + 1; k < dfM15.length; k++) {
    if (dfM15[k]!.close < lastSlVal) lastBearBos = k;
  }

  const recentSh = highs.slice(-2).map((x) => x[0]);
  const recentSl = lows.slice(-2).map((x) => x[0]);
  const keyResistance = Math.max(...recentSh);
  const keySupport = Math.min(...recentSl);

  if (hasHh && hasHl) {
    if (lastBearBos > lastBullBos && currClose < lastSlVal) return "BEARISH";
    return "BULLISH";
  }
  if (hasLh && hasLl) {
    if (lastBullBos > lastBearBos && currClose > lastShVal) return "BULLISH";
    return "BEARISH";
  }
  if (hasLl) return currClose > keyResistance ? "BULLISH" : "BEARISH";
  if (hasHh) return currClose < keySupport ? "BEARISH" : "BULLISH";
  if (hasLh && hasHl) {
    if (lastBearBos > lastBullBos) return "BEARISH";
    if (lastBullBos > lastBearBos) return "BULLISH";
    return "NEUTRAL";
  }
  if (hasHl && !hasLl) return "BULLISH";
  if (hasLh && !hasHh) return "BEARISH";
  return "NEUTRAL";
}

interface SweepResult {
  found: boolean;
  sweepExtreme: number;
  swingLevel: number;
  sweepIdx: number;
}

function detectLiquiditySweep(
  dfM5: OhlcBar[],
  spec: SymbolSpec
): { sellSweep: SweepResult; buySweep: SweepResult } {
  const empty: SweepResult = { found: false, sweepExtreme: 0, swingLevel: 0, sweepIdx: -1 };
  const n = dfM5.length;
  if (n < 10) return { sellSweep: empty, buySweep: empty };

  let { highs: swingHighs, lows: swingLows } = getSwingPoints(dfM5, 3, 3, spec.m5MinAmp);
  if (swingHighs.length < 2 || swingLows.length < 2) {
    ({ highs: swingHighs, lows: swingLows } = getSwingPoints(dfM5, 2, 2, spec.m5MinAmp));
  }
  if (!swingHighs.length || !swingLows.length) {
    ({ highs: swingHighs, lows: swingLows } = getSwingPoints(dfM5, 2, 2, 0));
  }
  if (!swingHighs.length || !swingLows.length) return { sellSweep: empty, buySweep: empty };

  let sellSweep = empty;
  let buySweep = empty;
  const lookbackStart = Math.max(1, n - 18);

  for (let i = n - 1; i >= lookbackStart && !sellSweep.found; i--) {
    for (let sIdx = swingLows.length - 1; sIdx >= 0; sIdx--) {
      const [slVal, slIdx] = swingLows[sIdx]!;
      if (i <= slIdx + 1) continue;

      let priorPeak = -Infinity;
      for (let k = Math.max(0, slIdx - 6); k <= slIdx; k++) {
        if (dfM5[k]!.high > priorPeak) priorPeak = dfM5[k]!.high;
      }
      if (priorPeak - slVal < spec.minStructDepth) continue;
      if (dfM5[i - 1]!.close < slVal) continue;

      const oneBar = slVal - dfM5[i]!.low >= spec.minPenetration && dfM5[i]!.close >= slVal;
      const twoBar =
        i + 1 < n &&
        slVal - dfM5[i]!.low >= spec.minPenetration &&
        dfM5[i]!.close >= slVal - spec.reclaimMaxDip &&
        dfM5[i + 1]!.close >= slVal;

      if (oneBar || twoBar) {
        const sweepLow = twoBar ? Math.min(dfM5[i]!.low, dfM5[i + 1]!.low) : dfM5[i]!.low;
        const sweepEnd = twoBar ? i + 1 : i;
        let stalePriorClose = false;
        if (spec.staleCloseCheck) {
          for (let k = slIdx + 1; k < Math.max(slIdx + 1, i - 1); k++) {
            if (dfM5[k]!.close < slVal) {
              stalePriorClose = true;
              break;
            }
          }
        }
        let priorLower = false;
        for (let k = Math.max(slIdx + 1, i - 3); k < i; k++) {
          if (dfM5[k]!.low < sweepLow) {
            priorLower = true;
            break;
          }
        }
        let subsequentBreak = false;
        for (let k = sweepEnd + 1; k < n; k++) {
          if (dfM5[k]!.close < sweepLow) {
            subsequentBreak = true;
            break;
          }
        }
        if (!stalePriorClose && !priorLower && !subsequentBreak) {
          sellSweep = { found: true, sweepExtreme: sweepLow, swingLevel: slVal, sweepIdx: i };
          break;
        }
      }
    }
  }

  for (let i = n - 1; i >= lookbackStart && !buySweep.found; i--) {
    for (let sIdx = swingHighs.length - 1; sIdx >= 0; sIdx--) {
      const [shVal, shIdx] = swingHighs[sIdx]!;
      if (i <= shIdx + 1) continue;

      let priorTrough = Infinity;
      for (let k = Math.max(0, shIdx - 6); k <= shIdx; k++) {
        if (dfM5[k]!.low < priorTrough) priorTrough = dfM5[k]!.low;
      }
      if (shVal - priorTrough < spec.minStructDepth) continue;
      if (dfM5[i - 1]!.close > shVal) continue;

      const oneBar = dfM5[i]!.high - shVal >= spec.minPenetration && dfM5[i]!.close <= shVal;
      const twoBar =
        i + 1 < n &&
        dfM5[i]!.high - shVal >= spec.minPenetration &&
        dfM5[i]!.close <= shVal + spec.reclaimMaxDip &&
        dfM5[i + 1]!.close <= shVal;

      if (oneBar || twoBar) {
        const sweepHigh = twoBar ? Math.max(dfM5[i]!.high, dfM5[i + 1]!.high) : dfM5[i]!.high;
        const sweepEnd = twoBar ? i + 1 : i;
        let stalePriorClose = false;
        if (spec.staleCloseCheck) {
          for (let k = shIdx + 1; k < Math.max(shIdx + 1, i - 1); k++) {
            if (dfM5[k]!.close > shVal) {
              stalePriorClose = true;
              break;
            }
          }
        }
        let priorHigher = false;
        for (let k = Math.max(shIdx + 1, i - 3); k < i; k++) {
          if (dfM5[k]!.high > sweepHigh) {
            priorHigher = true;
            break;
          }
        }
        let subsequentBreak = false;
        for (let k = sweepEnd + 1; k < n; k++) {
          if (dfM5[k]!.close > sweepHigh) {
            subsequentBreak = true;
            break;
          }
        }
        if (!stalePriorClose && !priorHigher && !subsequentBreak) {
          buySweep = { found: true, sweepExtreme: sweepHigh, swingLevel: shVal, sweepIdx: i };
          break;
        }
      }
    }
  }

  return { sellSweep, buySweep };
}

function findProtectedSweepExtreme(
  bars: OhlcBar[],
  sweepIdx: number,
  baseExtreme: number,
  isBull: boolean,
  lookback = 12
): number {
  let ext = baseExtreme;
  const start = Math.max(0, sweepIdx - lookback);
  for (let k = start; k <= sweepIdx && k < bars.length; k++) {
    ext = isBull ? Math.min(ext, bars[k]!.low) : Math.max(ext, bars[k]!.high);
  }
  return ext;
}

function detectChochBos(
  dfBars: OhlcBar[],
  sweepIdx: number,
  isBullish: boolean,
  minSwingAmp = 0
): { found: boolean; level: number; idx: number } {
  if (sweepIdx < 0 || sweepIdx >= dfBars.length) return { found: false, level: 0, idx: -1 };
  let { highs: sh, lows: sl } = getSwingPoints(dfBars, 2, 2, minSwingAmp);
  if ((isBullish && !sh.length) || (!isBullish && !sl.length)) {
    ({ highs: sh, lows: sl } = getSwingPoints(dfBars, 2, 2, 0));
  }

  if (isBullish) {
    const prior = sh.filter(([, idx]) => idx < sweepIdx);
    let chochLvl = prior.length ? prior[prior.length - 1]![0] : 0;
    if (!prior.length) {
      for (let k = Math.max(0, sweepIdx - 6); k < sweepIdx; k++) {
        if (dfBars[k]!.high > chochLvl) chochLvl = dfBars[k]!.high;
      }
    }
    if (chochLvl <= 0) return { found: false, level: 0, idx: -1 };
    for (let j = sweepIdx + 1; j < dfBars.length; j++) {
      if (dfBars[j]!.close > chochLvl) return { found: true, level: chochLvl, idx: j };
    }
  } else {
    const prior = sl.filter(([, idx]) => idx < sweepIdx);
    let chochLvl = prior.length ? prior[prior.length - 1]![0] : Infinity;
    if (!prior.length) {
      for (let k = Math.max(0, sweepIdx - 6); k < sweepIdx; k++) {
        if (dfBars[k]!.low < chochLvl) chochLvl = dfBars[k]!.low;
      }
    }
    if (!Number.isFinite(chochLvl)) return { found: false, level: 0, idx: -1 };
    for (let j = sweepIdx + 1; j < dfBars.length; j++) {
      if (dfBars[j]!.close < chochLvl) return { found: true, level: chochLvl, idx: j };
    }
  }
  return { found: false, level: 0, idx: -1 };
}

interface ZoneBox {
  low: number;
  high: number;
  idx: number;
}

function detectOrderBlocksAndBreakers(bars: OhlcBar[], minDisp: number, maxDist: number) {
  const n = bars.length;
  const lastPrice = bars[n - 1]!.close;
  const rawBull: ZoneBox[] = [];
  const rawBear: ZoneBox[] = [];

  for (let i = 2; i < n - 1; i++) {
    const disp = Math.abs(bars[i]!.close - bars[i]!.open);
    if (disp < minDisp) continue;
    if (bars[i - 1]!.close < bars[i - 1]!.open && bars[i]!.close > bars[i - 2]!.high) {
      const obL = bars[i - 1]!.low;
      const obH = bars[i - 1]!.high;
      if (Math.abs((obL + obH) / 2 - lastPrice) <= maxDist) rawBull.push({ low: obL, high: obH, idx: i });
    } else if (bars[i - 1]!.close > bars[i - 1]!.open && bars[i]!.close < bars[i - 2]!.low) {
      const obL = bars[i - 1]!.low;
      const obH = bars[i - 1]!.high;
      if (Math.abs((obL + obH) / 2 - lastPrice) <= maxDist) rawBear.push({ low: obL, high: obH, idx: i });
    }
  }

  const bullOb: ZoneBox[] = [];
  const bearOb: ZoneBox[] = [];
  const bullBreaker: ZoneBox[] = [];
  const bearBreaker: ZoneBox[] = [];

  for (const b of rawBull) {
    let mit = false;
    for (let j = b.idx + 1; j < n; j++) {
      if (bars[j]!.close < b.low) {
        mit = true;
        break;
      }
    }
    if (!mit) bullOb.push(b);
    else if (lastPrice >= b.low && Math.abs(lastPrice - b.low) <= maxDist) bearBreaker.push(b);
  }

  for (const b of rawBear) {
    let mit = false;
    for (let j = b.idx + 1; j < n; j++) {
      if (bars[j]!.close > b.high) {
        mit = true;
        break;
      }
    }
    if (!mit) bearOb.push(b);
    else if (lastPrice <= b.high && Math.abs(lastPrice - b.high) <= maxDist) bullBreaker.push(b);
  }

  return {
    bullOb: bullOb.slice(-2),
    bearOb: bearOb.slice(-2),
    bullBreaker: bullBreaker.slice(-2),
    bearBreaker: bearBreaker.slice(-2),
  };
}

function detectSmcZones(
  bars: OhlcBar[],
  spec: SymbolSpec,
  minIdx = 0,
  sweepLow?: number,
  sweepHigh?: number
) {
  const n = bars.length;
  const lastPrice = bars[n - 1]!.close;
  const rawBull: ZoneBox[] = [];
  const rawBear: ZoneBox[] = [];

  const startScan = Math.max(2, minIdx);
  for (let i = startScan; i < n; i++) {
    const gapUp = bars[i]!.low - bars[i - 2]!.high;
    const gapDown = bars[i - 2]!.low - bars[i]!.high;
    if (gapUp >= spec.minFvgGap) {
      if (sweepLow === undefined || bars[i - 2]!.high >= sweepLow - spec.sweepMargin) {
        rawBull.push({ low: bars[i - 2]!.high, high: bars[i]!.low, idx: i });
      }
    } else if (gapDown >= spec.minFvgGap) {
      if (sweepHigh === undefined || bars[i - 2]!.low <= sweepHigh + spec.sweepMargin) {
        rawBear.push({ low: bars[i]!.high, high: bars[i - 2]!.low, idx: i });
      }
    }
  }

  const activeBull: ZoneBox[] = [];
  const activeBear: ZoneBox[] = [];

  for (const f of rawBull) {
    let mit = false;
    for (let j = f.idx + 1; j < n - 1; j++) {
      if (bars[j]!.close < f.low - spec.mitTol) {
        mit = true;
        break;
      }
    }
    if (!mit && Math.abs((f.low + f.high) / 2 - lastPrice) <= spec.maxZoneDist) {
      activeBull.push(f);
    }
  }

  for (const f of rawBear) {
    let mit = false;
    for (let j = f.idx + 1; j < n - 1; j++) {
      if (bars[j]!.close > f.high + spec.mitTol) {
        mit = true;
        break;
      }
    }
    if (!mit && Math.abs((f.low + f.high) / 2 - lastPrice) <= spec.maxZoneDist) {
      activeBear.push(f);
    }
  }

  const obs = detectOrderBlocksAndBreakers(bars, spec.minObDisp, spec.maxZoneDist);
  return {
    bullFvg: activeBull.slice(-2),
    bearFvg: activeBear.slice(-2),
    ...obs,
  };
}

function checkFvgRetest(
  closedBar: OhlcBar,
  prevBar: OhlcBar,
  closedIdx: number,
  zones: ZoneBox[],
  isBullish: boolean,
  spec: SymbolSpec
): ZoneBox | null {
  const prevIdx = closedIdx - 1;
  for (let k = zones.length - 1; k >= 0; k--) {
    const z = zones[k]!;
    if (closedIdx <= z.idx) continue;
    const canUsePrev = prevIdx > z.idx;
    const gap = Math.max(0, z.high - z.low);
    const minDepthGap = spec.minFvgGap * 2.1;
    const penDepth = gap >= minDepthGap ? 0.35 * gap : 0;

    if (isBullish) {
      const entryCeil = z.high - penDepth;
      const directTouch =
        closedBar.low <= entryCeil &&
        closedBar.low >= z.low - spec.wickBuf &&
        closedBar.close >= z.low - spec.closeTol;
      const twoBar =
        canUsePrev &&
        prevBar.low <= entryCeil &&
        prevBar.low >= z.low - spec.wickBuf &&
        prevBar.close >= z.low - spec.closeTol &&
        closedBar.close >= z.low &&
        closedBar.close >= closedBar.open;
      if (directTouch || twoBar) return z;
    } else {
      const entryFloor = z.low + penDepth;
      const directTouch =
        closedBar.high >= entryFloor &&
        closedBar.high <= z.high + spec.wickBuf &&
        closedBar.close <= z.high + spec.closeTol;
      const twoBar =
        canUsePrev &&
        prevBar.high >= entryFloor &&
        prevBar.high <= z.high + spec.wickBuf &&
        prevBar.close <= z.high + spec.closeTol &&
        closedBar.close <= z.high &&
        closedBar.close <= closedBar.open;
      if (directTouch || twoBar) return z;
    }
  }
  return null;
}

function computeM15OpposingTarget(
  isBuy: boolean,
  dfM15: OhlcBar[],
  entryPrice: number,
  slDist: number,
  minTargetRrr: number,
  spec: SymbolSpec
): { tpPrice: number; rrr: number } {
  const sh3 = getSwingPoints(dfM15, 3, 3, 0);
  let sw2 = getSwingPoints(dfM15, 2, 2, spec.m15TargetMinAmp);
  if ((isBuy && !sw2.highs.length) || (!isBuy && !sw2.lows.length)) {
    const fb = getSwingPoints(dfM15, 2, 2, 0);
    if (isBuy && !sw2.highs.length) sw2.highs = fb.highs;
    if (!isBuy && !sw2.lows.length) sw2.lows = fb.lows;
  }

  const m15Zones = detectSmcZones(dfM15, spec, 0);
  const factor = Math.pow(10, spec.digits);
  const rnd = (v: number) => Math.round(v * factor) / factor;

  if (isBuy) {
    const candidates = [
      ...sh3.highs.map(([p]) => p),
      ...sw2.highs.map(([p]) => p),
      ...m15Zones.bearOb.map((z) => z.low),
      ...m15Zones.bearBreaker.map((z) => z.low),
    ]
      .filter((p) => p > entryPrice + spec.targetMinMove)
      .map(rnd)
      .sort((a, b) => a - b);

    for (const lvl of candidates) {
      const frontRunTp = lvl - spec.frontRunBuf;
      const candRrr = (frontRunTp - entryPrice) / slDist;
      if (candRrr >= minTargetRrr) {
        if (candRrr > 3.0) return { tpPrice: rnd(entryPrice + 3.0 * slDist), rrr: 3.0 };
        return { tpPrice: rnd(frontRunTp), rrr: Number(candRrr.toFixed(2)) };
      }
    }
    return { tpPrice: rnd(entryPrice + 2.2 * slDist), rrr: 2.2 };
  }

  const candidates = [
    ...sh3.lows.map(([p]) => p),
    ...sw2.lows.map(([p]) => p),
    ...m15Zones.bullOb.map((z) => z.high),
    ...m15Zones.bullBreaker.map((z) => z.high),
  ]
    .filter((p) => p < entryPrice - spec.targetMinMove)
    .map(rnd)
    .sort((a, b) => b - a);

  for (const lvl of candidates) {
    const frontRunTp = lvl + spec.frontRunBuf;
    const candRrr = (entryPrice - frontRunTp) / slDist;
    if (candRrr >= minTargetRrr) {
      if (candRrr > 3.0) return { tpPrice: rnd(entryPrice - 3.0 * slDist), rrr: 3.0 };
      return { tpPrice: rnd(frontRunTp), rrr: Number(candRrr.toFixed(2)) };
    }
  }
  return { tpPrice: rnd(entryPrice - 2.2 * slDist), rrr: 2.2 };
}

export interface SmcBacktestParams {
  spec: SymbolSpec;
  m5Bars: OhlcBar[];
  m15Bars: OhlcBar[];
  m1Bars?: OhlcBar[];
  startTimeMs: number;
  initialBalance: number;
  lotSize: number;
  maxSlDist: number;
  minRrr: number;
  sessionFilterEnabled: boolean;
  breakevenEnabled: boolean;
  smartRiskCapEnabled?: boolean;
  riskCapUsd?: number;
  beTriggerUsd?: number;
}

export interface SmcTradeSim {
  type: "BUY" | "SELL";
  symbol: string;
  lotUsed: number;
  entryPrice: number;
  exitPrice: number;
  slPrice: number;
  tpPrice: number;
  targetRrr: number;
  achievedRrr: number;
  profitUsd: number;
  profitPercent: number;
  breakevenTriggered: boolean;
  sessionLabel: string;
  reason: "TP_HIT" | "BREAKEVEN_LOCKED" | "SL_HIT" | "OPEN_END";
  entryTime: string;
  exitTime: string;
}

function computeSafeTradeLot(
  slDist: number,
  entryPrice: number,
  maxBaseLot: number,
  spec: SymbolSpec,
  smartRiskCapEnabled: boolean,
  riskCapUsd: number
): number {
  if (!smartRiskCapEnabled || slDist <= 0) {
    return Number(maxBaseLot.toFixed(2));
  }
  const usdPerUnitLot1 = Math.abs(priceDeltaToUsd(1.0, entryPrice, 1.0, spec));
  if (usdPerUnitLot1 <= 0) return Number(maxBaseLot.toFixed(2));
  const safeLot = Math.floor((riskCapUsd / (slDist * usdPerUnitLot1)) * 100 + 1e-9) / 100;
  const lotCap = spec.category === "indices" ? Math.max(maxBaseLot, 5.0) : maxBaseLot;
  return Number(Math.max(0.01, Math.min(lotCap, safeLot)).toFixed(2));
}

function computeAdaptiveBeTrigger(lotUsed: number, spec: SymbolSpec, baseBeTriggerUsd: number): number {
  if (spec.category === "indices" || spec.category === "metals") return Math.max(baseBeTriggerUsd, 50.0);
  return baseBeTriggerUsd;
}

export function runSmcBacktest(params: SmcBacktestParams) {
  const {
    spec,
    m5Bars,
    m15Bars,
    m1Bars,
    startTimeMs,
    initialBalance,
    lotSize,
    maxSlDist,
    minRrr,
    sessionFilterEnabled,
    breakevenEnabled,
    smartRiskCapEnabled = true,
    riskCapUsd = 52.0,
    beTriggerUsd = 50.0,
  } = params;

  const factor = Math.pow(10, spec.digits);
  const rnd = (v: number) => Math.round(v * factor) / factor;

  let balance = initialBalance;
  let peakEquity = initialBalance;
  let maxDrawdownPct = 0;

  let m15Ptr = 0;
  while (m15Ptr + 1 < m15Bars.length && m15Bars[m15Ptr + 1]!.time <= m5Bars[0]!.time) {
    m15Ptr++;
  }

  interface OpenPos {
    type: "BUY" | "SELL";
    lotUsed: number;
    beTrigger: number;
    entryPrice: number;
    slPrice: number;
    initialSlPrice: number;
    slDist: number;
    tpPrice: number;
    targetRrr: number;
    breakevenApplied: boolean;
    entryTimeMs: number;
    sessionLabel: string;
  }

  let openPos: OpenPos | null = null;
  let lastTradeExitBar = -10;
  const trades: SmcTradeSim[] = [];
  const usedSweeps = new Set<string>();
  const equityCurve: Array<{ time: string; balance: number }> = [
    { time: new Date(Math.max(startTimeMs, m5Bars[0]!.time)).toISOString(), balance: initialBalance },
  ];

  // S8 FVG-Defense Refined SL Rescue (enabled only on NAS100 where M5 FVG rescue adds verified edge)
  const tryFvgRefinedSlRescue = (
    isBull: boolean,
    entryPrice: number,
    rawSlDist: number,
    matched: ZoneBox,
    closedBar: OhlcBar,
    prevBar: OhlcBar,
    candleRange: number,
    isDirClose: boolean,
    barsSinceChoch: number
  ): { slPrice: number; slDist: number } | null => {
    if (!spec.fvgRefinedSlEnabled || rawSlDist <= maxSlDist) return null;

    const isNas = spec.symbol === "NAS100";
    const maxRawMult = isNas ? 2.5 : 1.65;
    const minBody = isNas ? 0.0 : 0.35;
    const maxChochBars = isNas ? 18 : 8;
    const minGapMult = isNas ? 1.0 : 1.3;
    const refBuf = isNas ? 9.5 : 1.1;
    const minRefSl = isNas ? 25.0 : 3.2;

    if (rawSlDist > maxSlDist * maxRawMult) return null;
    const bodyRatio = Math.abs(closedBar.close - closedBar.open) / Math.max(1e-9, candleRange);
    if (minBody > 0 && (!isDirClose || bodyRatio < minBody)) return null;
    if (barsSinceChoch > maxChochBars) return null;
    if (matched.high - matched.low < spec.minFvgGap * minGapMult) return null;

    const fvgExtreme = isBull
      ? Math.min(matched.low, closedBar.low, prevBar.low)
      : Math.max(matched.high, closedBar.high, prevBar.high);
    const refSl = rnd(isBull ? fvgExtreme - refBuf : fvgExtreme + refBuf);
    const refDist = isBull ? entryPrice - refSl : refSl - entryPrice;
    if (refDist >= minRefSl && refDist <= maxSlDist) {
      return { slPrice: refSl, slDist: refDist };
    }
    return null;
  };

  const evaluateM5SignalAtSlice = (m5Slice: OhlcBar[], m15Slice: OhlcBar[], entryPriceRaw: number, entryTimeMs: number) => {
    const m15Bias = detectMarketStructure(m15Slice, spec);
    if (m15Bias === "NEUTRAL") return null;

    const { sellSweep, buySweep } = detectLiquiditySweep(m5Slice, spec);
    const isBull = m15Bias === "BULLISH";
    const sw = isBull ? sellSweep : buySweep;
    if (!sw.found) return null;

    const swTime = m5Slice[sw.sweepIdx]?.time ?? 0;
    const swKey = `${isBull ? "B" : "S"}:${swTime}`;
    if (usedSweeps.has(swKey)) return null;

    const closedIdx = m5Slice.length - 1;
    const closedBar = m5Slice[closedIdx]!;
    const prevBar = m5Slice[closedIdx - 1]!;
    const entryPrice = rnd(entryPriceRaw);

    const choch = detectChochBos(m5Slice, sw.sweepIdx, isBull);
    if (!choch.found || closedIdx - choch.idx > 18) return null;
    if (isBull ? closedBar.close < sw.sweepExtreme : closedBar.close > sw.sweepExtreme) return null;

    const zones = isBull
      ? detectSmcZones(m5Slice, spec, sw.sweepIdx, sw.sweepExtreme)
      : detectSmcZones(m5Slice, spec, sw.sweepIdx, undefined, sw.sweepExtreme);
    const matched = checkFvgRetest(closedBar, prevBar, closedIdx, isBull ? zones.bullFvg : zones.bearFvg, isBull, spec);
    if (!matched) return null;

    const range = Math.max(spec.digits <= 3 ? 0.01 : 0.0001, closedBar.high - closedBar.low);
    const dirCloseOk = isBull ? closedBar.close > closedBar.open : closedBar.close < closedBar.open;
    const wickLen = isBull
      ? Math.min(closedBar.open, closedBar.close) - closedBar.low
      : closedBar.high - Math.max(closedBar.open, closedBar.close);
    const bodyBack = isBull ? closedBar.open - closedBar.close : closedBar.close - closedBar.open;
    const isPin = wickLen / range >= 0.45 && bodyBack <= 0.25 * range;
    const zoneBoundOk = isBull ? closedBar.close >= matched.low : closedBar.close <= matched.high;
    if (!zoneBoundOk || (!dirCloseOk && !isPin)) return null;

    const notChasing = isBull ? entryPrice <= matched.high + spec.maxChaseDist : entryPrice >= matched.low - spec.maxChaseDist;
    if (!notChasing) return null;

    let slPrice = rnd(isBull ? sw.sweepExtreme - spec.wickBuf : sw.sweepExtreme + spec.wickBuf);
    let slDist = isBull ? entryPrice - slPrice : slPrice - entryPrice;
    if (spec.protectedAnchorEnabled) {
      const protExt = findProtectedSweepExtreme(m5Slice, sw.sweepIdx, sw.sweepExtreme, isBull, 12);
      const protSl = rnd(isBull ? protExt - spec.wickBuf : protExt + spec.wickBuf);
      const protDist = isBull ? entryPrice - protSl : protSl - entryPrice;
      if (protDist > slDist && protDist <= maxSlDist) {
        slPrice = protSl;
        slDist = protDist;
      }
    }
    if (slDist > maxSlDist) {
      const rescued = tryFvgRefinedSlRescue(
        isBull, entryPrice, slDist, matched, closedBar, prevBar, range, dirCloseOk, closedIdx - choch.idx
      );
      if (rescued) {
        slPrice = rescued.slPrice;
        slDist = rescued.slDist;
      }
    }
    if (slDist < spec.m5MinSlDist || slDist <= 0 || slDist > maxSlDist) return null;

    const target = computeM15OpposingTarget(isBull, m15Slice, entryPrice, slDist, minRrr, spec);
    if (target.rrr < minRrr) return null;

    const tradeLot = computeSafeTradeLot(slDist, entryPrice, lotSize, spec, smartRiskCapEnabled, riskCapUsd);
    return {
      swKey,
      pos: {
        type: (isBull ? "BUY" : "SELL") as "BUY" | "SELL",
        lotUsed: tradeLot,
        beTrigger: computeAdaptiveBeTrigger(tradeLot, spec, beTriggerUsd),
        entryPrice,
        slPrice,
        initialSlPrice: slPrice,
        slDist,
        tpPrice: target.tpPrice,
        targetRrr: target.rrr,
        breakevenApplied: false,
        entryTimeMs,
        sessionLabel: getPktSessionLabel(entryTimeMs),
      },
    };
  };

  const manageOpenPosOnBar = (currBar: OhlcBar, barIndex: number): boolean => {
    if (!openPos) return false;
    let exitPrice: number | null = null;
    let reason: SmcTradeSim["reason"] | null = null;

    if (openPos.type === "BUY") {
      if (currBar.low <= openPos.slPrice) {
        exitPrice = openPos.slPrice;
        reason = openPos.breakevenApplied ? "BREAKEVEN_LOCKED" : "SL_HIT";
      } else if (currBar.high >= openPos.tpPrice) {
        exitPrice = openPos.tpPrice;
        reason = "TP_HIT";
      } else if (breakevenEnabled && !openPos.breakevenApplied) {
        const bestFloating = priceDeltaToUsd(currBar.high - openPos.entryPrice, currBar.high, openPos.lotUsed, spec);
        if (bestFloating >= openPos.beTrigger) {
          openPos.slPrice = rnd(openPos.entryPrice + spec.beBuffer);
          openPos.breakevenApplied = true;
        }
      }
    } else {
      if (currBar.high >= openPos.slPrice) {
        exitPrice = openPos.slPrice;
        reason = openPos.breakevenApplied ? "BREAKEVEN_LOCKED" : "SL_HIT";
      } else if (currBar.low <= openPos.tpPrice) {
        exitPrice = openPos.tpPrice;
        reason = "TP_HIT";
      } else if (breakevenEnabled && !openPos.breakevenApplied) {
        const bestFloating = priceDeltaToUsd(openPos.entryPrice - currBar.low, currBar.low, openPos.lotUsed, spec);
        if (bestFloating >= openPos.beTrigger) {
          openPos.slPrice = rnd(openPos.entryPrice - spec.beBuffer);
          openPos.breakevenApplied = true;
        }
      }
    }

    if (exitPrice !== null && reason !== null) {
      const delta = openPos.type === "BUY" ? exitPrice - openPos.entryPrice : openPos.entryPrice - exitPrice;
      const profitUsd = Number(priceDeltaToUsd(delta, exitPrice, openPos.lotUsed, spec).toFixed(2));
      const profitPct = Number(((profitUsd / Math.max(1, balance)) * 100).toFixed(2));
      balance = Number((balance + profitUsd).toFixed(2));
      if (balance > peakEquity) peakEquity = balance;
      const dd = peakEquity > 0 ? ((peakEquity - balance) / peakEquity) * 100 : 0;
      if (dd > maxDrawdownPct) maxDrawdownPct = dd;

      trades.push({
        type: openPos.type,
        symbol: spec.symbol,
        lotUsed: openPos.lotUsed,
        entryPrice: openPos.entryPrice,
        exitPrice: rnd(exitPrice),
        slPrice: openPos.initialSlPrice,
        tpPrice: openPos.tpPrice,
        targetRrr: openPos.targetRrr,
        achievedRrr: Number((delta / openPos.slDist).toFixed(2)),
        profitUsd,
        profitPercent: profitPct,
        breakevenTriggered: openPos.breakevenApplied,
        sessionLabel: openPos.sessionLabel,
        reason,
        entryTime: new Date(openPos.entryTimeMs).toISOString(),
        exitTime: new Date(currBar.time).toISOString(),
      });

      equityCurve.push({ time: new Date(currBar.time).toISOString(), balance });
      openPos = null;
      lastTradeExitBar = barIndex;
    }
    return true;
  };

  const useM1Refinement = Boolean(m1Bars && m1Bars.length >= 160 && spec.category === "indices");
  const m1WarmupIdx = useM1Refinement ? Math.min(120, Math.max(20, m1Bars!.length - 10)) : 0;
  const m1HandoffStartMs = useM1Refinement ? m1Bars![m1WarmupIdx]!.time : Infinity;
  let actualM5StopMs = Infinity;

  // Phase 1: M5 Bars (either entire window when no M1 feed, or days before M1 feed begins)
  for (let i = 45; i < m5Bars.length - 1; i++) {
    const currBar = m5Bars[i]!;
    if (useM1Refinement && currBar.time >= m1HandoffStartMs) {
      actualM5StopMs = currBar.time;
      break;
    }
    while (m15Ptr + 1 < m15Bars.length && m15Bars[m15Ptr + 1]!.time <= currBar.time) {
      m15Ptr++;
    }

    if (manageOpenPosOnBar(currBar, i)) continue;

    // Cooldown 2 bars after trade close & respect selected lookback window
    if (currBar.time < startTimeMs || i - lastTradeExitBar < 2) continue;

    // Next candle open executes confirmed closed-candle signal (zero lookahead)
    const entryBar = m5Bars[i + 1]!;
    if (sessionFilterEnabled && !isInPktKillzone(entryBar.time)) continue;

    const m5Slice = m5Bars.slice(Math.max(0, i - 119), i + 1);
    const m15Slice = m15Bars.slice(Math.max(0, m15Ptr - 99), m15Ptr + 1);
    if (m15Slice.length < 15 || m5Slice.length < 12) continue;

    const sig = evaluateM5SignalAtSlice(m5Slice, m15Slice, entryBar.open, entryBar.time);
    if (sig) {
      usedSweeps.add(sig.swKey);
      openPos = sig.pos;
    }
  }

  // Phase 2: Indices M1 LTF Execution Refinement on available M1 bars (zero lookahead)
  if (useM1Refinement && m1Bars) {
    let m5Ptr = 0;
    let m15PtrM1 = 0;
    while (m5Ptr + 1 < m5Bars.length && m5Bars[m5Ptr + 1]!.time <= m1Bars[0]!.time) m5Ptr++;
    while (m15PtrM1 + 1 < m15Bars.length && m15Bars[m15PtrM1 + 1]!.time <= m1Bars[0]!.time) m15PtrM1++;

    const m1MinGap = 2.2;
    const m1MinAmp = 5.0;
    const m1MitTol = 1.0;
    const m1CloseTol = 1.5;
    const m1MinPenGap = 4.5;
    const m1MaxChase = 12.0;
    let lastM1ExitIdx = -20;

    const detectM1Fvgs = (m1Slice: OhlcBar[], minIdx: number, isBull: boolean, extremeP: number): ZoneBox[] => {
      const zones: ZoneBox[] = [];
      const n = m1Slice.length;
      for (let k = Math.max(2, minIdx); k < n; k++) {
        if (isBull) {
          const gap = m1Slice[k]!.low - m1Slice[k - 2]!.high;
          if (gap >= m1MinGap && m1Slice[k - 2]!.high >= extremeP - spec.sweepMargin) {
            let mit = false;
            for (let j = k + 1; j < n - 1; j++) {
              if (m1Slice[j]!.close < m1Slice[k - 2]!.high - m1MitTol) { mit = true; break; }
            }
            if (!mit) zones.push({ low: m1Slice[k - 2]!.high, high: m1Slice[k]!.low, idx: k });
          }
        } else {
          const gap = m1Slice[k - 2]!.low - m1Slice[k]!.high;
          if (gap >= m1MinGap && m1Slice[k - 2]!.low <= extremeP + spec.sweepMargin) {
            let mit = false;
            for (let j = k + 1; j < n - 1; j++) {
              if (m1Slice[j]!.close > m1Slice[k - 2]!.low + m1MitTol) { mit = true; break; }
            }
            if (!mit) zones.push({ low: m1Slice[k]!.high, high: m1Slice[k - 2]!.low, idx: k });
          }
        }
      }
      return zones;
    };

    for (let i = m1WarmupIdx; i < m1Bars.length - 1; i++) {
      const currM1 = m1Bars[i]!;
      const nextM1 = m1Bars[i + 1]!;
      while (m5Ptr + 1 < m5Bars.length && m5Bars[m5Ptr + 1]!.time <= currM1.time) m5Ptr++;
      while (m15PtrM1 + 1 < m15Bars.length && m15Bars[m15PtrM1 + 1]!.time <= currM1.time) m15PtrM1++;

      if (Number.isFinite(actualM5StopMs) && currM1.time < actualM5StopMs) continue;

      if (manageOpenPosOnBar(currM1, i)) {
        if (!openPos) lastM1ExitIdx = i;
        continue;
      }

      if (currM1.time < startTimeMs || i - lastM1ExitIdx < 5) continue;
      if (sessionFilterEnabled && !isInPktKillzone(nextM1.time)) continue;
      if (m5Ptr < 35 || m15PtrM1 < 15) continue;

      // Strictly closed M15 and M5 bars before nextM1.time (zero lookahead)
      const m15ClosedEnd = nextM1.time >= m15Bars[m15PtrM1]!.time + 15 * 60 * 1000 ? m15PtrM1 + 1 : m15PtrM1;
      const m5ClosedEnd = nextM1.time >= m5Bars[m5Ptr]!.time + 5 * 60 * 1000 ? m5Ptr + 1 : m5Ptr;
      if (m15ClosedEnd < 15 || m5ClosedEnd < 35) continue;

      const m15Slice = m15Bars.slice(Math.max(0, m15ClosedEnd - 90), m15ClosedEnd);
      const m5Slice = m5Bars.slice(Math.max(0, m5ClosedEnd - 75), m5ClosedEnd);

      // Try M5 primary + S8 FVG-Defense Rescue at exact M5 close boundaries first
      const isM5CloseBoundary = m5ClosedEnd > m5Ptr || nextM1.time >= m5Bars[m5Ptr]!.time + 5 * 60 * 1000;
      if (isM5CloseBoundary) {
        const m5Sig = evaluateM5SignalAtSlice(m5Slice, m15Slice, nextM1.open, nextM1.time);
        if (m5Sig) {
          usedSweeps.add(m5Sig.swKey);
          openPos = m5Sig.pos;
          continue;
        }
      }

      // M1 LTF Execution Refinement following confirmed M5 Sweep
      const m15Bias = detectMarketStructure(m15Slice, spec);
      if (m15Bias === "NEUTRAL") continue;

      const { sellSweep, buySweep } = detectLiquiditySweep(m5Slice, spec);
      const isBull = m15Bias === "BULLISH";
      const sw = isBull ? sellSweep : buySweep;
      if (!sw.found) continue;

      const swTime = m5Slice[sw.sweepIdx]?.time ?? 0;
      const swKey = `${isBull ? "B" : "S"}:${swTime}`;
      if (usedSweeps.has(swKey)) continue;

      const m1WinStartTime = swTime - 8 * 60 * 1000;
      let sIdx = Math.max(0, i - 100);
      while (sIdx < i && m1Bars[sIdx]!.time < m1WinStartTime) sIdx++;
      if (i - sIdx < 10) continue;

      const m1Slice = m1Bars.slice(sIdx, i + 1);
      const n1 = m1Slice.length;
      const closedM1 = m1Slice[n1 - 1]!;

      let anchorIdx = 0;
      let m1Extreme = isBull ? Infinity : -Infinity;
      for (let k = 0; k < n1 - 2; k++) {
        if (m1Slice[k]!.time >= swTime - 60000 && m1Slice[k]!.time <= swTime + 5 * 60000) {
          if (isBull && m1Slice[k]!.low < m1Extreme) { m1Extreme = m1Slice[k]!.low; anchorIdx = k; }
          if (!isBull && m1Slice[k]!.high > m1Extreme) { m1Extreme = m1Slice[k]!.high; anchorIdx = k; }
        }
      }
      if (anchorIdx < 2 || anchorIdx >= n1 - 3 || n1 - 1 - anchorIdx > 60) continue;

      const trueExtreme = isBull ? Math.min(sw.sweepExtreme, m1Extreme) : Math.max(sw.sweepExtreme, m1Extreme);
      let invalid = false;
      for (let k = anchorIdx + 1; k < n1; k++) {
        if ((isBull && m1Slice[k]!.close < trueExtreme) || (!isBull && m1Slice[k]!.close > trueExtreme)) {
          invalid = true;
          break;
        }
      }
      if (invalid) continue;

      const choch = detectChochBos(m1Slice, anchorIdx, isBull, m1MinAmp);
      if (!choch.found || n1 - 1 - choch.idx > 25) continue;

      const fvgs = detectM1Fvgs(m1Slice, anchorIdx, isBull, trueExtreme);
      if (!fvgs.length) continue;

      let matched: ZoneBox | null = null;
      for (let z = fvgs.length - 1; z >= 0; z--) {
        const f = fvgs[z]!;
        if (n1 - 1 <= f.idx) continue;
        const gap = Math.max(0, f.high - f.low);
        const pen = gap >= m1MinPenGap ? 0.35 * gap : 0;
        const dirOk = isBull
          ? closedM1.low <= f.high - pen && closedM1.low >= f.low - spec.wickBuf && closedM1.close >= f.low - m1CloseTol
          : closedM1.high >= f.low + pen && closedM1.high <= f.high + spec.wickBuf && closedM1.close <= f.high + m1CloseTol;
        if (dirOk) { matched = f; break; }
      }
      if (!matched) continue;

      const range = Math.max(0.01, closedM1.high - closedM1.low);
      const bodyOk = isBull
        ? closedM1.close > closedM1.open && (closedM1.close - closedM1.open) / range >= 0.25 && closedM1.close >= matched.low
        : closedM1.close < closedM1.open && (closedM1.open - closedM1.close) / range >= 0.25 && closedM1.close <= matched.high;
      if (!bodyOk) continue;

      const entryPrice = rnd(nextM1.open);
      const slPrice = rnd(isBull ? trueExtreme - spec.wickBuf : trueExtreme + spec.wickBuf);
      const slDist = isBull ? entryPrice - slPrice : slPrice - entryPrice;
      const notChasing = isBull ? entryPrice <= matched.high + m1MaxChase : entryPrice >= matched.low - m1MaxChase;
      const m1MinSl = spec.m1MinSlDist > 0 ? spec.m1MinSlDist : 15.0;
      if (slDist < m1MinSl || slDist > maxSlDist || !notChasing) continue;

      const target = computeM15OpposingTarget(isBull, m15Slice, entryPrice, slDist, minRrr, spec);
      if (target.rrr < minRrr) continue;

      const tradeLot = computeSafeTradeLot(slDist, entryPrice, lotSize, spec, smartRiskCapEnabled, riskCapUsd);
      usedSweeps.add(swKey);
      openPos = {
        type: isBull ? "BUY" : "SELL",
        lotUsed: tradeLot,
        beTrigger: computeAdaptiveBeTrigger(tradeLot, spec, beTriggerUsd),
        entryPrice,
        slPrice,
        initialSlPrice: slPrice,
        slDist,
        tpPrice: target.tpPrice,
        targetRrr: target.rrr,
        breakevenApplied: false,
        entryTimeMs: nextM1.time,
        sessionLabel: getPktSessionLabel(nextM1.time),
      };
    }
  }

  // Close any open position at end of historical sample for clean accounting
  const finalBars = useM1Refinement && m1Bars && m1Bars.length > 0 ? m1Bars : m5Bars;
  if (openPos && finalBars.length > 0) {
    const lastBar = finalBars[finalBars.length - 1]!;
    const exitPrice = rnd(lastBar.close);
    const delta = openPos.type === "BUY" ? exitPrice - openPos.entryPrice : openPos.entryPrice - exitPrice;
    const profitUsd = Number(priceDeltaToUsd(delta, exitPrice, openPos.lotUsed, spec).toFixed(2));
    const profitPct = Number(((profitUsd / Math.max(1, balance)) * 100).toFixed(2));
    balance = Number((balance + profitUsd).toFixed(2));
    if (balance > peakEquity) peakEquity = balance;
    const dd = peakEquity > 0 ? ((peakEquity - balance) / peakEquity) * 100 : 0;
    if (dd > maxDrawdownPct) maxDrawdownPct = dd;

    trades.push({
      type: openPos.type,
      symbol: spec.symbol,
      lotUsed: openPos.lotUsed,
      entryPrice: openPos.entryPrice,
      exitPrice,
      slPrice: openPos.initialSlPrice,
      tpPrice: openPos.tpPrice,
      targetRrr: openPos.targetRrr,
      achievedRrr: Number((delta / openPos.slDist).toFixed(2)),
      profitUsd,
      profitPercent: profitPct,
      breakevenTriggered: openPos.breakevenApplied,
      sessionLabel: openPos.sessionLabel,
      reason: "OPEN_END",
      entryTime: new Date(openPos.entryTimeMs).toISOString(),
      exitTime: new Date(lastBar.time).toISOString(),
    });
    equityCurve.push({ time: new Date(lastBar.time).toISOString(), balance });
  }

  const wins = trades.filter((t) => t.profitUsd > 0).length;
  const losses = trades.filter((t) => t.profitUsd < 0).length;
  const breakevens = trades.filter((t) => t.reason === "BREAKEVEN_LOCKED").length;
  const grossWin = trades.filter((t) => t.profitUsd > 0).reduce((s, t) => s + t.profitUsd, 0);
  const grossLoss = Math.abs(trades.filter((t) => t.profitUsd < 0).reduce((s, t) => s + t.profitUsd, 0));
  const profitFactor = grossLoss > 0 ? Number((grossWin / grossLoss).toFixed(2)) : grossWin > 0 ? 9.99 : 0;
  const netProfit = Number((balance - initialBalance).toFixed(2));
  const winRate = trades.length > 0 ? Number(((wins / trades.length) * 100).toFixed(2)) : 0;
  const avgRrr =
    trades.length > 0
      ? Number((trades.reduce((s, t) => s + t.achievedRrr, 0) / trades.length).toFixed(2))
      : 0;

  return {
    symbol: spec.symbol,
    label: spec.label,
    category: spec.category,
    totalTrades: trades.length,
    wins,
    losses,
    breakevens,
    winRate,
    avgRrr,
    maxDrawdownPct: Number(maxDrawdownPct.toFixed(2)),
    initialBalance,
    finalBalance: Number(balance.toFixed(2)),
    netProfit,
    profitFactor,
    equityCurve: equityCurve.slice(-60),
    trades: [...trades].reverse().slice(0, 50),
  };
}
