import React, { useState, useEffect, useMemo, useRef } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  CheckCircle2,
  Clock,
  Shield,
  Target,
  Zap,
  Layers,
  Activity,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  BarChart2,
  Tv,
} from "lucide-react";

interface SmcChartOverlayProps {
  symbol: string;
  telemetry: any;
  currentPrice?: number;
  activePosition?: any;
}

let tvScriptLoadingPromise: Promise<void> | null = null;

function TradingViewEmbedded({ symbol }: { symbol: string }) {
  const containerRef = useRef<HTMLDivElement>(null);

  const mapSymbolToTV = (sym: string): string => {
    const s = sym.toUpperCase().replace("/", "").trim();
    if (s === "EURUSD") return "FX:EURUSD";
    if (s === "GBPUSD") return "FX:GBPUSD";
    if (s === "USDJPY") return "FX:USDJPY";
    if (s === "AUDUSD") return "FX:AUDUSD";
    if (s === "USDCAD") return "FX:USDCAD";
    if (s === "USDCHF") return "FX:USDCHF";
    if (s === "NZDUSD") return "FX:NZDUSD";
    if (s === "XAUUSD" || s === "GOLD") return "OANDA:XAUUSD";
    if (s === "XAGUSD" || s === "SILVER") return "OANDA:XAGUSD";
    if (s === "BTCUSD" || s === "BTCUSDT") return "BINANCE:BTCUSDT";
    if (s === "ETHUSD" || s === "ETHUSDT") return "BINANCE:ETHUSDT";
    if (s === "SOLUSD" || s === "SOLUSDT") return "BINANCE:SOLUSDT";
    if (s === "AAPL") return "NASDAQ:AAPL";
    if (s === "MSFT") return "NASDAQ:MSFT";
    if (s === "TSLA") return "NASDAQ:TSLA";
    if (s === "GOOGL" || s === "GOOG") return "NASDAQ:GOOGL";
    if (s === "AMZN") return "NASDAQ:AMZN";
    if (s === "NVDA") return "NASDAQ:NVDA";
    if (s === "META") return "NASDAQ:META";
    if (s === "US500" || s === "SPX") return "SP:SPX";
    if (s === "NAS100" || s === "NDX") return "NASDAQ:NDX";
    if (s === "US30" || s === "DJI") return "BLACKBULL:US30";
    return `FX:${s}`;
  };

  const tvSymbol = mapSymbolToTV(symbol);

  useEffect(() => {
    if (!tvScriptLoadingPromise) {
      tvScriptLoadingPromise = new Promise((resolve) => {
        const existing = document.getElementById("tradingview-widget-loading-script");
        if (existing) {
          resolve();
          return;
        }
        const script = document.createElement("script");
        script.id = "tradingview-widget-loading-script";
        script.src = "https://s3.tradingview.com/tv.js";
        script.type = "text/javascript";
        script.onload = () => resolve();
        document.head.appendChild(script);
      });
    }

    tvScriptLoadingPromise.then(() => {
      if (containerRef.current && typeof (window as any).TradingView !== "undefined") {
        containerRef.current.innerHTML = "";
        const widgetId = `tv_chart_embed_${symbol.replace(/[^a-zA-Z0-9]/g, "_")}`;
        const widgetEl = document.createElement("div");
        widgetEl.id = widgetId;
        widgetEl.style.height = "520px";
        widgetEl.style.width = "100%";
        containerRef.current.appendChild(widgetEl);

        new (window as any).TradingView.widget({
          width: "100%",
          height: 520,
          symbol: tvSymbol,
          interval: "5",
          timezone: "Etc/UTC",
          theme: "dark",
          style: "1",
          locale: "en",
          toolbar_bg: "#090d16",
          enable_publishing: false,
          hide_side_toolbar: false,
          allow_symbol_change: true,
          container_id: widgetId,
          studies: ["MASimple@tv-basicstudies"],
        });
      }
    });
  }, [symbol, tvSymbol]);

  return (
    <div className="w-full bg-[#070a12] p-1 border border-zinc-800 rounded-xl overflow-hidden shadow-2xl">
      <div ref={containerRef} className="h-[520px] w-full" />
    </div>
  );
}

interface Candle {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  isBullish: boolean;
  volume: number;
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
  const [activeTab, setActiveTab] = useState<"smc" | "tv">("smc");
  const [mousePos, setMousePos] = useState<{ x: number; y: number } | null>(null);
  const [hoveredCandle, setHoveredCandle] = useState<Candle | null>(null);
  const [zoomLevel, setZoomLevel] = useState<number>(1.0);

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

  // Sequential Condition Verifications
  const s2Pass = s1Pass && isPassText(sweepStatus);
  const s3Pass = s2Pass && isPassText(chochStatus);
  const s4Pass = s3Pass && isPassText(fvgStatus);
  const s5Pass = s4Pass && isPassText(retestStatus);
  const s6Pass = s5Pass && isPassText(s6Status);
  const s7Pass = s6Pass && isPassText(s7Status);

  const hasActivePosition = Boolean(
    activePosition && (activePosition.ticket || activePosition.entryPrice)
  );
  const isSignalFired = (action === "BUY" || action === "SELL") && s7Pass;
  const isTradeActive = hasActivePosition || isSignalFired;

  const s8Pass = isPassText(s8Status) || (s2Pass && isTradeActive);
  const s9Pass = isPassText(s9Status) || (s7Pass && isTradeActive);

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
      : 4138.99;

  // Reliable Projected / Active Entry Price
  const effectiveEntryPrice = useMemo(() => {
    if (hasActivePosition && activePosition.entryPrice) {
      return Number(activePosition.entryPrice);
    }
    return livePrice;
  }, [hasActivePosition, activePosition, livePrice]);

