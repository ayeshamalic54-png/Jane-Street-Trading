export interface SmcTelemetryPayload {
  symbol_pair: string;
  m15_bias: string;
  sweep_status: string;
  sweep_price: number;
  choch_status: string;
  choch_price: number;
  fvg_status: string;
  fvg_bounds_json: string;
  rejection_status: string;
  action: string;
  updated_at: string;
  retest_status: string;
  s6_status: string;
  s7_status: string;
  s8_status: string;
  s9_status: string;
  opposing_tp: number;
  target_rrr: number;
  steps_passed: number;
}

const isPassVal = (v: unknown): boolean =>
  typeof v === "string" && (v.includes("PASS") || v.includes("🟢") || v.includes("🔴"));

function parseJsonSafe(raw: unknown): any {
  if (!raw) return null;
  if (typeof raw === "object") return raw;
  if (typeof raw === "string") {
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }
  return null;
}

export function extractSmcMetrics(telRow: any): {
  opposingTp: number;
  targetRrr: number;
  stepsPassed: number;
  lastCandlePrice: number;
  biasTag: string;
} {
  if (!telRow) {
    return { opposingTp: 0, targetRrr: 0, stepsPassed: 0, lastCandlePrice: 0, biasTag: "NEUTRAL" };
  }
  const m15Bias = String(telRow.m15Bias ?? telRow.m15_bias ?? "NEUTRAL").toUpperCase();
  const sweepSt = String(telRow.sweepStatus ?? telRow.sweep_status ?? "FAIL");
  const chochSt = String(telRow.chochStatus ?? telRow.choch_status ?? "FAIL");
  const fvgSt = String(telRow.fvgStatus ?? telRow.fvg_status ?? "FAIL");
  const retestSt = String(telRow.retestStatus ?? telRow.retest_status ?? fvgSt);
  const s6St = String(telRow.s6Status ?? telRow.s6_status ?? telRow.rejectionStatus ?? telRow.rejection_status ?? "FAIL");
  const s7St = String(telRow.s7Status ?? telRow.s7_status ?? "FAIL");
  const s8St = String(telRow.s8Status ?? telRow.s8_status ?? "");
  const s9St = String(telRow.s9Status ?? telRow.s9_status ?? "");
  const act = String(telRow.action ?? "NONE").toUpperCase();

  const isBull = m15Bias.includes("BULLISH");
  const isBear = m15Bias.includes("BEARISH");
  const s1 = (isBull || isBear) && !m15Bias.includes("NEUTRAL");
  const s2 = s1 && isPassVal(sweepSt);
  const s3 = s2 && isPassVal(chochSt);
  const s4 = s3 && isPassVal(fvgSt);
  const s5 = s4 && isPassVal(retestSt);
  const s6 = s5 && isPassVal(s6St);
  const s7 = s6 && isPassVal(s7St);
  const isSig = (act === "BUY" || act === "SELL") && s7;
  const s8 = (typeof s8St === "string" && (s8St.includes("PASS") || s8St.includes("🟢"))) || (s2 && isSig);
  const s9 = (typeof s9St === "string" && (s9St.includes("PASS") || s9St.includes("🟢"))) || (s7 && isSig);

  const stepsPassed = [s1, s2, s3, s4, s5, s6, s7, s8, s9].filter(Boolean).length;

  const parsed = parseJsonSafe(telRow.fvgBoundsJson ?? telRow.fvg_bounds_json);
  const opposingTp = Number(parsed?.opposing_tp ?? parsed?.tp_price ?? 0) || 0;
  const candles = Array.isArray(parsed?.candles) ? parsed.candles : [];
  const lastCandlePrice = candles.length > 0 ? Number(candles[candles.length - 1]?.close ?? 0) || 0 : 0;

  let targetRrr = 0;
  const rrrMatch = s9St.match(/(\d+(?:\.\d+)?)R/i);
  if (rrrMatch) {
    targetRrr = Number(rrrMatch[1]) || 0;
  }

  let biasTag = "NEUTRAL";
  if (act === "BUY" || act === "BUY_SPREAD") biasTag = "BUY";
  else if (act === "SELL" || act === "SELL_SPREAD") biasTag = "SELL";
  else if (isBull) biasTag = "BULL_BIAS";
  else if (isBear) biasTag = "BEAR_BIAS";

  return { opposingTp, targetRrr, stepsPassed, lastCandlePrice, biasTag };
}

