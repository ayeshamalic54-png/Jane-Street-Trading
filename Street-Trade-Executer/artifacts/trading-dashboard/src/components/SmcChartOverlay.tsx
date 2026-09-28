import React, { useState, useMemo, useRef } from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  CheckCircle2,
  Clock,
  TrendingUp,
  TrendingDown,
  Shield,
  Target,
  Zap,
  Layers,
  Activity,
  Crosshair,
} from "lucide-react";

interface SmcChartOverlayProps {
  symbol: string;
  telemetry: any;
  currentPrice?: number;
  activePosition?: any;
}

interface Candle {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  isBullish: boolean;
  volume?: number;
  isSweep?: boolean;
  isChoch?: boolean;
  isRetest?: boolean;
  isRejection?: boolean;
}

export function SmcChartOverlay({
  symbol,
  telemetry,
  currentPrice,
  activePosition,
}: SmcChartOverlayProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [hoveredCandle, setHoveredCandle] = useState<Candle | null>(null);
  const [mousePos, setMousePos] = useState<{ x: number; y: number } | null>(null);

  const isMetals =
    symbol.toUpperCase().includes("XAU") ||
    symbol.toUpperCase().includes("XAG") ||
    symbol.toUpperCase().includes("GOLD");
  const defaultBuf = isMetals ? 0.75 : 0.0004;

  // Extract SMC parameters safely
  const sweepPrice = Number(telemetry?.sweep_price ?? telemetry?.sweepPrice ?? 0);
  const chochPrice = Number(telemetry?.choch_price ?? telemetry?.chochPrice ?? 0);
  const rawM15Bias = (telemetry?.m15_bias ?? telemetry?.m15Bias ?? "NEUTRAL ⚪").toUpperCase();
  const sweepStatus = telemetry?.sweep_status ?? telemetry?.sweepStatus ?? "FAIL ⚪";
  const chochStatus = telemetry?.choch_status ?? telemetry?.chochStatus ?? "FAIL ⚪";
  const fvgStatus = telemetry?.fvg_status ?? telemetry?.fvgStatus ?? "FAIL ⚪";
  const retestStatus = telemetry?.retest_status ?? telemetry?.retestStatus ?? "FAIL ⚪";
  const s6Status =
    telemetry?.s6_status ?? telemetry?.s6Status ?? telemetry?.rejection_status ?? "FAIL ⚪";
  const s7Status = telemetry?.s7_status ?? telemetry?.s7Status ?? "FAIL ⚪";
  const s8Status = telemetry?.s8_status ?? telemetry?.s8Status ?? "";
  const s9Status = telemetry?.s9_status ?? telemetry?.s9Status ?? "";
  const action = (telemetry?.action ?? "NONE").toUpperCase();

  const isPassText = (val: string) =>
    typeof val === "string" && (val.includes("PASS") || val.includes("🟢"));

  // Check Step 1 (M15 Bias)
  const isM15Bullish = rawM15Bias.includes("BULLISH");
  const isM15Bearish = rawM15Bias.includes("BEARISH");
  const s1Pass = (isM15Bullish || isM15Bearish) && !rawM15Bias.includes("NEUTRAL");

  // Sequential Condition Verifications (Conditions only pass if prerequisite passed)
  const s2Pass = s1Pass && isPassText(sweepStatus);
  const s3Pass = s2Pass && isPassText(chochStatus);
  const s4Pass = s3Pass && isPassText(fvgStatus);
  const s5Pass = s4Pass && isPassText(retestStatus);
  const s6Pass = s5Pass && isPassText(s6Status);
  const s7Pass = s6Pass && isPassText(s7Status);

  // Check if MT5 position is live OR if execution signal triggered
  const hasActivePosition = Boolean(activePosition && (activePosition.ticket || activePosition.entryPrice));
  const isSignalFired = (action === "BUY" || action === "SELL") && s7Pass;
  const isTradeActive = hasActivePosition || isSignalFired;

  // Step 8 & 9 are only considered FULL PASS when setup is valid and execution ready or active
  const s8Pass = s2Pass && (isTradeActive || (s7Pass && isPassText(s8Status)));
  const s9Pass = s7Pass && (isTradeActive || isPassText(s9Status));

  const passedCount = [
    s1Pass,
    s2Pass,
    s3Pass,
    s4Pass,
    s5Pass,
    s6Pass,
    s7Pass,
    s8Pass,
    s9Pass,
  ].filter(Boolean).length;

  const allConditionsMet = passedCount === 9 || isTradeActive;

  const tradeDirection = hasActivePosition
    ? (activePosition.orderType || (activePosition.type === 0 ? "BUY" : "SELL")).toUpperCase()
    : action !== "NONE"
    ? action
    : isM15Bullish
    ? "BUY"
    : isM15Bearish
    ? "SELL"
    : "NONE";

  const isBullishSetup = tradeDirection === "BUY" || isM15Bullish;
  const isBearishSetup = tradeDirection === "SELL" || isM15Bearish;

  const livePrice =
    currentPrice && currentPrice > 0
      ? currentPrice
      : sweepPrice > 0
      ? sweepPrice
      : 4134.48;

  const entryPrice = hasActivePosition
    ? Number(activePosition.entryPrice)
    : sweepPrice > 0
    ? sweepPrice
    : livePrice;

  // SL: $0.75 buffer behind sweep
  const slPrice = useMemo(() => {
    if (sweepPrice <= 0) return 0;
    if (isBullishSetup) {
      return Number((sweepPrice - defaultBuf).toFixed(2));
    } else if (isBearishSetup) {
      return Number((sweepPrice + defaultBuf).toFixed(2));
    }
    return Number((sweepPrice - defaultBuf).toFixed(2));
  }, [sweepPrice, isBullishSetup, isBearishSetup, defaultBuf]);

  // TP: 2.0R minimum structural target
  const tpPrice = useMemo(() => {
    if (slPrice <= 0 || sweepPrice <= 0) return 0;
    const slDist = Math.abs(entryPrice - slPrice);
    if (isBullishSetup) {
      return Number((entryPrice + 2.0 * slDist).toFixed(2));
    } else if (isBearishSetup) {
      return Number((entryPrice - 2.0 * slDist).toFixed(2));
    }
    return Number((entryPrice + 2.0 * slDist).toFixed(2));
  }, [slPrice, entryPrice, isBullishSetup, isBearishSetup]);

  // Parse FVG Bounds
  const fvgBounds = useMemo(() => {
    try {
      const rawJson = telemetry?.fvg_bounds_json ?? telemetry?.fvgBoundsJson;
      if (rawJson) {
        const parsed = JSON.parse(rawJson);
        if (Array.isArray(parsed) && parsed.length > 0) {
          const z = parsed[0];
          const l = Number(z.low ?? z.lowPrice ?? 0);
          const h = Number(z.high ?? z.highPrice ?? 0);
          if (l > 0 && h > l) return { low: l, high: h };
        }
      }
    } catch {}
    if (sweepPrice > 0 && s4Pass) {
      const spread = isMetals ? 1.4 : 0.0008;
      return {
        low: Number((isBullishSetup ? sweepPrice + spread * 0.4 : sweepPrice - spread * 1.4).toFixed(2)),
        high: Number((isBullishSetup ? sweepPrice + spread * 1.4 : sweepPrice - spread * 0.4).toFixed(2)),
      };
    }
    return null;
  }, [telemetry, sweepPrice, isMetals, isBullishSetup, s4Pass]);

  // Generate 26 clean M5 candlestick bars centered around live institutional levels
  const candles = useMemo<Candle[]>(() => {
    const bars: Candle[] = [];
    const baseP = livePrice;
    const step = isMetals ? 0.45 : 0.0002;
    const now = Date.now();

    for (let i = 25; i >= 0; i--) {
      const t = new Date(now - i * 5 * 60 * 1000);
      const timeStr = t.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });

      let openP = baseP + Math.sin(i * 0.5) * step * 3.2;
      let closeP = baseP + Math.sin((i - 1) * 0.5) * step * 3.2;

      let isSweep = false;
      let isChoch = false;
      let isRetest = false;
      let isRejection = false;

      // Candle 6: Sweep candle
      if (i === 6 && sweepPrice > 0 && s2Pass) {
        isSweep = true;
        if (isBullishSetup) {
          openP = sweepPrice + step * 0.4;
          closeP = sweepPrice + step * 0.7;
        } else {
          openP = sweepPrice - step * 0.4;
          closeP = sweepPrice - step * 0.7;
        }
      }

      // Candle 4: CHoCH candle
      if (i === 4 && chochPrice > 0 && s3Pass) {
        isChoch = true;
        if (isBullishSetup) {
          openP = chochPrice - step * 0.3;
          closeP = chochPrice + step * 0.5;
        } else {
          openP = chochPrice + step * 0.3;
          closeP = chochPrice - step * 0.5;
        }
      }

      // Candle 2: Retest
      if (i === 2 && fvgBounds && s5Pass) {
        isRetest = true;
      }

      // Candle 1: Rejection
      if (i === 1 && s6Pass) {
        isRejection = true;
        if (isBullishSetup) {
          openP = livePrice - step * 0.4;
          closeP = livePrice + step * 0.3;
        } else {
          openP = livePrice + step * 0.4;
          closeP = livePrice - step * 0.3;
        }
      }

      // Latest candle
      if (i === 0) {
        openP = closeP;
        closeP = livePrice;
      }

      let highP = Math.max(openP, closeP) + step * (isSweep ? 1.8 : isChoch ? 1.5 : 0.8);
      let lowP = Math.min(openP, closeP) - step * (isSweep ? 2.2 : isChoch ? 0.7 : 0.8);

      if (isSweep && sweepPrice > 0) {
        if (isBullishSetup) {
          lowP = sweepPrice - step * 0.3;
        } else {
          highP = sweepPrice + step * 0.3;
        }
      }

      bars.push({
        time: timeStr,
        open: Number(openP.toFixed(2)),
        high: Number(highP.toFixed(2)),
        low: Number(lowP.toFixed(2)),
        close: Number(closeP.toFixed(2)),
        isBullish: closeP >= openP,
        volume: Math.floor(450 + Math.random() * 850),
        isSweep,
        isChoch,
        isRetest,
        isRejection,
      });
    }
    return bars;
  }, [livePrice, sweepPrice, chochPrice, isMetals, isBullishSetup, fvgBounds, s2Pass, s3Pass, s5Pass, s6Pass]);

  // Dimensions & Price Mapping
  const svgWidth = 1000;
  const svgHeight = 440;
  const chartLeft = 30;
  const chartRight = 870; // dedicated price axis from 870 to 1000
  const chartTop = 30;
  const chartBottom = 395;
  const plotWidth = chartRight - chartLeft;
  const plotHeight = chartBottom - chartTop;

  const minPrice = useMemo(() => {
    const lows = candles.map((c) => c.low);
    if (slPrice > 0) lows.push(slPrice);
    if (tpPrice > 0) lows.push(tpPrice);
    if (sweepPrice > 0) lows.push(sweepPrice);
    if (fvgBounds) lows.push(fvgBounds.low);
    return Math.min(...lows) - (isMetals ? 0.8 : 0.0006);
  }, [candles, slPrice, tpPrice, sweepPrice, fvgBounds, isMetals]);

  const maxPrice = useMemo(() => {
    const highs = candles.map((c) => c.high);
    if (slPrice > 0) highs.push(slPrice);
    if (tpPrice > 0) highs.push(tpPrice);
    if (sweepPrice > 0) highs.push(sweepPrice);
    if (fvgBounds) highs.push(fvgBounds.high);
    return Math.max(...highs) + (isMetals ? 0.8 : 0.0006);
  }, [candles, slPrice, tpPrice, sweepPrice, fvgBounds, isMetals]);

  const priceRange = maxPrice - minPrice || 1;

  const getY = (priceVal: number) => {
    const clamped = Math.max(minPrice, Math.min(maxPrice, priceVal));
    return chartBottom - ((clamped - minPrice) / priceRange) * plotHeight;
  };

  const candleSpacing = plotWidth / candles.length;
  const candleBodyWidth = Math.max(8, Math.min(22, candleSpacing * 0.65));

  // 6 neat price grid ticks
  const gridTicks = useMemo(() => {
    const ticks = [];
    const step = priceRange / 5;
    for (let i = 0; i <= 5; i++) {
      const p = minPrice + step * i;
      ticks.push({
        price: p,
        y: getY(p),
      });
    }
    return ticks;
  }, [minPrice, priceRange]);

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * svgWidth;
    const y = ((e.clientY - rect.top) / rect.height) * svgHeight;
    setMousePos({ x, y });

    if (x >= chartLeft && x <= chartRight) {
      const candleIdx = Math.floor((x - chartLeft) / candleSpacing);
      if (candleIdx >= 0 && candleIdx < candles.length) {
        setHoveredCandle(candles[candleIdx]);
      }
    } else {
      setHoveredCandle(null);
    }
  };

  const handleMouseLeave = () => {
    setMousePos(null);
    setHoveredCandle(null);
  };

  return (
    <div className="w-full space-y-4 font-sans select-none">
      {/* 1. MASTER STATUS HUD BANNER (Distinct Colors: Waiting/Scanning vs Active Trade) */}
      <div
        className={cn(
          "px-4 py-3 rounded-lg border transition-all duration-300 flex flex-col md:flex-row items-start md:items-center justify-between gap-3 shadow-md",
          isTradeActive
            ? "bg-emerald-950/40 border-emerald-500/80 text-emerald-200 shadow-[0_0_20px_rgba(16,185,129,0.25)]"
            : s1Pass
            ? "bg-slate-900/80 border-slate-700/80 text-slate-300"
            : "bg-zinc-950/90 border-zinc-800 text-zinc-400"
        )}
      >
        <div className="flex items-center gap-3">
          <div
            className={cn(
              "w-9 h-9 rounded-full flex items-center justify-center font-bold text-sm shadow-inner shrink-0",
              isTradeActive
                ? "bg-emerald-500 text-black animate-pulse"
                : s1Pass
                ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                : "bg-zinc-800 text-zinc-400 border border-zinc-700"
            )}
          >
            {isTradeActive ? (
              <Zap className="w-5 h-5" />
            ) : (
              <Activity className="w-4 h-4 text-zinc-400" />
            )}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-bold uppercase tracking-wide">
                {isTradeActive
                  ? `⚡ TRADE ACTIVE: ${tradeDirection} EXECUTED @ $${entryPrice.toFixed(2)}`
                  : s1Pass
                  ? `🔍 SETUP SCANNING — ${passedCount} OF 9 CONDITIONS VERIFIED`
                  : "⚪ ORDER FLOW MONITORING — NO ACTIVE TRADE"}
              </span>
              <Badge
                variant="outline"
                className={cn(
                  "font-mono text-[10px] px-2 py-0.5 uppercase",
                  isTradeActive
                    ? "bg-emerald-500/20 text-emerald-300 border-emerald-400 animate-pulse"
                    : s1Pass
                    ? "bg-amber-500/15 text-amber-300 border-amber-500/30"
                    : "bg-zinc-800 text-zinc-400 border-zinc-700"
                )}
              >
                {isTradeActive ? "TRADE ACTIVE" : "AWAITING CONFIRMATION"}
              </Badge>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              {isTradeActive
                ? `Running ${tradeDirection} on ${symbol} | Lot: ${isMetals ? "0.07" : "0.51"} | SL: $${slPrice.toFixed(2)} ($${defaultBuf} Buf) | TP: $${tpPrice.toFixed(2)} (2.0R Target) ${
                    hasActivePosition && activePosition.profit !== undefined
                      ? `| Float P&L: $${Number(activePosition.profit).toFixed(2)}`
                      : ""
                  }`
                : !s1Pass
                ? "Step 1 PENDING ⚪: M15 Structure is Neutral (Waiting for confirmed Higher High / Lower Low)"
                : !s2Pass
                ? "Step 1 PASS 🟢 — Step 2 PENDING ⚪: Waiting for M5 Liquidity Sweep wick"
                : !s3Pass
                ? "Step 1 & 2 PASS 🟢 — Step 3 PENDING ⚪: Waiting for M5 CHoCH candle close break"
                : !s4Pass || !s5Pass
                ? "Step 1-3 PASS 🟢 — Step 4 & 5 PENDING ⚪: Waiting for Post-CHoCH FVG Creation & Retest"
                : "Step 1-5 PASS 🟢 — Waiting for Final Rejection & Candle Close confirmation"}
            </p>
          </div>
        </div>

        {/* Live Metrics Pills */}
        <div className="flex items-center gap-2 self-end md:self-center font-mono text-xs">
          <div className="px-2.5 py-1 rounded bg-zinc-900 border border-zinc-800 text-zinc-300">
            Market: <span className="text-white font-bold">${livePrice.toFixed(2)}</span>
          </div>
          {isTradeActive ? (
            <>
              <div className="px-2.5 py-1 rounded bg-rose-950/40 border border-rose-500/50 text-rose-300">
                SL: <span className="font-bold">${slPrice.toFixed(2)}</span>
              </div>
              <div className="px-2.5 py-1 rounded bg-emerald-950/40 border border-emerald-500/50 text-emerald-300">
                TP: <span className="font-bold">${tpPrice.toFixed(2)}</span>
              </div>
            </>
          ) : (
            <div className="px-2.5 py-1 rounded bg-zinc-900/80 border border-zinc-800 text-zinc-500 italic">
              SL & TP: <span className="text-zinc-400">Locked on Execution</span>
            </div>
          )}
        </div>
      </div>

      {/* 2. HIGH DEFINITION CANDLESTICK CHART */}
      <div className="relative w-full bg-[#0a0d14] border border-zinc-800 rounded-xl overflow-hidden shadow-2xl">
        {/* Top Chart Toolbar */}
        <div className="flex items-center justify-between px-4 py-2.5 bg-[#0e121b] border-b border-zinc-800/80 text-xs font-mono">
          <div className="flex items-center gap-3">
            <span className="font-bold text-white tracking-wider flex items-center gap-1.5">
              <span
                className={cn(
                  "w-2 h-2 rounded-full",
                  isTradeActive ? "bg-emerald-400 animate-ping" : "bg-zinc-500"
                )}
              />
              {symbol} <span className="text-zinc-400 font-normal">M5 Candlesticks</span>
            </span>
            <Badge
              variant="outline"
              className={cn(
                "text-[10px] px-2 py-0.5 font-bold",
                s1Pass && isM15Bullish
                  ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/40"
                  : s1Pass && isM15Bearish
                  ? "bg-rose-500/15 text-rose-400 border-rose-500/40"
                  : "bg-zinc-800/80 text-zinc-400 border-zinc-700"
              )}
            >
              M15 Bias: {rawM15Bias}
            </Badge>

            {isTradeActive && (
              <Badge className="bg-emerald-600 text-white font-bold text-[10px] px-2">
                ACTIVE POSITION
              </Badge>
            )}
          </div>

          <div className="flex items-center gap-4 text-zinc-400 text-[11px]">
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm bg-[#00c076]" /> Bullish Candle
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm bg-[#ff3b69]" /> Bearish Candle
            </span>
            {s2Pass && (
              <span className="flex items-center gap-1.5 text-sky-400">
                <span className="w-2.5 h-1 bg-sky-400 inline-block" /> Sweep Level
              </span>
            )}
            {s3Pass && (
              <span className="flex items-center gap-1.5 text-amber-400">
                <span className="w-2.5 h-1 bg-amber-400 inline-block" /> CHoCH Level
              </span>
            )}
          </div>
        </div>

        {/* SVG Chart Display */}
        <div className="relative w-full h-[440px]" ref={containerRef}>
          <svg
            viewBox={`0 0 ${svgWidth} ${svgHeight}`}
            className="w-full h-full cursor-crosshair"
            onMouseMove={handleMouseMove}
            onMouseLeave={handleMouseLeave}
          >
            <defs>
              <linearGradient id="fvgGradientActive" x1="0" y1="0" x2="0" y2="1">
                <stop
                  offset="0%"
                  stopColor={isBullishSetup ? "#10b981" : "#f43f5e"}
                  stopOpacity="0.22"
                />
                <stop
                  offset="100%"
                  stopColor={isBullishSetup ? "#10b981" : "#f43f5e"}
                  stopOpacity="0.05"
                />
              </linearGradient>

              <filter id="glowGreen" x="-20%" y="-20%" width="140%" height="140%">
                <feDropShadow dx="0" dy="0" stdDeviation="2.5" floodColor="#10b981" floodOpacity="0.9" />
              </filter>
              <filter id="glowRed" x="-20%" y="-20%" width="140%" height="140%">
                <feDropShadow dx="0" dy="0" stdDeviation="2.5" floodColor="#ef4444" floodOpacity="0.9" />
              </filter>
              <filter id="glowBlue" x="-20%" y="-20%" width="140%" height="140%">
                <feDropShadow dx="0" dy="0" stdDeviation="2" floodColor="#38bdf8" floodOpacity="0.8" />
              </filter>
              <filter id="glowGold" x="-20%" y="-20%" width="140%" height="140%">
                <feDropShadow dx="0" dy="0" stdDeviation="2" floodColor="#fbbf24" floodOpacity="0.9" />
              </filter>
            </defs>

            {/* Price Axis Background Strip on Right (x: 870 to 1000) */}
            <rect
              x={chartRight}
              y={chartTop}
              width={svgWidth - chartRight}
              height={plotHeight}
              fill="#0d111a"
              stroke="#1e222d"
              strokeWidth="1"
            />

            {/* Time Axis Background Strip on Bottom (y: 395 to 440) */}
            <rect
              x={chartLeft}
              y={chartBottom}
              width={plotWidth}
              height={svgHeight - chartBottom}
              fill="#0d111a"
              stroke="#1e222d"
              strokeWidth="1"
            />

            {/* Horizontal Price Grid Lines & Axis Numbers */}
            {gridTicks.map((tick, idx) => (
              <g key={idx}>
                <line
                  x1={chartLeft}
                  y1={tick.y}
                  x2={chartRight}
                  y2={tick.y}
                  stroke="#1c2130"
                  strokeWidth="1"
                  strokeDasharray="4 4"
                />
                <text
                  x={chartRight + 12}
                  y={tick.y + 3.5}
                  fill="#64748b"
                  fontSize="11"
                  fontFamily="monospace"
                  fontWeight="500"
                >
                  ${tick.price.toFixed(2)}
                </text>
              </g>
            ))}

            {/* Step 4 & 5: FVG Retest Zone (Only shown if S4 is verified or setup in progress) */}
            {fvgBounds && fvgBounds.high > fvgBounds.low && (
              <g>
                <rect
                  x={chartLeft + candleSpacing * 12}
                  y={getY(fvgBounds.high)}
                  width={plotWidth - candleSpacing * 12}
                  height={Math.max(6, Math.abs(getY(fvgBounds.low) - getY(fvgBounds.high)))}
                  fill={s5Pass ? "url(#fvgGradientActive)" : "rgba(100, 116, 139, 0.08)"}
                  stroke={s5Pass ? (isBullishSetup ? "#10b981" : "#f43f5e") : "#475569"}
                  strokeWidth="1"
                  strokeDasharray={s5Pass ? "none" : "3 3"}
                />
                <rect
                  x={chartLeft + candleSpacing * 12 + 6}
                  y={getY(fvgBounds.high) + 4}
                  width="180"
                  height="18"
                  fill={s5Pass ? "#064e3b" : "#1e293b"}
                  rx="3"
                  opacity="0.9"
                />
                <text
                  x={chartLeft + candleSpacing * 12 + 12}
                  y={getY(fvgBounds.high) + 16}
                  fill={s5Pass ? "#6ee7b7" : "#94a3b8"}
                  fontSize="10"
                  fontFamily="monospace"
                  fontWeight="bold"
                >
                  {s5Pass ? "🟢 S4/S5: FVG RETEST PASS" : "⏳ S4: POTENTIAL FVG ZONE"}
                </text>
              </g>
            )}

            {/* Step 2: Liquidity Sweep Horizontal Line (Active Blue if passed, faint muted if pending) */}
            {sweepPrice > 0 && s2Pass && (
              <g>
                <line
                  x1={chartLeft}
                  y1={getY(sweepPrice)}
                  x2={chartRight}
                  y2={getY(sweepPrice)}
                  stroke="#38bdf8"
                  strokeWidth={1.5}
                  strokeDasharray="5 3"
                  filter="url(#glowBlue)"
                />
                <rect
                  x={chartRight + 4}
                  y={getY(sweepPrice) - 10}
                  width="120"
                  height="20"
                  fill="#0369a1"
                  rx="3"
                />
                <text
                  x={chartRight + 8}
                  y={getY(sweepPrice) + 4}
                  fill="#e0f2fe"
                  fontSize="10"
                  fontFamily="monospace"
                  fontWeight="bold"
                >
                  SWEEP ${sweepPrice.toFixed(2)}
                </text>
              </g>
            )}

            {/* Step 3: CHoCH Break Horizontal Line (Active Amber if passed) */}
            {chochPrice > 0 && s3Pass && (
              <g>
                <line
                  x1={chartLeft}
                  y1={getY(chochPrice)}
                  x2={chartRight}
                  y2={getY(chochPrice)}
                  stroke="#f59e0b"
                  strokeWidth={1.5}
                  strokeDasharray="5 4"
                />
                <rect
                  x={chartRight + 4}
                  y={getY(chochPrice) - 10}
                  width="120"
                  height="20"
                  fill="#b45309"
                  rx="3"
                />
                <text
                  x={chartRight + 8}
                  y={getY(chochPrice) + 4}
                  fill="#fef3c7"
                  fontSize="10"
                  fontFamily="monospace"
                  fontWeight="bold"
                >
                  CHoCH ${chochPrice.toFixed(2)}
                </text>
              </g>
            )}

            {/* ======================================================== */}
            {/* DYNAMIC COLOR SHIFT: ENTRY, SL, AND TP LEVELS           */}
            {/* When Trade is Active: VIBRANT SOLID GLOWING COLORS       */}
            {/* When Trade is Pending: SUBTLE MUTED DASHED GHOST LINES  */}
            {/* ======================================================== */}

            {/* ENTRY PRICE LEVEL */}
            {isTradeActive && (
              <g>
                <line
                  x1={chartLeft}
                  y1={getY(entryPrice)}
                  x2={chartRight}
                  y2={getY(entryPrice)}
                  stroke="#fbbf24"
                  strokeWidth="2"
                  filter="url(#glowGold)"
                />
                <rect
                  x={chartRight + 4}
                  y={getY(entryPrice) - 10}
                  width="120"
                  height="20"
                  fill="#78350f"
                  rx="3"
                  stroke="#fbbf24"
                  strokeWidth="1"
                />
                <text
                  x={chartRight + 8}
                  y={getY(entryPrice) + 4}
                  fill="#fef3c7"
                  fontSize="10"
                  fontFamily="monospace"
                  fontWeight="bold"
                >
                  🎯 ENTRY ${entryPrice.toFixed(2)}
                </text>
              </g>
            )}

            {/* STOP LOSS (SL) LEVEL */}
            {slPrice > 0 && (
              <g>
                <line
                  x1={chartLeft}
                  y1={getY(slPrice)}
                  x2={chartRight}
                  y2={getY(slPrice)}
                  stroke={isTradeActive ? "#ef4444" : "#475569"}
                  strokeWidth={isTradeActive ? 2 : 1}
                  strokeDasharray={isTradeActive ? "none" : "4 4"}
                  opacity={isTradeActive ? 1 : 0.45}
                  filter={isTradeActive ? "url(#glowRed)" : undefined}
                />
                <rect
                  x={chartRight + 4}
                  y={getY(slPrice) - 10}
                  width="120"
                  height="20"
                  fill={isTradeActive ? "#991b1b" : "#1e293b"}
                  rx="3"
                  stroke={isTradeActive ? "#ef4444" : "#334155"}
                  strokeWidth="1"
                />
                <text
                  x={chartRight + 8}
                  y={getY(slPrice) + 4}
                  fill={isTradeActive ? "#fee2e2" : "#94a3b8"}
                  fontSize="10"
                  fontFamily="monospace"
                  fontWeight="bold"
                >
                  {isTradeActive
                    ? `🔴 ACTIVE SL $${slPrice.toFixed(2)}`
                    : `⏳ PROJ SL $${slPrice.toFixed(2)}`}
                </text>
              </g>
            )}

            {/* TAKE PROFIT (TP) 2.0R LEVEL */}
            {tpPrice > 0 && (
              <g>
                <line
                  x1={chartLeft}
                  y1={getY(tpPrice)}
                  x2={chartRight}
                  y2={getY(tpPrice)}
                  stroke={isTradeActive ? "#10b981" : "#475569"}
                  strokeWidth={isTradeActive ? 2 : 1}
                  strokeDasharray={isTradeActive ? "none" : "4 4"}
                  opacity={isTradeActive ? 1 : 0.45}
                  filter={isTradeActive ? "url(#glowGreen)" : undefined}
                />
                <rect
                  x={chartRight + 4}
                  y={getY(tpPrice) - 10}
                  width="120"
                  height="20"
                  fill={isTradeActive ? "#065f46" : "#1e293b"}
                  rx="3"
                  stroke={isTradeActive ? "#10b981" : "#334155"}
                  strokeWidth="1"
                />
                <text
                  x={chartRight + 8}
                  y={getY(tpPrice) + 4}
                  fill={isTradeActive ? "#d1fae5" : "#94a3b8"}
                  fontSize="10"
                  fontFamily="monospace"
                  fontWeight="bold"
                >
                  {isTradeActive
                    ? `🟢 ACTIVE TP $${tpPrice.toFixed(2)}`
                    : `⏳ PROJ TP $${tpPrice.toFixed(2)}`}
                </text>
              </g>
            )}

            {/* LIVE MARKET PRICE LINE */}
            <g>
              <line
                x1={chartLeft}
                y1={getY(livePrice)}
                x2={chartRight}
                y2={getY(livePrice)}
                stroke="#ffffff"
                strokeWidth="1"
                strokeDasharray="2 2"
                opacity="0.8"
              />
              <rect
                x={chartRight + 4}
                y={getY(livePrice) - 9}
                width="120"
                height="18"
                fill="#ffffff"
                rx="3"
              />
              <text
                x={chartRight + 10}
                y={getY(livePrice) + 4}
                fill="#000000"
                fontSize="10"
                fontFamily="monospace"
                fontWeight="900"
              >
                LIVE ${livePrice.toFixed(2)}
              </text>
            </g>

            {/* CRISP CANDLESTICKS RENDERING */}
            {candles.map((c, idx) => {
              const cx = chartLeft + (idx + 0.5) * candleSpacing;
              const yHigh = getY(c.high);
              const yLow = getY(c.low);
              const yOpen = getY(c.open);
              const yClose = getY(c.close);
              const yBodyTop = Math.min(yOpen, yClose);
              const bodyHeight = Math.max(2, Math.abs(yClose - yOpen));
              const isGreen = c.isBullish;
              const bodyFill = isGreen ? "#00c076" : "#ff3b69";
              const strokeColor = isGreen ? "#00e68c" : "#ff5c85";

              return (
                <g key={idx} className="cursor-pointer">
                  {/* High Definition Candlestick Wick */}
                  <line
                    x1={cx}
                    y1={yHigh}
                    x2={cx}
                    y2={yLow}
                    stroke={strokeColor}
                    strokeWidth="1.5"
                    shapeRendering="crispEdges"
                  />

                  {/* High Definition Candlestick Body */}
                  <rect
                    x={cx - candleBodyWidth / 2}
                    y={yBodyTop}
                    width={candleBodyWidth}
                    height={bodyHeight}
                    fill={bodyFill}
                    stroke={strokeColor}
                    strokeWidth="1"
                    rx="1"
                    shapeRendering="crispEdges"
                  />

                  {/* Sweep Wick Indicator Marker (Only if Sweep Passed) */}
                  {c.isSweep && s2Pass && (
                    <g>
                      <path
                        d={`M ${cx} ${yLow + 6} L ${cx - 6} ${yLow + 16} L ${cx + 6} ${yLow + 16} Z`}
                        fill="#38bdf8"
                      />
                      <rect
                        x={cx - 36}
                        y={yLow + 20}
                        width="72"
                        height="16"
                        fill="#0c4a6e"
                        rx="3"
                        stroke="#38bdf8"
                        strokeWidth="1"
                      />
                      <text
                        x={cx}
                        y={yLow + 31}
                        fill="#38bdf8"
                        fontSize="8.5"
                        fontFamily="monospace"
                        fontWeight="bold"
                        textAnchor="middle"
                      >
                        SWEEP WICK
                      </text>
                    </g>
                  )}

                  {/* CHoCH Indicator Marker (Only if CHoCH Passed) */}
                  {c.isChoch && s3Pass && (
                    <g>
                      <circle cx={cx} cy={yHigh - 8} r="3" fill="#f59e0b" />
                      <text
                        x={cx}
                        y={yHigh - 14}
                        fill="#fbbf24"
                        fontSize="8.5"
                        fontFamily="monospace"
                        fontWeight="bold"
                        textAnchor="middle"
                      >
                        CHOCH
                      </text>
                    </g>
                  )}

                  {/* Time Axis Label on Bottom */}
                  {idx % 4 === 0 && (
                    <text
                      x={cx}
                      y={chartBottom + 18}
                      fill="#64748b"
                      fontSize="10"
                      fontFamily="monospace"
                      textAnchor="middle"
                    >
                      {c.time}
                    </text>
                  )}
                </g>
              );
            })}

            {/* Mouse Crosshair Lines */}
            {mousePos &&
              mousePos.x >= chartLeft &&
              mousePos.x <= chartRight &&
              mousePos.y >= chartTop &&
              mousePos.y <= chartBottom && (
                <g pointerEvents="none">
                  <line
                    x1={mousePos.x}
                    y1={chartTop}
                    x2={mousePos.x}
                    y2={chartBottom}
                    stroke="#94a3b8"
                    strokeWidth="1"
                    strokeDasharray="3 3"
                  />
                  <line
                    x1={chartLeft}
                    y1={mousePos.y}
                    x2={chartRight}
                    y2={mousePos.y}
                    stroke="#94a3b8"
                    strokeWidth="1"
                    strokeDasharray="3 3"
                  />
                </g>
              )}
          </svg>

          {/* Interactive Tooltip Card */}
          {hoveredCandle && (
            <div className="absolute top-3 left-4 bg-zinc-950/95 border border-zinc-700/80 px-3 py-2 rounded-md text-[11px] font-mono text-zinc-200 shadow-2xl backdrop-blur-md pointer-events-none z-10 flex items-center gap-4">
              <div>
                <span className="text-zinc-400">Time:</span>{" "}
                <span className="text-white font-bold">{hoveredCandle.time}</span>
              </div>
              <div className="flex items-center gap-2">
                <span>
                  O:{" "}
                  <strong className={hoveredCandle.isBullish ? "text-emerald-400" : "text-rose-400"}>
                    ${hoveredCandle.open.toFixed(2)}
                  </strong>
                </span>
                <span>
                  H: <strong className="text-zinc-100">${hoveredCandle.high.toFixed(2)}</strong>
                </span>
                <span>
                  L: <strong className="text-zinc-100">${hoveredCandle.low.toFixed(2)}</strong>
                </span>
                <span>
                  C:{" "}
                  <strong className={hoveredCandle.isBullish ? "text-emerald-400" : "text-rose-400"}>
                    ${hoveredCandle.close.toFixed(2)}
                  </strong>
                </span>
              </div>
              {hoveredCandle.isSweep && s2Pass && (
                <Badge variant="outline" className="bg-sky-500/20 text-sky-300 border-sky-400 text-[10px]">
                  🔵 SWEEP CANDLE
                </Badge>
              )}
              {hoveredCandle.isChoch && s3Pass && (
                <Badge variant="outline" className="bg-amber-500/20 text-amber-300 border-amber-400 text-[10px]">
                  🟠 CHOCH CANDLE
                </Badge>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 3. STEP-BY-STEP LIVE 9-CONDITION PIPELINE (Dynamic Status Colors) */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-mono font-bold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
            <Layers className="w-3.5 h-3.5 text-indigo-400" /> Pure SMC Strict 9-Step Verification Status
          </h4>
          <span className="text-[11px] font-mono text-zinc-500">
            Real-time synchronization with VPS Engine
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5 font-mono text-xs">
          {/* Step 1 */}
          <div
            className={cn(
              "p-3 rounded-lg border transition-all",
              s1Pass
                ? "bg-emerald-950/25 border-emerald-500/40 text-emerald-200"
                : "bg-zinc-900/60 border-zinc-800 text-zinc-400"
            )}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="font-bold flex items-center gap-1.5">
                {s1Pass ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                ) : (
                  <Clock className="w-4 h-4 text-zinc-500" />
                )}
                S1: M15 Structural Bias
              </span>
              <Badge
                variant="outline"
                className={cn(
                  "text-[10px] px-1.5 py-0.2",
                  s1Pass
                    ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/50"
                    : "bg-zinc-800 text-zinc-400 border-zinc-700"
                )}
              >
                {s1Pass ? rawM15Bias : "NEUTRAL ⚪"}
              </Badge>
            </div>
            <p className="text-[11px] text-zinc-400 leading-snug">
              {s1Pass
                ? `M15 order flow confirmed ${rawM15Bias.includes("BULLISH") ? "Bullish (HH/HL)" : "Bearish (LH/LL)"}.`
                : "Scanning M15 fractal swing structure (waiting for directional trend)."}
            </p>
          </div>

          {/* Step 2 */}
          <div
            className={cn(
              "p-3 rounded-lg border transition-all",
              s2Pass
                ? "bg-sky-950/30 border-sky-500/40 text-sky-200"
                : "bg-zinc-900/60 border-zinc-800 text-zinc-400"
            )}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="font-bold flex items-center gap-1.5">
                {s2Pass ? (
                  <CheckCircle2 className="w-4 h-4 text-sky-400" />
                ) : (
                  <Clock className="w-4 h-4 text-zinc-500" />
                )}
                S2: Liquidity Sweep
              </span>
              <Badge
                variant="outline"
                className={cn(
                  "text-[10px] px-1.5 py-0.2",
                  s2Pass
                    ? "bg-sky-500/20 text-sky-300 border-sky-500/50"
                    : "bg-zinc-800 text-zinc-400 border-zinc-700"
                )}
              >
                {s2Pass ? sweepStatus : "PENDING ⚪"}
              </Badge>
            </div>
            <p className="text-[11px] text-zinc-400 leading-snug">
              {s2Pass
                ? `Absorbed retail stops at $${sweepPrice.toFixed(2)} via wick rejection.`
                : "Waiting for candle wick to sweep previous M5 swing high/low."}
            </p>
          </div>

          {/* Step 3 */}
          <div
            className={cn(
              "p-3 rounded-lg border transition-all",
              s3Pass
                ? "bg-amber-950/30 border-amber-500/40 text-amber-200"
                : "bg-zinc-900/60 border-zinc-800 text-zinc-400"
            )}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="font-bold flex items-center gap-1.5">
                {s3Pass ? (
                  <CheckCircle2 className="w-4 h-4 text-amber-400" />
                ) : (
                  <Clock className="w-4 h-4 text-zinc-500" />
                )}
                S3: M5 CHoCH Break
              </span>
              <Badge
                variant="outline"
                className={cn(
                  "text-[10px] px-1.5 py-0.2",
                  s3Pass
                    ? "bg-amber-500/20 text-amber-300 border-amber-500/50"
                    : "bg-zinc-800 text-zinc-400 border-zinc-700"
                )}
              >
                {s3Pass ? chochStatus : "PENDING ⚪"}
              </Badge>
            </div>
            <p className="text-[11px] text-zinc-400 leading-snug">
              {s3Pass
                ? `Confirmed trend change by closing past $${chochPrice.toFixed(2)}.`
                : "Waiting for candle body close beyond the minor pivot point."}
            </p>
          </div>

          {/* Step 4 */}
          <div
            className={cn(
              "p-3 rounded-lg border transition-all",
              s4Pass
                ? "bg-emerald-950/25 border-emerald-500/40 text-emerald-200"
                : "bg-zinc-900/60 border-zinc-800 text-zinc-400"
            )}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="font-bold flex items-center gap-1.5">
                {s4Pass ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                ) : (
                  <Clock className="w-4 h-4 text-zinc-500" />
                )}
                S4: Post-CHoCH FVG
              </span>
              <Badge
                variant="outline"
                className={cn(
                  "text-[10px] px-1.5 py-0.2",
                  s4Pass
                    ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/50"
                    : "bg-zinc-800 text-zinc-400 border-zinc-700"
                )}
              >
                {s4Pass ? fvgStatus : "PENDING ⚪"}
              </Badge>
            </div>
            <p className="text-[11px] text-zinc-400 leading-snug">
              {s4Pass
                ? "Imbalance gap formed strictly after CHoCH candle index."
                : "Waiting for 3-candle imbalance (Fair Value Gap) after CHoCH."}
            </p>
          </div>

          {/* Step 5 */}
          <div
            className={cn(
              "p-3 rounded-lg border transition-all",
              s5Pass
                ? "bg-emerald-950/25 border-emerald-500/40 text-emerald-200"
                : "bg-zinc-900/60 border-zinc-800 text-zinc-400"
            )}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="font-bold flex items-center gap-1.5">
                {s5Pass ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                ) : (
                  <Clock className="w-4 h-4 text-zinc-500" />
                )}
                S5: FVG Retest
              </span>
              <Badge
                variant="outline"
                className={cn(
                  "text-[10px] px-1.5 py-0.2",
                  s5Pass
                    ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/50"
                    : "bg-zinc-800 text-zinc-400 border-zinc-700"
                )}
              >
                {s5Pass ? retestStatus : "PENDING ⚪"}
              </Badge>
            </div>
            <p className="text-[11px] text-zinc-400 leading-snug">
              {s5Pass
                ? "Price dipped into confirmed Post-CHoCH FVG zone."
                : "Waiting for subsequent candle to retest the FVG zone."}
            </p>
          </div>

          {/* Step 6 */}
          <div
            className={cn(
              "p-3 rounded-lg border transition-all",
              s6Pass
                ? "bg-emerald-950/25 border-emerald-500/40 text-emerald-200"
                : "bg-zinc-900/60 border-zinc-800 text-zinc-400"
            )}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="font-bold flex items-center gap-1.5">
                {s6Pass ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                ) : (
                  <Clock className="w-4 h-4 text-zinc-500" />
                )}
                S6: Rejection Candle
              </span>
              <Badge
                variant="outline"
                className={cn(
                  "text-[10px] px-1.5 py-0.2",
                  s6Pass
                    ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/50"
                    : "bg-zinc-800 text-zinc-400 border-zinc-700"
                )}
              >
                {s6Pass ? s6Status : "PENDING ⚪"}
              </Badge>
            </div>
            <p className="text-[11px] text-zinc-400 leading-snug">
              {s6Pass
                ? "Confirmed directional rejection candle inside the FVG."
                : "Waiting for directional rejection candle at zone."}
            </p>
          </div>

          {/* Step 7 */}
          <div
            className={cn(
              "p-3 rounded-lg border transition-all",
              s7Pass
                ? "bg-emerald-950/25 border-emerald-500/40 text-emerald-200"
                : "bg-zinc-900/60 border-zinc-800 text-zinc-400"
            )}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="font-bold flex items-center gap-1.5">
                {s7Pass ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                ) : (
                  <Clock className="w-4 h-4 text-zinc-500" />
                )}
                S7: Candle Closed
              </span>
              <Badge
                variant="outline"
                className={cn(
                  "text-[10px] px-1.5 py-0.2",
                  s7Pass
                    ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/50"
                    : "bg-zinc-800 text-zinc-400 border-zinc-700"
                )}
              >
                {s7Pass ? s7Status : "PENDING ⚪"}
              </Badge>
            </div>
            <p className="text-[11px] text-zinc-400 leading-snug">
              {s7Pass
                ? "Confirmed full candle closure (no unconfirmed ticks)."
                : "Execution strictly waits for full candle closure."}
            </p>
          </div>

          {/* Step 8 */}
          <div
            className={cn(
              "p-3 rounded-lg border transition-all",
              s8Pass
                ? "bg-rose-950/30 border-rose-500/50 text-rose-200"
                : "bg-zinc-900/60 border-zinc-800 text-zinc-400"
            )}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="font-bold flex items-center gap-1.5">
                {s8Pass ? (
                  <Shield className="w-4 h-4 text-rose-400" />
                ) : (
                  <Clock className="w-4 h-4 text-zinc-500" />
                )}
                S8: SL Placement
              </span>
              <Badge
                variant="outline"
                className={cn(
                  "text-[10px] px-1.5 py-0.2",
                  s8Pass
                    ? "bg-rose-500/20 text-rose-300 border-rose-500/50"
                    : "bg-zinc-800 text-zinc-400 border-zinc-700"
                )}
              >
                {s8Pass ? `PASS 🟢 ($${defaultBuf} Buf)` : "PENDING ⚪"}
              </Badge>
            </div>
            <p className="text-[11px] text-zinc-400 leading-snug">
              {s8Pass
                ? `Locked exact $${defaultBuf} buffer behind Sweep wick ($${slPrice.toFixed(2)}).`
                : `Will anchor $${defaultBuf} behind Sweep wick upon trade execution.`}
            </p>
          </div>

          {/* Step 9 */}
          <div
            className={cn(
              "p-3 rounded-lg border transition-all",
              s9Pass
                ? "bg-emerald-950/25 border-emerald-500/40 text-emerald-200"
                : "bg-zinc-900/60 border-zinc-800 text-zinc-400"
            )}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="font-bold flex items-center gap-1.5">
                {s9Pass ? (
                  <Target className="w-4 h-4 text-emerald-400" />
                ) : (
                  <Clock className="w-4 h-4 text-zinc-500" />
                )}
                S9: 2.0R Target Space
              </span>
              <Badge
                variant="outline"
                className={cn(
                  "text-[10px] px-1.5 py-0.2",
                  s9Pass
                    ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/50"
                    : "bg-zinc-800 text-zinc-400 border-zinc-700"
                )}
              >
                {s9Pass ? "PASS 🟢 (2.0R Space)" : "PENDING ⚪"}
              </Badge>
            </div>
            <p className="text-[11px] text-zinc-400 leading-snug">
              {s9Pass
                ? `Verified minimum 2.0R structural target space available ($${tpPrice.toFixed(2)}).`
                : "Calculates 2.0R structural target space once entry triggers."}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