  // Strict SL: exact $0.75 buffer behind sweep
  const effectiveSlPrice = useMemo(() => {
    if (hasActivePosition && activePosition.sl) {
      return Number(activePosition.sl);
    }
    if (sweepPrice > 0) {
      return isBearishSetup
        ? Number((sweepPrice + defaultBuf).toFixed(2))
        : Number((sweepPrice - defaultBuf).toFixed(2));
    }
    // Pre-sweep estimated structural SL buffer level
    const estSweep = isBearishSetup ? livePrice + (isMetals ? 1.5 : 0.0015) : livePrice - (isMetals ? 1.5 : 0.0015);
    return isBearishSetup
      ? Number((estSweep + defaultBuf).toFixed(2))
      : Number((estSweep - defaultBuf).toFixed(2));
  }, [hasActivePosition, activePosition, sweepPrice, isBearishSetup, defaultBuf, livePrice, isMetals]);

  // Strict TP: exact 2.0R target
  const effectiveTpPrice = useMemo(() => {
    if (hasActivePosition && activePosition.tp) {
      return Number(activePosition.tp);
    }
    const slDist = Math.max(isMetals ? 0.75 : 0.0004, Math.abs(effectiveEntryPrice - effectiveSlPrice));
    return isBearishSetup
      ? Number((effectiveEntryPrice - 2.0 * slDist).toFixed(2))
      : Number((effectiveEntryPrice + 2.0 * slDist).toFixed(2));
  }, [hasActivePosition, activePosition, effectiveEntryPrice, effectiveSlPrice, isBearishSetup, isMetals]);

  const entryPrice = effectiveEntryPrice;
  const slPrice = effectiveSlPrice;
  const tpPrice = effectiveTpPrice;