export function formatSmcTelemetryPayload(telRow: any): SmcTelemetryPayload | null {
  if (!telRow) return null;
  const m = extractSmcMetrics(telRow);
  return {
    symbol_pair: telRow.symbolPair,
    m15_bias: telRow.m15Bias || "NEUTRAL ⚪",
    sweep_status: telRow.sweepStatus || "FAIL ⚪",
    sweep_price: Number(telRow.sweepPrice ?? 0),
    choch_status: telRow.chochStatus || "FAIL ⚪",
    choch_price: Number(telRow.chochPrice ?? 0),
    fvg_status: telRow.fvgStatus || "FAIL ⚪",
    fvg_bounds_json: telRow.fvgBoundsJson || "[]",
    rejection_status: telRow.rejectionStatus || "FAIL ⚪",
    action: telRow.action || "NONE",
    updated_at: telRow.updatedAt ? new Date(telRow.updatedAt).toISOString() : "",
    retest_status: telRow.retestStatus || telRow.fvgStatus || "FAIL ⚪",
    s6_status: telRow.s6Status || telRow.rejectionStatus || "FAIL ⚪",
    s7_status: telRow.s7Status || "FAIL ⚪",
    s8_status: telRow.s8Status || "PASS 🟢 (Structural Cap)",
    s9_status: telRow.s9Status || "PASS 🟢 (>=1.85R Target)",
    opposing_tp: m.opposingTp,
    target_rrr: m.targetRrr,
    steps_passed: m.stepsPassed,
  };
}

export function buildEnrichedScannedAssets(
  scannedRows: any[],
  telemetryRows: any[],
  isSymbolEnabled: (sym: string) => boolean
) {
  const telByPair = new Map<string, any>();
  const telByLegA = new Map<string, any>();

  for (const t of telemetryRows || []) {
    const sp = String(t.symbolPair || "");
    const spU = sp.toUpperCase();
    if (!sp || spU.includes("US500") || spU.includes("SPX") || !isSymbolEnabled(sp)) continue;
    if (!telByPair.has(spU)) telByPair.set(spU, t);
    const legA = spU.split("/")[0]?.trim() || spU;
    if (legA && !telByLegA.has(legA)) telByLegA.set(legA, t);
  }

  const seenPairs = new Set<string>();
  const result: any[] = [];

  for (const s of scannedRows || []) {
    const sp = String(s.symbolPair || "");
    const spU = sp.toUpperCase();
    if (!sp || spU.includes("US500") || spU.includes("SPX") || !isSymbolEnabled(sp)) continue;
    seenPairs.add(spU);
    const legA = spU.split("/")[0]?.trim() || spU;
    const tel = telByPair.get(spU) ?? telByLegA.get(legA);
    const m = extractSmcMetrics(tel);
    const priceA = Number(s.priceA ?? 0) || m.lastCandlePrice;
    const telAct = String(tel?.action ?? "NONE").toUpperCase();
    const rowAct = String(s.action ?? "NONE").toUpperCase();
    const effectiveAct = telAct !== "NONE" ? telAct : rowAct;

    result.push({
      symbolPair: sp,
      symbol: legA,
      priceA,
      priceB: Number(s.priceB ?? 0),
      winRate: Number(s.winRate ?? 50.0),
      zScore: Number(s.zScore ?? 0),
      action: effectiveAct,
      opposingTp: m.opposingTp,
      targetRrr: m.targetRrr,
      stepsPassed: m.stepsPassed,
      m15Bias: m.biasTag,
      telemetryUpdatedAt: tel?.updatedAt ? new Date(tel.updatedAt).toISOString() : null,
    });
  }

  for (const t of telemetryRows || []) {
    const sp = String(t.symbolPair || "");
    const spU = sp.toUpperCase();
    if (!sp || seenPairs.has(spU) || spU.includes("US500") || spU.includes("SPX") || !isSymbolEnabled(sp)) continue;
    seenPairs.add(spU);
    const legA = spU.split("/")[0]?.trim() || spU;
    const m = extractSmcMetrics(t);
    result.push({
      symbolPair: sp,
      symbol: legA,
      priceA: m.lastCandlePrice,
      priceB: 0,
      winRate: 50.0,
      zScore: 0,
      action: String(t.action ?? "NONE"),
      opposingTp: m.opposingTp,
      targetRrr: m.targetRrr,
      stepsPassed: m.stepsPassed,
      m15Bias: m.biasTag,
      telemetryUpdatedAt: t.updatedAt ? new Date(t.updatedAt).toISOString() : null,
    });
  }

  return result;
}