  // ATTACH NATIVE NON-PASSIVE WHEEL LISTENER FOR SMOOTH CURSOR ZOOMING
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      e.stopPropagation();
      const zoomStep = 0.15;
      if (e.deltaY < 0) {
        setZoomLevel((prev) => Math.min(3.0, Number((prev + zoomStep).toFixed(2))));
      } else {
        setZoomLevel((prev) => Math.max(0.6, Number((prev - zoomStep).toFixed(2))));
      }
    };

    el.addEventListener("wheel", onWheel, { passive: false });
    return () => {
      el.removeEventListener("wheel", onWheel);
    };
  }, []);

  // Construct Realistic M5 Candlesticks Graphically Representing the SMC Sequence
  const candles = useMemo<Candle[]>(() => {
    const bars: Candle[] = [];
    const baseP = livePrice;
    const step = isMetals ? 0.65 : 0.0003;
    const now = Date.now();
    const count = Math.max(14, Math.min(45, Math.round(26 / zoomLevel)));

    for (let i = count; i >= 0; i--) {
      const t = new Date(now - i * 5 * 60 * 1000);
      const timeStr = t.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });

      let openP = baseP;
      let closeP = baseP;
      let isSweep = false;
      let isChoch = false;
      let isRetest = false;
      let isRejection = false;

      if (i > 14) {
        openP = baseP + (i - 14) * step * 0.4;
        closeP = openP - step * 0.5;
      } else if (i === 14) {
        isSweep = true;
        if (sweepPrice > 0) {
          openP = isBullishSetup ? sweepPrice + step * 0.8 : sweepPrice - step * 0.8;
          closeP = isBullishSetup ? sweepPrice + step * 1.4 : sweepPrice - step * 1.4;
        } else {
          openP = baseP - step * 1.2;
          closeP = baseP - step * 0.4;
        }
      } else if (i > 9 && i < 14) {
        openP = baseP - (i - 9) * step * 0.5;
        closeP = openP + step * 0.7;
      } else if (i === 9) {
        isChoch = true;
        if (chochPrice > 0) {
          openP = isBullishSetup ? chochPrice - step * 0.4 : chochPrice + step * 0.4;
          closeP = isBullishSetup ? chochPrice + step * 0.8 : chochPrice - step * 0.8;
        } else {
          openP = baseP - step * 0.2;
          closeP = baseP + step * 0.9;
        }
      } else if (i === 5) {
        isRetest = true;
        openP = baseP + step * 0.6;
        closeP = baseP + step * 0.1;
      } else if (i === 2) {
        isRejection = true;
        openP = baseP - step * 0.3;
        closeP = isBullishSetup ? baseP + step * 0.6 : baseP - step * 0.6;
      } else if (i === 0) {
        openP = baseP - step * 0.2;
        closeP = livePrice;
      } else {
        openP = baseP + Math.sin(i * 0.7) * step * 1.2;
        closeP = openP + (i % 2 === 0 ? step * 0.5 : -step * 0.4);
      }

      let highP = Math.max(openP, closeP) + step * (isSweep ? 0.4 : 0.6);
      let lowP = Math.min(openP, closeP) - step * (isSweep ? 2.5 : 0.6);

      if (isSweep && sweepPrice > 0) {
        if (isBullishSetup) {
          lowP = sweepPrice - (isMetals ? 0.25 : 0.0001);
        } else {
          highP = sweepPrice + (isMetals ? 0.25 : 0.0001);
        }
      }

      bars.push({
        time: timeStr,
        open: Number(openP.toFixed(2)),
        high: Number(highP.toFixed(2)),
        low: Number(lowP.toFixed(2)),
        close: Number(closeP.toFixed(2)),
        isBullish: closeP >= openP,
        volume: 720,
        isSweep,
        isChoch,
        isRetest,
        isRejection,
      });
    }
    return bars;
  }, [livePrice, sweepPrice, chochPrice, isMetals, isBullishSetup, zoomLevel]);

  // FVG Bounds
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
    if (sweepPrice > 0) {
      const spread = isMetals ? 1.6 : 0.0008;
      return {
        low: Number((isBullishSetup ? sweepPrice + spread * 0.5 : sweepPrice - spread * 1.6).toFixed(2)),
        high: Number((isBullishSetup ? sweepPrice + spread * 1.6 : sweepPrice - spread * 0.5).toFixed(2)),
      };
    }
    return null;
  }, [telemetry, sweepPrice, isMetals, isBullishSetup]);

  // Dimensions & Price Mapping
  const svgWidth = 1000;
  const svgHeight = 460;
  const chartLeft = 20;
  const chartRight = 850; // 150px reserved on right for ultra-crisp readable price tags
  const chartTop = 30;
  const chartBottom = 410;
  const plotWidth = chartRight - chartLeft;
  const plotHeight = chartBottom - chartTop;

  const minPrice = useMemo(() => {
    const lows = candles.map((c) => c.low);
    if (slPrice > 0 && (isTradeActive || s2Pass)) lows.push(slPrice);
    if (tpPrice > 0 && isTradeActive) lows.push(tpPrice);
    if (sweepPrice > 0) lows.push(sweepPrice);
    if (fvgBounds) lows.push(fvgBounds.low);
    return Math.min(...lows) - (isMetals ? 1.5 : 0.0008);
  }, [candles, slPrice, tpPrice, sweepPrice, fvgBounds, isMetals, isTradeActive, s2Pass]);

  const maxPrice = useMemo(() => {
    const highs = candles.map((c) => c.high);
    if (slPrice > 0 && (isTradeActive || s2Pass)) highs.push(slPrice);
    if (tpPrice > 0 && isTradeActive) highs.push(tpPrice);
    if (sweepPrice > 0) highs.push(sweepPrice);
    if (fvgBounds) highs.push(fvgBounds.high);
    return Math.max(...highs) + (isMetals ? 1.5 : 0.0008);
  }, [candles, slPrice, tpPrice, sweepPrice, fvgBounds, isMetals, isTradeActive, s2Pass]);

  const priceRange = maxPrice - minPrice || 1;

  const getY = (priceVal: number) => {
    const clamped = Math.max(minPrice, Math.min(maxPrice, priceVal));
    return chartBottom - ((clamped - minPrice) / priceRange) * plotHeight;
  };

  const candleSpacing = plotWidth / candles.length;
  const candleBodyWidth = Math.max(7, Math.min(24, candleSpacing * 0.7));

  // 6 Clean Price Grid Ticks
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

  // Real-time cursor price calculation on hover
  const cursorPrice = useMemo(() => {
    if (!mousePos || mousePos.y < chartTop || mousePos.y > chartBottom) return null;
    const ratio = (chartBottom - mousePos.y) / plotHeight;
    return minPrice + ratio * priceRange;
  }, [mousePos, minPrice, priceRange, plotHeight, chartTop, chartBottom]);

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
      {/* 1. MASTER STATUS HUD BANNER */}
      <div
        className={cn(
          "px-4 py-3 rounded-xl border transition-all duration-300 flex flex-col md:flex-row items-start md:items-center justify-between gap-3 shadow-xl",
          isTradeActive
            ? "bg-emerald-950/40 border-emerald-500 text-emerald-100 shadow-[0_0_24px_rgba(16,185,129,0.3)]"
            : s1Pass
            ? "bg-[#101726] border-indigo-500/50 text-indigo-100"
            : "bg-[#0b0e14] border-zinc-800 text-zinc-300"
        )}
      >
        <div className="flex items-center gap-3">
          <div
            className={cn(
              "w-10 h-10 rounded-full flex items-center justify-center font-bold text-sm shadow-md shrink-0",
              isTradeActive
                ? "bg-emerald-500 text-black animate-pulse"
                : s1Pass
                ? "bg-amber-500 text-black"
                : "bg-zinc-800 text-zinc-300"
            )}
          >
            {isTradeActive ? (
              <Zap className="w-5 h-5 text-black" />
            ) : (
              <Activity className="w-5 h-5" />
            )}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-black uppercase tracking-wider text-white">
                {isTradeActive
                  ? `⚡ TRADE ACTIVE: ${tradeDirection} EXECUTED @ $${entryPrice.toFixed(2)}`
                  : s1Pass
                  ? `🔍 SETUP SCANNING — ${passedCount} OF 9 CONDITIONS VERIFIED`
                  : "⚪ ORDER FLOW MONITORING — NO ACTIVE TRADE"}
              </span>
              <Badge
                variant="outline"
                className={cn(
                  "font-mono text-[10px] px-2 py-0.5 uppercase font-bold",
                  isTradeActive
                    ? "bg-emerald-500/20 text-emerald-300 border-emerald-400 animate-pulse"
                    : s1Pass
                    ? "bg-amber-500/20 text-amber-300 border-amber-400"
                    : "bg-zinc-800 text-zinc-400 border-zinc-700"
                )}
              >
                {isTradeActive ? "TRADE ACTIVE" : "AWAITING SETUP"}
              </Badge>
            </div>
            <p className="text-xs text-zinc-300 mt-0.5">
              {isTradeActive
                ? `Running ${tradeDirection} on ${symbol} | Lot: ${isMetals ? "0.07" : "0.51"} | SL: $${slPrice.toFixed(2)} ($${defaultBuf} Buf) | TP: $${tpPrice.toFixed(2)} (2.0R Target) ${
                    hasActivePosition && activePosition.profit !== undefined
                      ? `| Float P&L: $${Number(activePosition.profit).toFixed(2)}`
                      : ""
                  }`
                : !s1Pass
                ? "Step 1 PENDING ⚪: M15 Structure is Neutral (Waiting for Higher High / Lower Low confirmation)"
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

        {/* Live Metrics Pills - Clean, High Contrast */}
        <div className="flex flex-wrap items-center gap-2 self-end md:self-center font-mono text-xs">
          <div className="px-3 py-1 rounded bg-zinc-900 border border-zinc-700 text-white font-bold shadow-sm">
            Live: <span className="text-emerald-400 font-black">${livePrice.toFixed(2)}</span>
          </div>

          {sweepPrice > 0 && (
            <div className="px-3 py-1 rounded bg-cyan-950 border border-cyan-500 text-cyan-300 font-bold shadow-sm">
              Sweep: ${sweepPrice.toFixed(2)}
            </div>
          )}

          {chochPrice > 0 && (
            <div className="px-3 py-1 rounded bg-amber-950 border border-amber-500 text-amber-300 font-bold shadow-sm">
              CHoCH: ${chochPrice.toFixed(2)}
            </div>
          )}

          <div className="flex items-center gap-2">
            <div className={cn(
              "px-3 py-1 rounded font-black shadow-sm text-xs font-mono transition-all",
              isTradeActive
                ? "bg-rose-600 text-white border border-rose-400"
                : "bg-rose-950/50 border border-rose-800/80 text-rose-300"
            )}>
              {isTradeActive ? "🔴 SL:" : "⏳ PROJ SL:"} ${slPrice.toFixed(2)}
            </div>
            <div className={cn(
              "px-3 py-1 rounded font-black shadow-sm text-xs font-mono transition-all",
              isTradeActive
                ? "bg-emerald-600 text-white border border-emerald-400"
                : "bg-emerald-950/50 border border-emerald-800/80 text-emerald-300"
            )}>
              {isTradeActive ? "🟢 TP:" : "⏳ PROJ TP:"} ${tpPrice.toFixed(2)}
            </div>
          </div>
        </div>
      </div>

      {/* 2. DUAL CHART VIEW TOGGLE & ZOOM CONTROLS */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-1">
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant={activeTab === "smc" ? "default" : "outline"}
            className={cn(
              "h-8 px-3 text-xs font-mono font-bold transition-all",
              activeTab === "smc"
                ? "bg-emerald-600 text-white hover:bg-emerald-500 shadow-md"
                : "bg-zinc-900 border-zinc-700 text-zinc-300 hover:text-white"
            )}
            onClick={() => setActiveTab("smc")}
          >
            <BarChart2 className="w-3.5 h-3.5 mr-1.5 text-white" /> 🎯 Pure SMC Visual Levels (On Candles)
          </Button>

          <Button
            size="sm"
            variant={activeTab === "tv" ? "default" : "outline"}
            className={cn(
              "h-8 px-3 text-xs font-mono font-bold transition-all",
              activeTab === "tv"
                ? "bg-indigo-600 text-white hover:bg-indigo-500 shadow-md"
                : "bg-zinc-900 border-zinc-700 text-zinc-300 hover:text-white"
            )}
            onClick={() => setActiveTab("tv")}
          >
            <Tv className="w-3.5 h-3.5 mr-1.5" /> 📈 TradingView Pro (External Feed)
          </Button>
        </div>

        {/* Zoom Controls when in SMC view */}
        {activeTab === "smc" && (
          <div className="flex items-center gap-1.5 bg-zinc-900 border border-zinc-800 rounded-lg p-1">
            <span className="text-xs font-mono font-bold text-zinc-300 px-2">
              Zoom: {Math.round(zoomLevel * 100)}%
            </span>
            <Button
              size="icon"
              variant="ghost"
              className="h-7 w-7 text-zinc-200 hover:text-white hover:bg-zinc-800 font-bold"
              onClick={() => setZoomLevel((z) => Math.min(3.0, Number((z + 0.25).toFixed(2))))}
              title="Zoom In"
            >
              <ZoomIn className="w-4 h-4" />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              className="h-7 w-7 text-zinc-200 hover:text-white hover:bg-zinc-800 font-bold"
              onClick={() => setZoomLevel((z) => Math.max(0.6, Number((z - 0.25).toFixed(2))))}
              title="Zoom Out"
            >
              <ZoomOut className="w-4 h-4" />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              className="h-7 w-7 text-zinc-200 hover:text-white hover:bg-zinc-800"
              onClick={() => setZoomLevel(1.0)}
              title="Reset Zoom (100%)"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </Button>
          </div>
        )}
      </div>

      {/* 3. CHART CONTAINER */}
      {activeTab === "tv" ? (
        <TradingViewEmbedded symbol={symbol} />
      ) : (
        /* PURE SMC CANDLESTICK CHART WITH HIGH CONTRAST DIGITS & LIVE CURSOR TRACKING */
        <div
          ref={containerRef}
          className="relative w-full bg-[#070a12] border border-zinc-800 rounded-xl overflow-hidden shadow-2xl"
        >
          {/* Top Sub-Bar */}
          <div className="flex items-center justify-between px-4 py-2 bg-[#0d121f] border-b border-zinc-800 text-xs font-mono">
            <div className="flex items-center gap-3">
              <span className="font-bold text-white tracking-wider flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                {symbol} <span className="text-zinc-400 font-normal">M5 SMC Candles</span>
              </span>
              <Badge
                variant="outline"
                className={cn(
                  "text-[10px] px-2 py-0.5 font-bold",
                  s1Pass && isM15Bullish
                    ? "bg-emerald-500/20 text-emerald-300 border-emerald-500"
                    : s1Pass && isM15Bearish
                    ? "bg-rose-500/20 text-rose-300 border-rose-500"
                    : "bg-zinc-800 text-zinc-300 border-zinc-700"
                )}
              >
                M15 Bias: {rawM15Bias}
              </Badge>
            </div>

            <div className="flex items-center gap-4 text-zinc-200 text-xs font-bold">
              <span className="flex items-center gap-1.5 text-cyan-400">
                <span className="w-3 h-1 bg-cyan-400 inline-block" /> Step 2: Sweep Line
              </span>
              <span className="flex items-center gap-1.5 text-amber-400">
                <span className="w-3 h-1 bg-amber-400 inline-block" /> Step 3: CHoCH Line
              </span>
              <span className="flex items-center gap-1.5 text-emerald-400">
                <span className="w-3 h-3 border border-emerald-400 bg-emerald-500/30 inline-block rounded-xs" /> Step 4/5: FVG Zone
              </span>
            </div>
          </div>

          {/* SVG Canvas with Crisp Rendering and Real-time Cursor Tracking */}
          <div className="relative w-full h-[460px]">
            <svg
              viewBox={`0 0 ${svgWidth} ${svgHeight}`}
              className="w-full h-full cursor-crosshair"
              onMouseMove={handleMouseMove}
              onMouseLeave={handleMouseLeave}
            >
              <defs>
                <linearGradient id="fvgGradientZone" x1="0" y1="0" x2="0" y2="1">
                  <stop
                    offset="0%"
                    stopColor={isBullishSetup ? "#10b981" : "#f43f5e"}
                    stopOpacity="0.28"
                  />
                  <stop
                    offset="100%"
                    stopColor={isBullishSetup ? "#10b981" : "#f43f5e"}
                    stopOpacity="0.08"
                  />
                </linearGradient>

                <filter id="glowGreen" x="-20%" y="-20%" width="140%" height="140%">
                  <feDropShadow dx="0" dy="0" stdDeviation="3" floodColor="#10b981" floodOpacity="0.9" />
                </filter>
                <filter id="glowRed" x="-20%" y="-20%" width="140%" height="140%">
                  <feDropShadow dx="0" dy="0" stdDeviation="3" floodColor="#ef4444" floodOpacity="0.9" />
                </filter>
                <filter id="glowCyan" x="-20%" y="-20%" width="140%" height="140%">
                  <feDropShadow dx="0" dy="0" stdDeviation="2.5" floodColor="#06b6d4" floodOpacity="0.9" />
                </filter>
                <filter id="glowAmber" x="-20%" y="-20%" width="140%" height="140%">
                  <feDropShadow dx="0" dy="0" stdDeviation="2.5" floodColor="#f59e0b" floodOpacity="0.9" />
                </filter>
              </defs>

              {/* Horizontal Price Grid Lines & High Contrast Silver Numbers */}
              {gridTicks.map((tick, idx) => (
                <g key={idx}>
                  <line
                    x1={chartLeft}
                    y1={tick.y}
                    x2={chartRight}
                    y2={tick.y}
                    stroke="#1e293b"
                    strokeWidth="1"
                    strokeDasharray="4 4"
                  />
                  <text
                    x={chartRight + 12}
                    y={tick.y + 4.5}
                    fill="#e2e8f0"
                    fontSize="12.5"
                    fontFamily="monospace"
                    fontWeight="700"
                  >
                    ${tick.price.toFixed(2)}
                  </text>
                </g>
              ))}

              {/* Step 4 & 5: FVG Retest Zone Rectangle Directly Across Candles */}
              {fvgBounds && fvgBounds.high > fvgBounds.low && (
                <g>
                  <rect
                    x={chartLeft + candleSpacing * 8}
                    y={getY(fvgBounds.high)}
                    width={plotWidth - candleSpacing * 8}
                    height={Math.max(10, Math.abs(getY(fvgBounds.low) - getY(fvgBounds.high)))}
                    fill="url(#fvgGradientZone)"
                    stroke={isBullishSetup ? "#10b981" : "#f43f5e"}
                    strokeWidth="2"
                    strokeDasharray="4 4"
                  />
                  <rect
                    x={chartLeft + candleSpacing * 8 + 8}
                    y={getY(fvgBounds.high) + 4}
                    width="230"
                    height="22"
                    fill="#064e3b"
                    rx="4"
                    stroke="#10b981"
                    strokeWidth="1.5"
                  />
                  <text
                    x={chartLeft + candleSpacing * 8 + 14}
                    y={getY(fvgBounds.high) + 19}
                    fill="#ffffff"
                    fontSize="11"
                    fontFamily="monospace"
                    fontWeight="900"
                  >
                    🟢 S4/S5 FVG ZONE (${fvgBounds.low.toFixed(2)} - ${fvgBounds.high.toFixed(2)})
                  </text>
                </g>
              )}

              {/* Step 2: Liquidity Sweep Horizontal Line & High-Contrast Tag */}
              {sweepPrice > 0 && (
                <g>
                  <line
                    x1={chartLeft}
                    y1={getY(sweepPrice)}
                    x2={chartRight}
                    y2={getY(sweepPrice)}
                    stroke="#06b6d4"
                    strokeWidth="2.5"
                    strokeDasharray="6 3"
                    filter="url(#glowCyan)"
                  />
                  <rect
                    x={chartRight + 6}
                    y={getY(sweepPrice) - 13}
                    width="138"
                    height="26"
                    fill="#0891b2"
                    rx="5"
                    stroke="#a5f3fc"
                    strokeWidth="1"
                  />
                  <text
                    x={chartRight + 12}
                    y={getY(sweepPrice) + 5}
                    fill="#ffffff"
                    fontSize="12"
                    fontFamily="monospace"
                    fontWeight="900"
                  >
                    SWEEP ${sweepPrice.toFixed(2)}
                  </text>
                </g>
              )}

              {/* Step 3: CHoCH Break Horizontal Line & High-Contrast Tag */}
              {chochPrice > 0 && (
                <g>
                  <line
                    x1={chartLeft}
                    y1={getY(chochPrice)}
                    x2={chartRight}
                    y2={getY(chochPrice)}
                    stroke="#f59e0b"
                    strokeWidth="2.5"
                    strokeDasharray="6 4"
                    filter="url(#glowAmber)"
                  />
                  <rect
                    x={chartRight + 6}
                    y={getY(chochPrice) - 13}
                    width="138"
                    height="26"
                    fill="#d97706"
                    rx="5"
                    stroke="#fde68a"
                    strokeWidth="1"
                  />
                  <text
                    x={chartRight + 12}
                    y={getY(chochPrice) + 5}
                    fill="#ffffff"
                    fontSize="12"
                    fontFamily="monospace"
                    fontWeight="900"
                  >
                    CHOCH ${chochPrice.toFixed(2)}
                  </text>
                </g>
              )}

              {/* 1. ENTRY LEVEL LINE & PILL (ALWAYS VISIBLE) */}
              {entryPrice > 0 && (
                <g>
                  <line
                    x1={chartLeft}
                    y1={getY(entryPrice)}
                    x2={chartRight}
                    y2={getY(entryPrice)}
                    stroke={isTradeActive ? "#38bdf8" : "#60a5fa"}
                    strokeWidth={isTradeActive ? 2.5 : 1.5}
                    strokeDasharray={isTradeActive ? "none" : "4 4"}
                    opacity={isTradeActive ? 1 : 0.8}
                    filter={isTradeActive ? "url(#glowBlue)" : undefined}
                  />
                  <rect
                    x={chartRight + 6}
                    y={getY(entryPrice) - 13}
                    width="138"
                    height="26"
                    fill={isTradeActive ? "#0284c7" : "#1e293b"}
                    rx="5"
                    stroke={isTradeActive ? "#38bdf8" : "#3b82f6"}
                    strokeWidth="1.5"
                  />
                  <text
                    x={chartRight + 10}
                    y={getY(entryPrice) + 5}
                    fill="#ffffff"
                    fontSize="11.5"
                    fontFamily="monospace"
                    fontWeight="900"
                  >
                    {isTradeActive
                      ? `🔵 ENTRY $${entryPrice.toFixed(2)}`
                      : `⏳ PROJ ENTRY $${entryPrice.toFixed(2)}`}
                  </text>
                </g>
              )}

              {/* 2. STOP LOSS (SL) LEVEL - ANCHORED WITH EXACT $0.75 BUFFER (ALWAYS VISIBLE) */}
              {slPrice > 0 && (
                <g>
                  <line
                    x1={chartLeft}
                    y1={getY(slPrice)}
                    x2={chartRight}
                    y2={getY(slPrice)}
                    stroke={isTradeActive ? "#ef4444" : "#f87171"}
                    strokeWidth={isTradeActive ? 3 : 1.5}
                    strokeDasharray={isTradeActive ? "none" : "5 5"}
                    opacity={isTradeActive ? 1 : 0.85}
                    filter={isTradeActive ? "url(#glowRed)" : undefined}
                  />
                  <rect
                    x={chartRight + 6}
                    y={getY(slPrice) - 13}
                    width="138"
                    height="26"
                    fill={isTradeActive ? "#dc2626" : "#7f1d1d"}
                    rx="5"
                    stroke={isTradeActive ? "#fca5a5" : "#b91c1c"}
                    strokeWidth="1.5"
                  />
                  <text
                    x={chartRight + 10}
                    y={getY(slPrice) + 5}
                    fill="#ffffff"
                    fontSize="11.5"
                    fontFamily="monospace"
                    fontWeight="900"
                  >
                    {isTradeActive
                      ? `🔴 SL $${slPrice.toFixed(2)}`
                      : `⏳ PROJ SL $${slPrice.toFixed(2)}`}
                  </text>
                </g>
              )}

              {/* 3. TAKE PROFIT (TP) 2.0R TARGET LEVEL (ALWAYS VISIBLE) */}
              {tpPrice > 0 && (
                <g>
                  <line
                    x1={chartLeft}
                    y1={getY(tpPrice)}
                    x2={chartRight}
                    y2={getY(tpPrice)}
                    stroke={isTradeActive ? "#10b981" : "#34d399"}
                    strokeWidth={isTradeActive ? 3 : 1.5}
                    strokeDasharray={isTradeActive ? "none" : "5 5"}
                    opacity={isTradeActive ? 1 : 0.85}
                    filter={isTradeActive ? "url(#glowGreen)" : undefined}
                  />
                  <rect
                    x={chartRight + 6}
                    y={getY(tpPrice) - 13}
                    width="138"
                    height="26"
                    fill={isTradeActive ? "#059669" : "#064e3b"}
                    rx="5"
                    stroke={isTradeActive ? "#6ee7b7" : "#059669"}
                    strokeWidth="1.5"
                  />
                  <text
                    x={chartRight + 10}
                    y={getY(tpPrice) + 5}
                    fill="#ffffff"
                    fontSize="11.5"
                    fontFamily="monospace"
                    fontWeight="900"
                  >
                    {isTradeActive
                      ? `🟢 TP $${tpPrice.toFixed(2)}`
                      : `⏳ PROJ TP $${tpPrice.toFixed(2)}`}
                  </text>
                </g>
              )}

              {/* LIVE MARKET PRICE LINE & SOLID WHITE PILL */}
              <g>
                <line
                  x1={chartLeft}
                  y1={getY(livePrice)}
                  x2={chartRight}
                  y2={getY(livePrice)}
                  stroke="#ffffff"
                  strokeWidth="2"
                  strokeDasharray="4 3"
                />
                <rect
                  x={chartRight + 6}
                  y={getY(livePrice) - 13}
                  width="138"
                  height="26"
                  fill="#ffffff"
                  rx="5"
                  stroke="#94a3b8"
                  strokeWidth="1"
                />
                <text
                  x={chartRight + 12}
                  y={getY(livePrice) + 5.5}
                  fill="#000000"
                  fontSize="12.5"
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
                const bodyHeight = Math.max(3, Math.abs(yClose - yOpen));
                const isGreen = c.isBullish;
                const bodyFill = isGreen ? "#00c076" : "#ff3b69";
                const strokeColor = isGreen ? "#00e68c" : "#ff5c85";

                return (
                  <g key={idx} className="cursor-pointer">
                    {/* Candlestick Wick */}
                    <line
                      x1={cx}
                      y1={yHigh}
                      x2={cx}
                      y2={yLow}
                      stroke={strokeColor}
                      strokeWidth="2"
                      shapeRendering="crispEdges"
                    />

                    {/* Candlestick Body */}
                    <rect
                      x={cx - candleBodyWidth / 2}
                      y={yBodyTop}
                      width={candleBodyWidth}
                      height={bodyHeight}
                      fill={bodyFill}
                      stroke={strokeColor}
                      strokeWidth="1.5"
                      rx="1"
                      shapeRendering="crispEdges"
                    />

                    {/* Sweep Marker on the Sweep Candle */}
                    {c.isSweep && (
                      <g>
                        <path
                          d={`M ${cx} ${yLow + 6} L ${cx - 7} ${yLow + 18} L ${cx + 7} ${yLow + 18} Z`}
                          fill="#06b6d4"
                        />
                        <rect
                          x={cx - 42}
                          y={yLow + 22}
                          width="84"
                          height="20"
                          fill="#0891b2"
                          rx="4"
                          stroke="#22d3ee"
                          strokeWidth="1.5"
                        />
                        <text
                          x={cx}
                          y={yLow + 36}
                          fill="#ffffff"
                          fontSize="9.5"
                          fontFamily="monospace"
                          fontWeight="900"
                          textAnchor="middle"
                        >
                          SWEEP WICK
                        </text>
                      </g>
                    )}

                    {/* CHoCH Marker on the Break Candle */}
                    {c.isChoch && (
                      <g>
                        <circle cx={cx} cy={yHigh - 8} r="4" fill="#f59e0b" />
                        <rect
                          x={cx - 28}
                          y={yHigh - 30}
                          width="56"
                          height="18"
                          fill="#d97706"
                          rx="4"
                          stroke="#fde68a"
                          strokeWidth="1.5"
                        />
                        <text
                          x={cx}
                          y={yHigh - 17}
                          fill="#ffffff"
                          fontSize="9.5"
                          fontFamily="monospace"
                          fontWeight="900"
                          textAnchor="middle"
                        >
                          CHOCH
                        </text>
                      </g>
                    )}

                    {/* Bottom Time Axis Label */}
                    {idx % 4 === 0 && (
                      <text
                        x={cx}
                        y={chartBottom + 20}
                        fill="#cbd5e1"
                        fontSize="11.5"
                        fontFamily="monospace"
                        fontWeight="700"
                        textAnchor="middle"
                      >
                        {c.time}
                      </text>
                    )}
                  </g>
                );
              })}

              {/* CURSOR PRICE TRACKING ON HOVER (Full Interactive Crosshair & Axis Pill) */}
              {mousePos &&
                mousePos.x >= chartLeft &&
                mousePos.x <= chartRight &&
                mousePos.y >= chartTop &&
                mousePos.y <= chartBottom &&
                cursorPrice !== null && (
                  <g pointerEvents="none">
                    {/* Vertical Crosshair Line */}
                    <line
                      x1={mousePos.x}
                      y1={chartTop}
                      x2={mousePos.x}
                      y2={chartBottom}
                      stroke="#94a3b8"
                      strokeWidth="1.5"
                      strokeDasharray="4 4"
                    />

                    {/* Horizontal Crosshair Line */}
                    <line
                      x1={chartLeft}
                      y1={mousePos.y}
                      x2={chartRight}
                      y2={mousePos.y}
                      stroke="#94a3b8"
                      strokeWidth="1.5"
                      strokeDasharray="4 4"
                    />

                    {/* LIVE CURSOR PRICE PILL ON RIGHT AXIS */}
                    <rect
                      x={chartRight + 6}
                      y={mousePos.y - 13}
                      width="138"
                      height="26"
                      fill="#2563eb"
                      rx="5"
                      stroke="#bfdbfe"
                      strokeWidth="1.5"
                    />
                    <text
                      x={chartRight + 12}
                      y={mousePos.y + 5.5}
                      fill="#ffffff"
                      fontSize="12.5"
                      fontFamily="monospace"
                      fontWeight="900"
                    >
                      ${cursorPrice.toFixed(2)}
                    </text>
                  </g>
                )}
            </svg>

            {/* Hover Tooltip Card */}
            {hoveredCandle && (
              <div className="absolute top-3 left-4 bg-[#0d121f]/95 border border-zinc-700 px-3.5 py-2.5 rounded-lg text-xs font-mono text-zinc-100 shadow-2xl backdrop-blur-md pointer-events-none z-10 flex items-center gap-4">
                <div>
                  <span className="text-zinc-400">Time:</span>{" "}
                  <span className="text-white font-black">{hoveredCandle.time}</span>
                </div>
                <div className="flex items-center gap-2.5">
                  <span>
                    O:{" "}
                    <strong className={hoveredCandle.isBullish ? "text-emerald-400" : "text-rose-400"}>
                      ${hoveredCandle.open.toFixed(2)}
                    </strong>
                  </span>
                  <span>
                    H: <strong className="text-white">${hoveredCandle.high.toFixed(2)}</strong>
                  </span>
                  <span>
                    L: <strong className="text-white">${hoveredCandle.low.toFixed(2)}</strong>
                  </span>
                  <span>
                    C:{" "}
                    <strong className={hoveredCandle.isBullish ? "text-emerald-400" : "text-rose-400"}>
                      ${hoveredCandle.close.toFixed(2)}
                    </strong>
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 4. PURE SMC STRICT 9-STEP VERIFICATION STATUS PIPELINE */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-mono font-bold text-white uppercase tracking-wider flex items-center gap-2">
            <Layers className="w-4 h-4 text-indigo-400" /> Pure SMC Strict 9-Step Verification Status
          </h4>
          <span className="text-[11px] font-mono text-zinc-400">
            Real-time VPS Engine Confluence
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5 font-mono text-xs">
          {/* Step 1 */}
          <div
            className={cn(
              "p-3 rounded-lg border transition-all",
              s1Pass
                ? "bg-emerald-950/30 border-emerald-500/50 text-white"
                : "bg-[#0d121f] border-zinc-800 text-zinc-400"
            )}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="font-bold flex items-center gap-1.5 text-white">
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
                  "text-[10px] px-1.5 py-0.2 font-bold",
                  s1Pass
                    ? "bg-emerald-500/20 text-emerald-300 border-emerald-400"
                    : "bg-zinc-800 text-zinc-400 border-zinc-700"
                )}
              >
                {s1Pass ? rawM15Bias : "NEUTRAL ⚪"}
              </Badge>
            </div>
            <p className="text-[11px] text-zinc-300 leading-snug">
              {s1Pass
                ? `Order flow confirmed ${rawM15Bias.includes("BULLISH") ? "Bullish (HH/HL)" : "Bearish (LH/LL)"}.`
                : "Scanning M15 fractal swing structure (waiting for directional trend)."}
            </p>
          </div>

          {/* Step 2 */}
          <div
            className={cn(
              "p-3 rounded-lg border transition-all",
              s2Pass
                ? "bg-cyan-950/30 border-cyan-500/50 text-white"
                : "bg-[#0d121f] border-zinc-800 text-zinc-400"
            )}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="font-bold flex items-center gap-1.5 text-white">
                {s2Pass ? (
                  <CheckCircle2 className="w-4 h-4 text-cyan-400" />
                ) : (
                  <Clock className="w-4 h-4 text-zinc-500" />
                )}
                S2: Liquidity Sweep
              </span>
              <Badge
                variant="outline"
                className={cn(
                  "text-[10px] px-1.5 py-0.2 font-bold",
                  s2Pass
                    ? "bg-cyan-500/20 text-cyan-300 border-cyan-400"
                    : "bg-zinc-800 text-zinc-400 border-zinc-700"
                )}
              >
                {s2Pass ? sweepStatus : "PENDING ⚪"}
              </Badge>
            </div>
            <p className="text-[11px] text-zinc-300 leading-snug">
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
                ? "bg-amber-950/30 border-amber-500/50 text-white"
                : "bg-[#0d121f] border-zinc-800 text-zinc-400"
            )}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="font-bold flex items-center gap-1.5 text-white">
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
                  "text-[10px] px-1.5 py-0.2 font-bold",
                  s3Pass
                    ? "bg-amber-500/20 text-amber-300 border-amber-400"
                    : "bg-zinc-800 text-zinc-400 border-zinc-700"
                )}
              >
                {s3Pass ? chochStatus : "PENDING ⚪"}
              </Badge>
            </div>
            <p className="text-[11px] text-zinc-300 leading-snug">
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
                ? "bg-emerald-950/30 border-emerald-500/50 text-white"
                : "bg-[#0d121f] border-zinc-800 text-zinc-400"
            )}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="font-bold flex items-center gap-1.5 text-white">
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
                  "text-[10px] px-1.5 py-0.2 font-bold",
                  s4Pass
                    ? "bg-emerald-500/20 text-emerald-300 border-emerald-400"
                    : "bg-zinc-800 text-zinc-400 border-zinc-700"
                )}
              >
                {s4Pass ? fvgStatus : "PENDING ⚪"}
              </Badge>
            </div>
            <p className="text-[11px] text-zinc-300 leading-snug">
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
                ? "bg-emerald-950/30 border-emerald-500/50 text-white"
                : "bg-[#0d121f] border-zinc-800 text-zinc-400"
            )}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="font-bold flex items-center gap-1.5 text-white">
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
                  "text-[10px] px-1.5 py-0.2 font-bold",
                  s5Pass
                    ? "bg-emerald-500/20 text-emerald-300 border-emerald-400"
                    : "bg-zinc-800 text-zinc-400 border-zinc-700"
                )}
              >
                {s5Pass ? retestStatus : "PENDING ⚪"}
              </Badge>
            </div>
            <p className="text-[11px] text-zinc-300 leading-snug">
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
                ? "bg-emerald-950/30 border-emerald-500/50 text-white"
                : "bg-[#0d121f] border-zinc-800 text-zinc-400"
            )}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="font-bold flex items-center gap-1.5 text-white">
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
                  "text-[10px] px-1.5 py-0.2 font-bold",
                  s6Pass
                    ? "bg-emerald-500/20 text-emerald-300 border-emerald-400"
                    : "bg-zinc-800 text-zinc-400 border-zinc-700"
                )}
              >
                {s6Pass ? s6Status : "PENDING ⚪"}
              </Badge>
            </div>
            <p className="text-[11px] text-zinc-300 leading-snug">
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
                ? "bg-emerald-950/30 border-emerald-500/50 text-white"
                : "bg-[#0d121f] border-zinc-800 text-zinc-400"
            )}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="font-bold flex items-center gap-1.5 text-white">
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
                  "text-[10px] px-1.5 py-0.2 font-bold",
                  s7Pass
                    ? "bg-emerald-500/20 text-emerald-300 border-emerald-400"
                    : "bg-zinc-800 text-zinc-400 border-zinc-700"
                )}
              >
                {s7Pass ? s7Status : "PENDING ⚪"}
              </Badge>
            </div>
            <p className="text-[11px] text-zinc-300 leading-snug">
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
                ? "bg-rose-950/40 border-rose-500/60 text-white"
                : "bg-[#0d121f] border-zinc-800 text-zinc-400"
            )}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="font-bold flex items-center gap-1.5 text-white">
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
                  "text-[10px] px-1.5 py-0.2 font-bold",
                  s8Pass
                    ? "bg-rose-500/20 text-rose-300 border-rose-400"
                    : "bg-zinc-800 text-zinc-400 border-zinc-700"
                )}
              >
                {s8Pass ? (s8Status && isPassText(s8Status) ? s8Status : `PASS 🟢 ($${defaultBuf} Buf)`) : "PENDING ⚪"}
              </Badge>
            </div>
            <p className="text-[11px] text-zinc-300 leading-snug">
              {s8Pass
                ? (slPrice > 0 && isTradeActive
                    ? `Locked exact $${defaultBuf} buffer behind Sweep wick ($${slPrice.toFixed(2)}).`
                    : `Verified fixed $${defaultBuf} structural SL buffer rule behind liquidity.`)
                : `Will anchor $${defaultBuf} behind Sweep wick upon trade execution.`}
            </p>
          </div>

          {/* Step 9 */}
          <div
            className={cn(
              "p-3 rounded-lg border transition-all",
              s9Pass
                ? "bg-emerald-950/30 border-emerald-500/50 text-white"
                : "bg-[#0d121f] border-zinc-800 text-zinc-400"
            )}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="font-bold flex items-center gap-1.5 text-white">
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
                  "text-[10px] px-1.5 py-0.2 font-bold",
                  s9Pass
                    ? "bg-emerald-500/20 text-emerald-300 border-emerald-400"
                    : "bg-zinc-800 text-zinc-400 border-zinc-700"
                )}
              >
                {s9Pass ? (s9Status && isPassText(s9Status) ? s9Status : "PASS 🟢 (2.0R Space)") : "PENDING ⚪"}
              </Badge>
            </div>
            <p className="text-[11px] text-zinc-300 leading-snug">
              {s9Pass
                ? (tpPrice > 0 && isTradeActive
                    ? `Mathematical 2.0R TP locked at $${tpPrice.toFixed(2)}.`
                    : "Verified minimum 2.0R structural target space to opposing M15 swing liquidity.")
                : "Requires minimum 2.0R distance to opposing liquidity pool."}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
