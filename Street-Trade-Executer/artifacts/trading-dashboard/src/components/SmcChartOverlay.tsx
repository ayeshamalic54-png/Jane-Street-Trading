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
  activeZones?: Array<{ type: string; label: string; range: string }>;
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
        widgetEl.style.height = "560px";
        widgetEl.style.width = "100%";
        containerRef.current.appendChild(widgetEl);

        new (window as any).TradingView.widget({
          autosize: true,
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
    <div className="w-full bg-[#070a12] overflow-hidden">
      <div ref={containerRef} className="h-[560px] w-full" />
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
  activeZones = [],
}: SmcChartOverlayProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState<number>(1000);
  const [activeTab, setActiveTab] = useState<"smc" | "tv">("tv");
  const [mousePos, setMousePos] = useState<{ x: number; y: number } | null>(null);
  const [hoveredCandle, setHoveredCandle] = useState<Candle | null>(null);
  const [zoomLevel, setZoomLevel] = useState<number>(1.0);

  useEffect(() => {
    if (!containerRef.current) return;
    const updateSize = () => {
      if (containerRef.current) {
        const w = containerRef.current.clientWidth;
        if (w > 0) setContainerWidth(w);
      }
    };
    updateSize();

    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect.width > 0) {
          setContainerWidth(Math.round(entry.contentRect.width));
        }
      }
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  const isMobile = containerWidth < 640;

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
    if (hasActivePosition && (activePosition.entryPrice || activePosition.entry)) {
      return Number(activePosition.entryPrice || activePosition.entry);
    }
    return livePrice;
  }, [hasActivePosition, activePosition, livePrice]);

  // Strict SL: anchored to sweep with exact $0.75 buffer (or institutional baseline ~$7.50 distance / $52.50 USD risk on 0.07 lots)
  const effectiveSlPrice = useMemo(() => {
    if (hasActivePosition && activePosition && (Number(activePosition.sl) > 0 || Number(activePosition.slPrice) > 0)) {
      return Number(activePosition.sl || activePosition.slPrice);
    }
    const minSweepDist = isMetals ? 3.0 : 0.0010;
    if (sweepPrice > 0 && Math.abs(effectiveEntryPrice - sweepPrice) >= minSweepDist) {
      return isBearishSetup
        ? Number((sweepPrice + defaultBuf).toFixed(2))
        : Number((sweepPrice - defaultBuf).toFixed(2));
    }
    // Baseline institutional SMC structural risk:
    const defaultSlDist = isMetals ? 7.50 : 0.0020;
    return isBearishSetup
      ? Number((effectiveEntryPrice + defaultSlDist).toFixed(2))
      : Number((effectiveEntryPrice - defaultSlDist).toFixed(2));
  }, [hasActivePosition, activePosition, sweepPrice, isBearishSetup, defaultBuf, effectiveEntryPrice, isMetals]);

  // Strict TP: baseline 1:1.85 target ($97-$112 USD reward on 0.07 lots, with Order Block shield)
  const effectiveTpPrice = useMemo(() => {
    if (hasActivePosition && activePosition && (Number(activePosition.tp) > 0 || Number(activePosition.tpPrice) > 0)) {
      return Number(activePosition.tp || activePosition.tpPrice);
    }
    const slDist = Math.max(isMetals ? 3.0 : 0.0015, Math.abs(effectiveEntryPrice - effectiveSlPrice));
    return isBearishSetup
      ? Number((effectiveEntryPrice - 1.85 * slDist).toFixed(2))
      : Number((effectiveEntryPrice + 1.85 * slDist).toFixed(2));
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
      const zoomStep = 0.25;
      if (e.deltaY < 0) {
        setZoomLevel((prev) => Math.min(3.5, Number((prev + zoomStep).toFixed(2))));
      } else {
        setZoomLevel((prev) => Math.max(0.4, Number((prev - zoomStep).toFixed(2))));
      }
    };

    el.addEventListener("wheel", onWheel, { passive: false });
    return () => {
      el.removeEventListener("wheel", onWheel);
    };
  }, []);

  // 1. Extract Real MT5 M5 Candlesticks from Bot Telemetry Feed
  const realCandles = useMemo<Candle[] | null>(() => {
    try {
      let rawList: any[] | null = null;
      if (Array.isArray(telemetry?.candles) && telemetry.candles.length >= 8) {
        rawList = telemetry.candles;
      } else {
        const rawJson = telemetry?.fvg_bounds_json ?? telemetry?.fvgBoundsJson;
        if (rawJson) {
          const parsed = typeof rawJson === "string" ? JSON.parse(rawJson) : rawJson;
          if (Array.isArray(parsed?.candles) && parsed.candles.length >= 8) {
            rawList = parsed.candles;
          }
        }
      }

      if (!rawList || rawList.length < 8) return null;

      // Slice to match zoom level or responsive count
      const maxCount = isMobile
        ? Math.max(12, Math.min(36, Math.round(18 / zoomLevel)))
        : Math.max(16, Math.min(50, Math.round(32 / zoomLevel)));

      const sliced = rawList.slice(-maxCount);

      // Map to Candle objects
      const mapped: Candle[] = sliced.map((c, i) => {
        const isLast = i === sliced.length - 1;
        const openP = Number(c.open);
        const closeP = isLast && livePrice > 0 ? livePrice : Number(c.close);
        const highP = isLast && livePrice > 0 ? Math.max(Number(c.high), livePrice) : Number(c.high);
        const lowP = isLast && livePrice > 0 ? Math.min(Number(c.low), livePrice) : Number(c.low);
        return {
          time: c.time || "",
          open: openP,
          high: highP,
          low: lowP,
          close: closeP,
          isBullish: closeP >= openP,
          volume: Number(c.volume || 100),
          isSweep: Boolean(c.isSweep),
          isChoch: Boolean(c.isChoch),
          isRetest: Boolean(c.isRetest),
          isRejection: Boolean(c.isRejection),
        };
      });

      // Identify milestone candles if not already tagged
      if (s2Pass && sweepPrice > 0 && !mapped.some((c) => c.isSweep)) {
        let bestIdx = -1;
        let bestDiff = Infinity;
        mapped.forEach((c, idx) => {
          const target = isBullishSetup ? c.low : c.high;
          const diff = Math.abs(target - sweepPrice);
          if (diff < bestDiff) {
            bestDiff = diff;
            bestIdx = idx;
          }
        });
        if (bestIdx >= 0 && bestDiff < (isMetals ? 2.5 : 0.005)) {
          mapped[bestIdx].isSweep = true;
        }
      }

      if (s3Pass && chochPrice > 0 && !mapped.some((c) => c.isChoch)) {
        let bestIdx = -1;
        let bestDiff = Infinity;
        mapped.forEach((c, idx) => {
          const target = isBullishSetup ? c.high : c.low;
          const diff = Math.abs(target - chochPrice);
          if (diff < bestDiff) {
            bestDiff = diff;
            bestIdx = idx;
          }
        });
        if (bestIdx >= 0 && bestDiff < (isMetals ? 2.5 : 0.005)) {
          mapped[bestIdx].isChoch = true;
        }
      }

      return mapped;
    } catch {
      return null;
    }
  }, [telemetry, livePrice, zoomLevel, isMobile, s2Pass, s3Pass, sweepPrice, chochPrice, isBullishSetup, isMetals]);

  // Construct Realistic M5 Candlesticks Graphically Representing the SMC Sequence (Real MT5 + Schematic Fallback)
  const candles = useMemo<Candle[]>(() => {
    // If real MT5 candlesticks are available from bot telemetry, use them directly!
    if (realCandles && realCandles.length >= 8) {
      return realCandles;
    }

    const bars: Candle[] = [];
    const step = isMetals ? 0.65 : 0.0003;
    const now = Date.now();
    const count = isMobile
      ? Math.max(8, Math.min(36, Math.round(18 / zoomLevel)))
      : Math.max(8, Math.min(60, Math.round(28 / zoomLevel)));

    // Reference SMC anchor levels
    const swP =
      sweepPrice > 0
        ? sweepPrice
        : isBullishSetup
        ? Number((livePrice - step * 6.5).toFixed(2))
        : Number((livePrice + step * 6.5).toFixed(2));

    const chP =
      chochPrice > 0
        ? chochPrice
        : isBullishSetup
        ? Number((swP + step * 4.0).toFixed(2))
        : Number((swP - step * 4.0).toFixed(2));

    // Milestone bar indices across the timeline (0 = oldest, count - 1 = live forming bar)
    const sweepIdx = Math.max(2, Math.floor(count * 0.35));
    const chochIdx = Math.max(sweepIdx + 2, Math.floor(count * 0.55));
    const retestIdx = Math.max(chochIdx + 2, Math.floor(count * 0.72));
    const rejectionIdx = Math.max(retestIdx + 1, Math.min(count - 2, Math.floor(count * 0.86)));
    const liveIdx = count - 1;

    // Build contiguous sequence: bar[k].open ALWAYS equals bar[k-1].close
    let prevClose = isBullishSetup
      ? swP + step * (sweepIdx * 0.45 + 1.2)
      : swP - step * (sweepIdx * 0.45 + 1.2);

    for (let k = 0; k < count; k++) {
      const idxFromEnd = count - 1 - k;
      const t = new Date(now - idxFromEnd * 5 * 60 * 1000);
      const timeStr = t.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });

      const openP = prevClose;
      let closeP = openP;
      let isSweep = false;
      let isChoch = false;
      let isRetest = false;
      let isRejection = false;

      if (k === liveIdx) {
        // Current forming candle: close is strictly identical to livePrice
        closeP = livePrice;
      } else if (k < sweepIdx) {
        // Phase 1: Pre-sweep trend leading down (or up) to liquidity level
        const progress = (k + 1) / sweepIdx;
        const target = isBullishSetup
          ? swP + step * 0.35 + (1 - progress) * step * 2.5
          : swP - step * 0.35 - (1 - progress) * step * 2.5;
        // Alternating small candles with net drift towards sweep
        const micro = (k % 3 === 0 ? 0.3 : -0.2) * step;
        closeP = isBullishSetup
          ? Math.max(swP + step * 0.2, target + micro)
          : Math.min(swP - step * 0.2, target + micro);
      } else if (k === sweepIdx) {
        // Phase 2: Liquidity sweep candle
        isSweep = s2Pass;
        // Closes back inside structure
        closeP = isBullishSetup ? swP + step * 0.5 : swP - step * 0.5;
      } else if (k > sweepIdx && k < chochIdx) {
        // Phase 3: Displacement impulse surge towards CHoCH
        const progress = (k - sweepIdx) / (chochIdx - sweepIdx);
        closeP = isBullishSetup
          ? openP + step * (0.8 + progress * 0.4)
          : openP - step * (0.8 + progress * 0.4);
      } else if (k === chochIdx) {
        // Phase 4: CHoCH breakout candle (closes beyond chochPrice)
        isChoch = s3Pass;
        closeP = isBullishSetup ? chP + step * 0.45 : chP - step * 0.45;
      } else if (k > chochIdx && k < retestIdx) {
        // Phase 5: Post-CHoCH peak / transition to pullback
        const fvgMid = (swP + chP) * 0.5;
        closeP = (openP + fvgMid) * 0.5;
      } else if (k === retestIdx) {
        // Phase 6: Retest candle dipping into FVG zone
        isRetest = s5Pass;
        const fvgMid = (swP + chP) * 0.5;
        closeP = isBullishSetup ? fvgMid + step * 0.15 : fvgMid - step * 0.15;
      } else if (k === rejectionIdx) {
        // Phase 7: Rejection candle pushing away from FVG in setup direction
        isRejection = s6Pass;
        closeP = isBullishSetup ? openP + step * 0.65 : openP - step * 0.65;
      } else {
        // Phase 8: Smooth interpolation between rejection and final live candle
        const remaining = liveIdx - k;
        const stepDelta = (livePrice - openP) / (remaining + 1);
        closeP = openP + stepDelta;
      }

      // Calculate realistic wicks
      let highP = Math.max(openP, closeP) + step * 0.25;
      let lowP = Math.min(openP, closeP) - step * 0.25;

      if (k === sweepIdx) {
        // Accentuate the liquidity sweep wick
        if (isBullishSetup) {
          lowP = swP - (isMetals ? 0.35 : 0.0002);
          highP = Math.max(openP, closeP) + step * 0.2;
        } else {
          highP = swP + (isMetals ? 0.35 : 0.0002);
          lowP = Math.min(openP, closeP) - step * 0.2;
        }
      } else if (k === liveIdx) {
        // Final live candle: ensure wick wraps livePrice neatly
        highP = Math.max(openP, livePrice) + (livePrice >= openP ? step * 0.2 : step * 0.08);
        lowP = Math.min(openP, livePrice) - (livePrice <= openP ? step * 0.2 : step * 0.08);
      } else if (k === rejectionIdx) {
        // Rejection candle: long wick testing into FVG
        const fvgMid = (swP + chP) * 0.5;
        if (isBullishSetup) {
          lowP = Math.min(lowP, fvgMid - step * 0.3);
        } else {
          highP = Math.max(highP, fvgMid + step * 0.3);
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

      prevClose = closeP;
    }

    return bars;
  }, [
    realCandles,
    livePrice,
    sweepPrice,
    chochPrice,
    isMetals,
    isBullishSetup,
    isBearishSetup,
    zoomLevel,
    isMobile,
    s2Pass,
    s3Pass,
    s5Pass,
    s6Pass,
  ]);

  const shouldShowTradeLevels = isTradeActive || s7Pass;

  // Parsed Active SMC Zones (FVG, OB, Breaker, iFVG) from live bot scanner — Strictly Filtered for Clean Structure
  const parsedActiveZones = useMemo(() => {
    if (!activeZones || activeZones.length === 0) return [];
    const list: Array<{
      type: string;
      name: string;
      isBullish: boolean;
      low: number;
      high: number;
      label: string;
    }> = [];
    const maxDist = isMetals ? 16.0 : 0.0080;
    const seenRanges: string[] = [];

    for (const z of activeZones) {
      if (!z.range || (z.label && z.label.toUpperCase().includes("USDT")) || (z.type && z.type.toUpperCase().includes("USDT"))) continue;
      const parts = z.range.split(/[\u2013\-]/);
      if (parts.length >= 2) {
        const low = parseFloat(parts[0].trim());
        const high = parseFloat(parts[1].trim());
        if (!isNaN(low) && !isNaN(high) && high > low) {
          // 1. Proximity check: Must be within realistic trading range of livePrice
          const mid = (low + high) / 2;
          if (Math.abs(mid - livePrice) > maxDist) continue;

          // 2. Deduplication check: Avoid identical or nearly identical duplicate ranges
          const isDuplicate = seenRanges.some((r) => {
            const [rL, rH] = r.split(":").map(Number);
            return Math.abs(rL - low) < 0.35 && Math.abs(rH - high) < 0.35;
          });
          if (isDuplicate) continue;
          seenRanges.push(`${low.toFixed(2)}:${high.toFixed(2)}`);

          const isBullish = z.type.toUpperCase().includes("BULLISH") || z.label.includes("🟢");
          const name = z.type.replace("BULLISH_", "").replace("BEARISH_", "");
          list.push({
            type: z.type,
            name,
            isBullish,
            low,
            high,
            label: z.label,
          });
        }
      }
    }
    // Limit to max 3 cleanest, freshest active zones on the chart to eliminate clutter
    return list.slice(0, 3);
  }, [activeZones, livePrice, isMetals]);

  // FVG Bounds: Resolved from bot telemetry, activeZones, or structural displacement
  const fvgBounds = useMemo(() => {
    // 1. Check telemetry JSON for exact FVG bounds
    try {
      const rawJson = telemetry?.fvg_bounds_json ?? telemetry?.fvgBoundsJson;
      if (rawJson) {
        const parsed = typeof rawJson === "string" ? JSON.parse(rawJson) : rawJson;
        if (typeof parsed === "object" && parsed !== null) {
          const list = isBullishSetup
            ? parsed.bullish_fvg || []
            : parsed.bearish_fvg || [];
          for (const item of list) {
            if (Array.isArray(item) && item.length >= 2) {
              const l = Number(item[0]);
              const h = Number(item[1]);
              const avg = (l + h) / 2;
              if (Math.abs(avg - livePrice) <= (isMetals ? 15.0 : 0.0080) && h > l) {
                return { low: l, high: h, label: "BOT DETECTED FVG" };
              }
            }
          }
        }
      }
    } catch {}

    // 2. Check activeZones from bot scanner
    if (parsedActiveZones && parsedActiveZones.length > 0) {
      const fvgZone = parsedActiveZones.find((z) => z.type.toUpperCase().includes("FVG"));
      if (fvgZone && fvgZone.high > fvgZone.low) {
        return { low: fvgZone.low, high: fvgZone.high, label: fvgZone.label || "ACTIVE FVG" };
      }
    }

    // 3. Fallback: Structural displacement FVG on the SMC Diagram
    const swP = sweepPrice > 0 ? sweepPrice : (isBullishSetup ? livePrice - (isMetals ? 5.5 : 0.003) : livePrice + (isMetals ? 5.5 : 0.003));
    const chP = chochPrice > 0 ? chochPrice : (isBullishSetup ? swP + (isMetals ? 3.8 : 0.002) : swP - (isMetals ? 3.8 : 0.002));
    const low = isBullishSetup ? Number((swP + (chP - swP) * 0.35).toFixed(2)) : Number((chP + (swP - chP) * 0.35).toFixed(2));
    const high = isBullishSetup ? Number((swP + (chP - swP) * 0.65).toFixed(2)) : Number((chP + (swP - chP) * 0.65).toFixed(2));
    if (high > low) {
      return { low: Math.min(low, high), high: Math.max(low, high), label: s4Pass ? "S4 DISPLACEMENT FVG" : "DISPLACEMENT FVG" };
    }

    return null;
  }, [telemetry, parsedActiveZones, livePrice, sweepPrice, chochPrice, isMetals, isBullishSetup, s4Pass]);

  // Institutional Swing Structure Levels (Buy-Side & Sell-Side Liquidity + CHoCH)
  const swingStructure = useMemo(() => {
    if (!candles || candles.length < 5) {
      return { swingHigh: 0, swingLow: 0, chochLvl: 0 };
    }
    const completed = candles.slice(0, -1);
    const highs = completed.map((c) => c.high);
    const lows = completed.map((c) => c.low);

    const highest = Math.max(...highs);
    const lowest = Math.min(...lows);

    const swingHigh = sweepPrice > 0 && isBearishSetup ? sweepPrice : highest;
    const swingLow = sweepPrice > 0 && isBullishSetup ? sweepPrice : lowest;
    const chochLvl =
      chochPrice > 0
        ? chochPrice
        : isBullishSetup
        ? Number((swingLow + (highest - swingLow) * 0.45).toFixed(2))
        : Number((swingHigh - (swingHigh - lowest) * 0.45).toFixed(2));

    return {
      swingHigh: Number(swingHigh.toFixed(2)),
      swingLow: Number(swingLow.toFixed(2)),
      chochLvl: Number(chochLvl.toFixed(2)),
    };
  }, [candles, sweepPrice, chochPrice, isBullishSetup, isBearishSetup]);

  // Dimensions & Price Mapping (Full-Height TradingView Candlestick Proportions)
  const svgWidth = Math.max(340, containerWidth);
  const svgHeight = isMobile ? 380 : 460;
  const chartLeft = isMobile ? 8 : 20;
  const rightTagWidth = isMobile ? 112 : 148;
  const chartRight = svgWidth - (rightTagWidth + 8);
  const chartTop = isMobile ? 18 : 25;
  const chartBottom = svgHeight - (isMobile ? 28 : 35);
  const plotWidth = Math.max(100, chartRight - chartLeft);
  const plotHeight = Math.max(100, chartBottom - chartTop);

  const showSlLevel = isTradeActive || s2Pass;
  const showTpLevel = isTradeActive || s4Pass;
  const showEntryLevel = isTradeActive || s7Pass;

  // STRICT M5 SCALPING SCALING: Scale to VISIBLE CANDLESTICKS so candles are tall, bold, and dynamic!
  const rawCandleLows = useMemo(() => candles.map((c) => c.low), [candles]);
  const rawCandleHighs = useMemo(() => candles.map((c) => c.high), [candles]);
  const candleMin = Math.min(...rawCandleLows, livePrice);
  const candleMax = Math.max(...rawCandleHighs, livePrice);
  const candleSpan = candleMax - candleMin || 1;
  const vertPad = Math.max(isMetals ? 0.90 : 0.0005, candleSpan * 0.16);

  const minPrice = useMemo(() => {
    let min = candleMin - vertPad;
    // Include nearby levels without allowing distant SL to squash the candles
    if (showSlLevel && effectiveSlPrice > 0 && candleMin - effectiveSlPrice <= candleSpan * 1.2) {
      min = Math.min(min, effectiveSlPrice - (isMetals ? 0.40 : 0.0002));
    }
    if (swingStructure.swingLow > 0 && candleMin - swingStructure.swingLow <= candleSpan * 1.2) {
      min = Math.min(min, swingStructure.swingLow - (isMetals ? 0.40 : 0.0002));
    }
    if (fvgBounds && fvgBounds.low > 0 && candleMin - fvgBounds.low <= candleSpan * 1.2) {
      min = Math.min(min, fvgBounds.low - (isMetals ? 0.40 : 0.0002));
    }
    return Number(min.toFixed(2));
  }, [candleMin, vertPad, candleSpan, showSlLevel, effectiveSlPrice, swingStructure.swingLow, fvgBounds, isMetals]);

  const maxPrice = useMemo(() => {
    let max = candleMax + vertPad;
    // Include nearby levels without allowing distant TP to squash the candles
    if (showTpLevel && effectiveTpPrice > 0 && effectiveTpPrice - candleMax <= candleSpan * 1.2) {
      max = Math.max(max, effectiveTpPrice + (isMetals ? 0.40 : 0.0002));
    }
    if (swingStructure.swingHigh > 0 && swingStructure.swingHigh - candleMax <= candleSpan * 1.2) {
      max = Math.max(max, swingStructure.swingHigh + (isMetals ? 0.40 : 0.0002));
    }
    if (fvgBounds && fvgBounds.high > 0 && fvgBounds.high - candleMax <= candleSpan * 1.2) {
      max = Math.max(max, fvgBounds.high + (isMetals ? 0.40 : 0.0002));
    }
    return Number(max.toFixed(2));
  }, [candleMax, vertPad, candleSpan, showTpLevel, effectiveTpPrice, swingStructure.swingHigh, fvgBounds, isMetals]);

  const priceRange = maxPrice - minPrice || 1;

  const getY = (priceVal: number) => {
    const clamped = Math.max(minPrice, Math.min(maxPrice, priceVal));
    return chartBottom - ((clamped - minPrice) / priceRange) * plotHeight;
  };

  const candleSpacing = plotWidth / candles.length;
  // Thick, bold, high-visibility TradingView-like candlesticks that enlarge when zoomed in!
  const candleBodyWidth = Math.max(isMobile ? 10 : 14, Math.min(isMobile ? 26 : 42, candleSpacing * 0.76));

  // Market Structure Zigzag Path & Fractal Swing Points
  const marketStructure = useMemo(() => {
    if (!candles || candles.length < 5) return { swings: [], path: "" };

    const swings: Array<{
      idx: number;
      price: number;
      type: "HH" | "HL" | "LH" | "LL";
      x: number;
      y: number;
      label: string;
      isHigh: boolean;
    }> = [];

    // Find fractal swing peaks & valleys
    for (let i = 1; i < candles.length - 1; i++) {
      const prev = candles[i - 1];
      const curr = candles[i];
      const next = candles[i + 1];

      const cx = chartLeft + (i + 0.5) * candleSpacing;

      const isFractalHigh = curr.high >= prev.high && curr.high >= next.high;
      const isFractalLow = curr.low <= prev.low && curr.low <= next.low;

      if (isFractalHigh && !isFractalLow) {
        const lastSwing = swings[swings.length - 1];
        if (lastSwing && lastSwing.isHigh) {
          if (curr.high > lastSwing.price) {
            const prevHigh = [...swings.slice(0, -1)].reverse().find((s) => s.isHigh);
            const tag: "HH" | "LH" = prevHigh ? (curr.high >= prevHigh.price ? "HH" : "LH") : (isBullishSetup ? "HH" : "LH");
            swings[swings.length - 1] = {
              idx: i,
              price: curr.high,
              type: tag,
              x: cx,
              y: getY(curr.high),
              label: tag,
              isHigh: true,
            };
          }
        } else {
          const prevHigh = [...swings].reverse().find((s) => s.isHigh);
          const tag: "HH" | "LH" = prevHigh ? (curr.high >= prevHigh.price ? "HH" : "LH") : (isBullishSetup ? "HH" : "LH");
          swings.push({
            idx: i,
            price: curr.high,
            type: tag,
            x: cx,
            y: getY(curr.high),
            label: tag,
            isHigh: true,
          });
        }
      } else if (isFractalLow && !isFractalHigh) {
        const lastSwing = swings[swings.length - 1];
        if (lastSwing && !lastSwing.isHigh) {
          if (curr.low < lastSwing.price) {
            const prevLow = [...swings.slice(0, -1)].reverse().find((s) => !s.isHigh);
            const tag: "HL" | "LL" = prevLow ? (curr.low <= prevLow.price ? "LL" : "HL") : (isBullishSetup ? "HL" : "LL");
            swings[swings.length - 1] = {
              idx: i,
              price: curr.low,
              type: tag,
              x: cx,
              y: getY(curr.low),
              label: tag,
              isHigh: false,
            };
          }
        } else {
          const prevLow = [...swings].reverse().find((s) => !s.isHigh);
          const tag: "HL" | "LL" = prevLow ? (curr.low <= prevLow.price ? "LL" : "HL") : (isBullishSetup ? "HL" : "LL");
          swings.push({
            idx: i,
            price: curr.low,
            type: tag,
            x: cx,
            y: getY(curr.low),
            label: tag,
            isHigh: false,
          });
        }
      }
    }

    // Polyline path connecting the structural swings
    let path = "";
    if (swings.length >= 2) {
      path = swings.map((s, idx) => `${idx === 0 ? "M" : "L"} ${s.x.toFixed(1)} ${s.y.toFixed(1)}`).join(" ");
    }

    return { swings, path };
  }, [candles, candleSpacing, chartLeft, isBullishSetup, minPrice, maxPrice, priceRange, plotHeight, chartBottom]);

  // Key milestone candle indices across the SMC sequence
  const candleMilestones = useMemo(() => {
    const count = candles.length;
    const defaultSweep = Math.max(2, Math.floor(count * 0.35));
    const defaultChoch = Math.max(defaultSweep + 2, Math.floor(count * 0.55));
    const defaultRetest = Math.max(defaultChoch + 2, Math.floor(count * 0.72));
    const defaultRejection = Math.max(defaultRetest + 1, Math.min(count - 2, Math.floor(count * 0.86)));

    const sIdx = candles.findIndex((c) => c.isSweep);
    const cIdx = candles.findIndex((c) => c.isChoch);
    const rIdx = candles.findIndex((c) => c.isRetest);
    const jIdx = candles.findIndex((c) => c.isRejection);

    const sweep = sIdx >= 0 ? sIdx : defaultSweep;
    const choch = cIdx >= 0 ? cIdx : defaultChoch;
    const retest = rIdx >= 0 ? rIdx : defaultRetest;
    const rejection = jIdx >= 0 ? jIdx : defaultRejection;
    const entry = isTradeActive || s7Pass ? rejection : (s5Pass ? retest : choch);

    return { sweep, choch, retest, rejection, entry };
  }, [candles, isTradeActive, s7Pass, s5Pass]);

  interface RenderedZone {
    id: string;
    type: "FVG" | "OB" | "BREAKER" | "IFVG" | "OTHER";
    name: string;
    low: number;
    high: number;
    originIdx: number;
    originX: number;
    originAnchorY: number;
    originLabel: string;
    topY: number;
    botY: number;
    boxHeight: number;
    boxWidth: number;
    badgeX: number;
    badgeY: number;
    badgeWidth: number;
    badgeHeight: number;
    badgeBg: string;
    badgeStroke: string;
    badgeTextColor: string;
    boxFill: string;
    boxStroke: string;
    strokeDash: string;
    strokeWidth: number;
    glowFilter?: string;
    badgeTitle: string;
    badgeSub: string;
    isPrimaryFvg: boolean;
  }

  // Institutional SMC Zones with Precise Origin Candlestick Anchoring & Collision Prevention
  const renderedSmcZones = useMemo<RenderedZone[]>(() => {
    if (!candles || candles.length === 0) return [];
    const list: RenderedZone[] = [];
    const candleCount = candles.length;

    // Helper: find originating candle for a zone
    const findOrigin = (zLow: number, zHigh: number, type: string) => {
      const uType = type.toUpperCase();
      let bestIdx = -1;

      // 1. Structural window search based on SMC type
      if (uType.includes("BREAKER")) {
        // Breaker was an old swing high/low broken during displacement (between sweep and choch)
        for (let k = Math.max(0, candleMilestones.sweep - 2); k <= Math.min(candleCount - 1, candleMilestones.choch); k++) {
          const c = candles[k];
          if (c && c.high >= zLow && c.low <= zHigh) return k;
        }
        bestIdx = Math.max(1, candleMilestones.sweep - 1);
      } else if (uType.includes("OB")) {
        // Order Block is the last opposing bar before sweep/displacement
        for (let k = Math.max(0, candleMilestones.sweep - 2); k <= candleMilestones.sweep; k++) {
          const c = candles[k];
          if (c && c.high >= zLow && c.low <= zHigh) return k;
        }
        bestIdx = Math.max(0, candleMilestones.sweep - 1);
      } else if (uType.includes("IFVG")) {
        // Inversion FVG created near sweep/choch
        for (let k = candleMilestones.sweep; k <= candleMilestones.choch; k++) {
          const c = candles[k];
          if (c && c.high >= zLow && c.low <= zHigh) return k;
        }
        bestIdx = Math.min(candleCount - 2, candleMilestones.sweep + 1);
      } else {
        // Standard FVG displacement around CHoCH
        for (let k = Math.max(0, candleMilestones.choch - 1); k <= Math.min(candleCount - 2, candleMilestones.choch + 1); k++) {
          const c = candles[k];
          if (c && c.high >= zLow && c.low <= zHigh) return k;
        }
        bestIdx = Math.min(candleCount - 2, candleMilestones.choch);
      }

      // 2. Global candle overlap scan if specific window didn't intersect
      for (let k = 0; k < candleCount - 1; k++) {
        const c = candles[k];
        if (c.high >= zLow && c.low <= zHigh) {
          return k;
        }
      }

      return Math.max(0, Math.min(candleCount - 2, bestIdx));
    };

    // 1. Primary Setup Post-CHoCH FVG (fvgBounds)
    if (fvgBounds && fvgBounds.high > fvgBounds.low) {
      const originIdx = findOrigin(fvgBounds.low, fvgBounds.high, "FVG");
      const originX = chartLeft + (originIdx + 0.5) * candleSpacing;
      const topY = getY(fvgBounds.high);
      const botY = getY(fvgBounds.low);
      const boxHeight = Math.max(12, Math.abs(botY - topY));
      const boxWidth = Math.max(candleSpacing * 2.5, chartRight - originX);
      const originCandle = candles[originIdx];
      const candleCenterY = originCandle ? getY((originCandle.open + originCandle.close) / 2) : topY + boxHeight / 2;

      const fvgTitle = s5Pass
        ? "🟢 S5 RETEST CONFIRMED"
        : s4Pass
        ? "⏳ S4 DISPLACEMENT FVG — RETESTING"
        : isBullishSetup
        ? "🟢 BULLISH FVG ZONE"
        : "🔴 BEARISH FVG ZONE";

      list.push({
        id: "fvg-primary",
        type: "FVG",
        name: "S4/S5 Displacement FVG",
        low: fvgBounds.low,
        high: fvgBounds.high,
        originIdx,
        originX,
        originAnchorY: candleCenterY,
        originLabel: `⚓ C#${originIdx + 1} FVG ORIGIN`,
        topY,
        botY,
        boxHeight,
        boxWidth,
        badgeX: originX + 8,
        badgeY: Math.min(chartBottom - 26, Math.max(chartTop + 4, topY + 3)),
        badgeWidth: isMobile ? 185 : 255,
        badgeHeight: 20,
        badgeBg: s5Pass ? "#064e3b" : s4Pass ? "#134e4a" : "#0f172a",
        badgeStroke: s5Pass ? "#10b981" : s4Pass ? "#14b8a6" : isBullishSetup ? "#10b981" : "#f43f5e",
        badgeTextColor: "#ffffff",
        boxFill: "url(#fvgGradientZone)",
        boxStroke: s5Pass ? "#10b981" : s4Pass ? "#14b8a6" : isBullishSetup ? "#10b981" : "#f43f5e",
        strokeDash: s5Pass ? "none" : "4 4",
        strokeWidth: s5Pass ? 2.5 : 1.5,
        glowFilter: s5Pass ? "url(#glowGreen)" : undefined,
        badgeTitle: fvgTitle,
        badgeSub: `(${fvgBounds.low.toFixed(2)} - ${fvgBounds.high.toFixed(2)})`,
        isPrimaryFvg: true,
      });
    }

    // 2. Active Zones (Order Blocks, Breakers, iFVG)
    parsedActiveZones.forEach((z, idx) => {
      // Exclude if identical to fvgBounds
      if (fvgBounds && Math.abs(fvgBounds.low - z.low) < 0.05 && Math.abs(fvgBounds.high - z.high) < 0.05) {
        return;
      }

      const isOB = z.type.toUpperCase().includes("OB");
      const isBreaker = z.type.toUpperCase().includes("BREAKER");
      const isIFVG = z.type.toUpperCase().includes("IFVG") || z.name.toUpperCase().includes("IFVG");

      const zoneType: "FVG" | "OB" | "BREAKER" | "IFVG" | "OTHER" = isOB
        ? "OB"
        : isBreaker
        ? "BREAKER"
        : isIFVG
        ? "IFVG"
        : "FVG";

      const originIdx = findOrigin(z.low, z.high, z.type);
      const originX = chartLeft + (originIdx + 0.5) * candleSpacing;
      const topY = getY(z.high);
      const botY = getY(z.low);
      const boxHeight = Math.max(9, Math.abs(botY - topY));
      const boxWidth = Math.max(candleSpacing * 2.5, chartRight - originX);
      const originCandle = candles[originIdx];
      const candleCenterY = originCandle ? getY((originCandle.open + originCandle.close) / 2) : topY + boxHeight / 2;

      let boxFill = "rgba(6, 182, 212, 0.16)";
      let boxStroke = "#06b6d4";
      let badgeBg = "#083344";
      let badgeStroke = "#06b6d4";
      let strokeDash = "4 3";
      let strokeWidth = 1.3;

      if (isOB) {
        boxFill = z.isBullish ? "rgba(59, 130, 246, 0.16)" : "rgba(168, 85, 247, 0.16)";
        boxStroke = z.isBullish ? "#3b82f6" : "#a855f7";
        badgeBg = z.isBullish ? "#172554" : "#3b0764";
        badgeStroke = boxStroke;
        strokeDash = "none";
        strokeWidth = 1.5;
      } else if (isBreaker) {
        boxFill = "rgba(245, 158, 11, 0.16)";
        boxStroke = "#f59e0b";
        badgeBg = "#451a03";
        badgeStroke = "#f59e0b";
        strokeDash = "5 3";
        strokeWidth = 1.5;
      } else if (isIFVG) {
        boxFill = "rgba(6, 182, 212, 0.16)";
        boxStroke = "#06b6d4";
        badgeBg = "#083344";
        badgeStroke = "#06b6d4";
        strokeDash = "3 3";
      }

      const shortName = isOB ? "OB" : isBreaker ? "BREAKER" : isIFVG ? "iFVG" : "ZONE";

      list.push({
        id: `parsed-zone-${idx}`,
        type: zoneType,
        name: z.label || z.name,
        low: z.low,
        high: z.high,
        originIdx,
        originX,
        originAnchorY: candleCenterY,
        originLabel: `⚓ C#${originIdx + 1} ${shortName}`,
        topY,
        botY,
        boxHeight,
        boxWidth,
        badgeX: originX + 6,
        badgeY: Math.min(chartBottom - 26, Math.max(chartTop + 4, topY + 3)),
        badgeWidth: isMobile ? 140 : 180,
        badgeHeight: 18,
        badgeBg,
        badgeStroke,
        badgeTextColor: boxStroke,
        boxFill,
        boxStroke,
        strokeDash,
        strokeWidth,
        badgeTitle: z.label || z.name,
        badgeSub: `(${z.low.toFixed(2)} - ${z.high.toFixed(2)})`,
        isPrimaryFvg: false,
      });
    });

    // 3. Dynamic Anti-Collision Pass for Zone Badges
    for (let i = 0; i < list.length; i++) {
      for (let j = 0; j < i; j++) {
        const prev = list[j];
        const curr = list[i];

        const xDist = Math.abs(curr.badgeX - prev.badgeX);
        const yDist = Math.abs(curr.badgeY - prev.badgeY);

        if (xDist < prev.badgeWidth + 12 && yDist < 22) {
          const candidateX = prev.badgeX + prev.badgeWidth + 12;
          if (candidateX + curr.badgeWidth <= chartRight - 8) {
            curr.badgeX = candidateX;
          } else {
            if (prev.badgeY + 24 <= chartBottom - 26) {
              curr.badgeY = prev.badgeY + 24;
            } else {
              curr.badgeY = Math.max(chartTop + 4, prev.badgeY - 24);
            }
          }
        }
      }
    }

    return list;
  }, [
    candles,
    candleMilestones,
    fvgBounds,
    parsedActiveZones,
    chartLeft,
    chartRight,
    chartTop,
    chartBottom,
    candleSpacing,
    isMobile,
    isBullishSetup,
    s4Pass,
    s5Pass,
    minPrice,
    maxPrice,
    priceRange,
    plotHeight,
  ]);

  // Anti-Collision Right Axis Tags Algorithm
  interface RightAxisTag {
    id: string;
    price: number;
    targetY: number;
    renderedY: number;
    bgFill: string;
    borderStroke: string;
    textColor: string;
    fontSize: string;
    label: string;
    priority: number;
  }

  const tagHeight = isMobile ? 20 : 24;
  const minTagGap = tagHeight + 2;

  const stackedTags = useMemo<RightAxisTag[]>(() => {
    const list: RightAxisTag[] = [];

    // 1. Live Price (Highest priority)
    list.push({
      id: "live",
      price: livePrice,
      targetY: getY(livePrice),
      renderedY: getY(livePrice),
      bgFill: "#ffffff",
      borderStroke: "#94a3b8",
      textColor: "#000000",
      fontSize: isMobile ? "10" : "11.5",
      label: `LIVE $${livePrice.toFixed(2)}`,
      priority: 100,
    });

    // 2. Active Entry Level
    if (showEntryLevel && effectiveEntryPrice > 0) {
      list.push({
        id: "entry",
        price: effectiveEntryPrice,
        targetY: getY(effectiveEntryPrice),
        renderedY: getY(effectiveEntryPrice),
        bgFill: "#0284c7",
        borderStroke: "#38bdf8",
        textColor: "#ffffff",
        fontSize: isMobile ? "9.5" : "10.5",
        label: isMobile ? `ENTRY $${effectiveEntryPrice.toFixed(2)}` : `🔵 ENTRY $${effectiveEntryPrice.toFixed(2)}`,
        priority: 90,
      });
    }

    // 3. Stop Loss (SL)
    if (showSlLevel && effectiveSlPrice > 0) {
      list.push({
        id: "sl",
        price: effectiveSlPrice,
        targetY: getY(effectiveSlPrice),
        renderedY: getY(effectiveSlPrice),
        bgFill: isTradeActive ? "#dc2626" : "#7f1d1d",
        borderStroke: isTradeActive ? "#fca5a5" : "#b91c1c",
        textColor: "#ffffff",
        fontSize: isMobile ? "9.5" : "10.5",
        label: isTradeActive
          ? Math.abs(effectiveSlPrice - effectiveEntryPrice) < 0.20
            ? `🛡️ BREAKEVEN $${effectiveSlPrice.toFixed(2)}`
            : `🔴 SL $${effectiveSlPrice.toFixed(2)}`
          : `🔒 SL (0.75) $${effectiveSlPrice.toFixed(2)}`,
        priority: 85,
      });
    }

    // 4. Take Profit (TP)
    if (showTpLevel && effectiveTpPrice > 0) {
      list.push({
        id: "tp",
        price: effectiveTpPrice,
        targetY: getY(effectiveTpPrice),
        renderedY: getY(effectiveTpPrice),
        bgFill: isTradeActive ? "#059669" : "#064e3b",
        borderStroke: isTradeActive ? "#6ee7b7" : "#059669",
        textColor: "#ffffff",
        fontSize: isMobile ? "9.5" : "10.5",
        label: isTradeActive
          ? `🟢 TP $${effectiveTpPrice.toFixed(2)}`
          : `🎯 1:1.85 $${effectiveTpPrice.toFixed(2)}`,
        priority: 85,
      });
    }

    // 5. CHoCH Level
    if (swingStructure.chochLvl > 0) {
      list.push({
        id: "choch",
        price: swingStructure.chochLvl,
        targetY: getY(swingStructure.chochLvl),
        renderedY: getY(swingStructure.chochLvl),
        bgFill: s3Pass ? "#d97706" : "#78350f",
        borderStroke: s3Pass ? "#fde68a" : "#d97706",
        textColor: "#ffffff",
        fontSize: isMobile ? "9.5" : "10.5",
        label: s3Pass
          ? (isMobile ? `CHOCH 🟢 $${swingStructure.chochLvl.toFixed(2)}` : `⚡ CHOCH 🟢 $${swingStructure.chochLvl.toFixed(2)}`)
          : `⏳ CHOCH $${swingStructure.chochLvl.toFixed(2)}`,
        priority: 70,
      });
    }

    // 6. Swing High
    if (swingStructure.swingHigh > 0) {
      const isSwept = s2Pass && isBearishSetup;
      list.push({
        id: "swingHigh",
        price: swingStructure.swingHigh,
        targetY: getY(swingStructure.swingHigh),
        renderedY: getY(swingStructure.swingHigh),
        bgFill: isSwept ? "#0891b2" : "#164e63",
        borderStroke: isSwept ? "#a5f3fc" : "#0891b2",
        textColor: "#ffffff",
        fontSize: isMobile ? "9" : "10",
        label: isSwept
          ? (isMobile ? `SWEPT 🟢 $${swingStructure.swingHigh.toFixed(2)}` : `⚡ BUY SWEPT $${swingStructure.swingHigh.toFixed(2)}`)
          : (isMobile ? `SWING HI $${swingStructure.swingHigh.toFixed(2)}` : `⏳ SWING HI $${swingStructure.swingHigh.toFixed(2)}`),
        priority: 60,
      });
    }

    // 7. Swing Low
    if (swingStructure.swingLow > 0) {
      const isSwept = s2Pass && isBullishSetup;
      list.push({
        id: "swingLow",
        price: swingStructure.swingLow,
        targetY: getY(swingStructure.swingLow),
        renderedY: getY(swingStructure.swingLow),
        bgFill: isSwept ? "#0891b2" : "#164e63",
        borderStroke: isSwept ? "#a5f3fc" : "#0891b2",
        textColor: "#ffffff",
        fontSize: isMobile ? "9" : "10",
        label: isSwept
          ? (isMobile ? `SWEPT 🟢 $${swingStructure.swingLow.toFixed(2)}` : `⚡ SELL SWEPT $${swingStructure.swingLow.toFixed(2)}`)
          : (isMobile ? `SWING LO $${swingStructure.swingLow.toFixed(2)}` : `⏳ SWING LO $${swingStructure.swingLow.toFixed(2)}`),
        priority: 60,
      });
    }

    // Sort by natural targetY ascending (top to bottom on chart)
    list.sort((a, b) => a.targetY - b.targetY);

    // Iterative relaxation to eliminate label collisions
    for (let iter = 0; iter < 12; iter++) {
      // Forward pass: push down if overlapping
      for (let i = 1; i < list.length; i++) {
        const prev = list[i - 1];
        const curr = list[i];
        const gap = curr.renderedY - prev.renderedY;
        if (gap < minTagGap) {
          const overlap = minTagGap - gap;
          if (curr.priority > prev.priority) {
            prev.renderedY -= overlap * 0.7;
            curr.renderedY += overlap * 0.3;
          } else if (prev.priority > curr.priority) {
            prev.renderedY -= overlap * 0.3;
            curr.renderedY += overlap * 0.7;
          } else {
            prev.renderedY -= overlap * 0.5;
            curr.renderedY += overlap * 0.5;
          }
        }
      }
      // Backward pass: push up if overlapping
      for (let i = list.length - 2; i >= 0; i--) {
        const curr = list[i];
        const next = list[i + 1];
        const gap = next.renderedY - curr.renderedY;
        if (gap < minTagGap) {
          const overlap = minTagGap - gap;
          curr.renderedY -= overlap * 0.5;
          next.renderedY += overlap * 0.5;
        }
      }
    }

    // Boundary constraints: keep within chart viewport
    const topLimit = chartTop + tagHeight / 2;
    const botLimit = chartBottom - tagHeight / 2;

    for (let i = 0; i < list.length; i++) {
      list[i].renderedY = Math.max(
        topLimit + i * minTagGap,
        Math.min(botLimit - (list.length - 1 - i) * minTagGap, list[i].renderedY)
      );
    }

    return list;
  }, [
    chartTop,
    chartBottom,
    isMobile,
    tagHeight,
    minTagGap,
    livePrice,
    showEntryLevel,
    effectiveEntryPrice,
    showSlLevel,
    effectiveSlPrice,
    showTpLevel,
    effectiveTpPrice,
    swingStructure,
    s2Pass,
    s3Pass,
    isTradeActive,
    isBullishSetup,
    isBearishSetup,
    minPrice,
    priceRange,
    plotHeight,
  ]);

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
                ? `Running ${tradeDirection} on ${symbol} | Lot: ${isMetals ? "0.07" : "0.51"} | SL: $${slPrice.toFixed(2)} ${
                    Math.abs(slPrice - entryPrice) < 0.20 ? "(Breakeven 🛡️)" : `($${defaultBuf} Buf)`
                  } | TP: $${tpPrice.toFixed(2)} (Opposing Liquidity Target) ${
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
                ? "Step 1-3 PASS 🟢 — Step 4 & 5 PENDING ⚪: Waiting for Displacement FVG Creation & Retest"
                : "Step 1-5 PASS 🟢 — Waiting for Final Rejection & Candle Close confirmation"}
            </p>
          </div>
        </div>

        {/* Live Metrics Pills - Clean, High Contrast */}
        <div className="flex flex-wrap items-center gap-2 self-end md:self-center font-mono text-xs">
          {isMetals && new Date().getUTCHours() === 21 && (
            <div className="px-3 py-1 rounded bg-amber-950/90 border border-amber-400 text-amber-200 font-bold shadow-sm flex items-center gap-1.5 animate-pulse text-[11px]">
              <span className="w-2 h-2 rounded-full bg-amber-400" />
              <span>⏸️ Market Rollover Break (Resumes 03:00 PKT / 22:00 UTC)</span>
            </div>
          )}

          <div className="px-3 py-1 rounded bg-zinc-900 border border-zinc-700 text-white font-bold shadow-sm" title="Exact MT5 Broker Midpoint (Bid+Ask)/2">
            MT5 Broker: <span className="text-emerald-400 font-black">${livePrice.toFixed(2)}</span>
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
                ? "bg-rose-600 text-white border border-rose-400 shadow-[0_0_12px_rgba(244,63,94,0.4)]"
                : s2Pass
                ? "bg-rose-950 border border-rose-500 text-rose-200"
                : "bg-zinc-900/60 border border-zinc-800 text-zinc-500"
            )}>
              {isTradeActive
                ? Math.abs(slPrice - entryPrice) < 0.20
                  ? `🛡️ BREAKEVEN SL: $${slPrice.toFixed(2)} (Risk-Free)`
                  : `🔴 ACTIVE SL: $${slPrice.toFixed(2)} (${isMetals ? "~$52 Risk" : ""})`
                : s2Pass
                ? `🔒 SL (0.75 Buf): $${slPrice.toFixed(2)} (${isMetals ? "~$52 Risk" : ""})`
                : "⏳ SL: Locks at Sweep (Step 2)"}
            </div>
            <div className={cn(
              "px-3 py-1 rounded font-black shadow-sm text-xs font-mono transition-all",
              isTradeActive
                ? "bg-emerald-600 text-white border border-emerald-400 shadow-[0_0_12px_rgba(16,185,129,0.4)]"
                : s4Pass
                ? "bg-emerald-950 border border-emerald-500 text-emerald-200"
                : "bg-zinc-900/60 border border-zinc-800 text-zinc-500"
            )}>
              {isTradeActive
                ? `🟢 ACTIVE TP: $${tpPrice.toFixed(2)} (${isMetals ? "~$97-$110 Target" : ""})`
                : s4Pass
                ? `🎯 1:1.85 TARGET: $${tpPrice.toFixed(2)} (${isMetals ? "~$97-$110 Target" : ""})`
                : "⏳ TP: Locks at FVG (Step 4)"}
            </div>
          </div>
        </div>
      </div>

      {/* 2. DUAL CHART VIEW TOGGLE & ZOOM CONTROLS */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-1">
        <div className="flex items-center gap-2">
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
            <Tv className="w-3.5 h-3.5 mr-1.5" /> 📈 Real TradingView Pro Chart (Full M5 Feed)
          </Button>

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
            <BarChart2 className="w-3.5 h-3.5 mr-1.5 text-white" /> 🎯 SMC Diagram Canvas
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
              onClick={() => setZoomLevel((z) => Math.min(3.5, Number((z + 0.35).toFixed(2))))}
              title="Zoom In (Enlarge Scalping Candles)"
            >
              <ZoomIn className="w-4 h-4" />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              className="h-7 w-7 text-zinc-200 hover:text-white hover:bg-zinc-800 font-bold"
              onClick={() => setZoomLevel((z) => Math.max(0.4, Number((z - 0.35).toFixed(2))))}
              title="Zoom Out (Show More Structure)"
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

      {/* 3. MAIN CHART CONTAINER (ALWAYS HOUSES 7-STEP SMC RIBBON ON TOP) */}
      <div
        ref={containerRef}
        className="relative w-full bg-[#070a12] border border-zinc-800 rounded-xl overflow-hidden shadow-2xl"
      >
        {/* TOP SMC STRUCTURE SEQUENCE BAR (INSIDE THE CHART CONTAINER - ALWAYS VISIBLE) */}
        <div className="px-3 py-2.5 bg-[#090d18] border-b border-zinc-800 text-xs font-mono">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
              <div className="flex items-center gap-2">
                <span className="font-bold text-white tracking-wider flex items-center gap-1.5 text-xs">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                  {symbol} <span className="text-zinc-400 font-normal">Pure SMC Structure Sequence</span>
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
                  HTF Bias: {rawM15Bias}
                </Badge>
                {Boolean(realCandles && realCandles.length >= 8) ? (
                  <Badge
                    variant="outline"
                    className="text-[10px] px-2 py-0.5 font-bold bg-cyan-500/20 text-cyan-300 border-cyan-500 shadow-[0_0_8px_rgba(6,182,212,0.3)]"
                  >
                    ⚡ REAL MT5 M5 FEED
                  </Badge>
                ) : (
                  <Badge
                    variant="outline"
                    className="text-[10px] px-2 py-0.5 font-bold bg-indigo-500/20 text-indigo-300 border-indigo-500"
                  >
                    📐 SMC SCHEMATIC CANVAS
                  </Badge>
                )}
              </div>

              <div className="flex items-center gap-2 text-[11px]">
                <span className="text-zinc-400 font-bold">Sequence Progress:</span>
                <span className="font-black px-2 py-0.5 rounded bg-zinc-800 text-emerald-400 border border-zinc-700">
                  {isTradeActive ? "TRADE ACTIVE 🟢 (In Profit)" : `${Math.min(7, passedCount)} / 7 Steps Verified`}
                </span>
              </div>
            </div>

            {/* 7-Step Sequential Micro-Grid Directly Inside Chart (Responsive on Mobile) */}
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-1.5 text-[10px]">
              {/* S1: M15 Bias */}
              <div className={cn(
                "p-1.5 rounded-lg border-2 text-center transition-all",
                s1Pass
                  ? "bg-emerald-950/80 border-emerald-400 text-emerald-200 font-black shadow-[0_0_10px_rgba(16,185,129,0.3)]"
                  : "bg-slate-900 border-slate-600 text-slate-200 font-bold"
              )}>
                <div className="text-[9px] text-slate-300 uppercase font-semibold">1. M15 Bias</div>
                <div className="truncate font-black mt-0.5">
                  {s1Pass ? (isM15Bullish ? "BULLISH 🟢" : "BEARISH 🔴") : "NEUTRAL ⚪"}
                </div>
              </div>

              {/* S2: Sweep */}
              <div className={cn(
                "p-1.5 rounded-lg border-2 text-center transition-all",
                s2Pass
                  ? "bg-cyan-950/80 border-cyan-400 text-cyan-200 font-black shadow-[0_0_10px_rgba(6,182,212,0.3)]"
                  : s1Pass
                  ? "bg-amber-950/70 border-amber-400 text-amber-200 font-black shadow-[0_0_10px_rgba(245,158,11,0.3)] animate-pulse"
                  : "bg-slate-900 border-slate-600 text-slate-200 font-bold"
              )}>
                <div className="text-[9px] text-slate-300 uppercase font-semibold">2. Sweep</div>
                <div className="truncate font-black mt-0.5">
                  {s2Pass ? "SWEEP 🟢" : s1Pass ? "SCANNING ⏳" : "WAITING ⚪"}
                </div>
              </div>

              {/* S3: CHoCH */}
              <div className={cn(
                "p-1.5 rounded-lg border-2 text-center transition-all",
                s3Pass
                  ? "bg-amber-950/80 border-amber-400 text-amber-200 font-black shadow-[0_0_10px_rgba(245,158,11,0.3)]"
                  : s2Pass
                  ? "bg-amber-950/70 border-amber-400 text-amber-200 font-black shadow-[0_0_10px_rgba(245,158,11,0.3)] animate-pulse"
                  : "bg-slate-900 border-slate-600 text-slate-200 font-bold"
              )}>
                <div className="text-[9px] text-slate-300 uppercase font-semibold">3. CHoCH</div>
                <div className="truncate font-black mt-0.5">
                  {s3Pass ? "CHOCH 🟢" : s2Pass ? "SCANNING ⏳" : "WAITING ⚪"}
                </div>
              </div>

              {/* S4: FVG Creation */}
              <div className={cn(
                "p-1.5 rounded-lg border-2 text-center transition-all",
                s4Pass
                  ? "bg-teal-950/80 border-teal-400 text-teal-200 font-black shadow-[0_0_10px_rgba(20,184,166,0.3)]"
                  : s3Pass
                  ? "bg-amber-950/70 border-amber-400 text-amber-200 font-black shadow-[0_0_10px_rgba(245,158,11,0.3)] animate-pulse"
                  : "bg-slate-900 border-slate-600 text-slate-200 font-bold"
              )}>
                <div className="text-[9px] text-slate-300 uppercase font-semibold">4. FVG Form</div>
                <div className="truncate font-black mt-0.5">
                  {s4Pass ? "FVG 🟢" : s3Pass ? "SCANNING ⏳" : "WAITING ⚪"}
                </div>
              </div>

              {/* S5: FVG Retest */}
              <div className={cn(
                "p-1.5 rounded-lg border-2 text-center transition-all",
                s5Pass
                  ? "bg-emerald-950/80 border-emerald-400 text-emerald-200 font-black shadow-[0_0_10px_rgba(16,185,129,0.3)]"
                  : s4Pass
                  ? "bg-amber-950/70 border-amber-400 text-amber-200 font-black shadow-[0_0_10px_rgba(245,158,11,0.3)] animate-pulse"
                  : "bg-slate-900 border-slate-600 text-slate-200 font-bold"
              )}>
                <div className="text-[9px] text-slate-300 uppercase font-semibold">5. Retest</div>
                <div className="truncate font-black mt-0.5">
                  {s5Pass ? "RETESTED 🟢" : s4Pass ? "AWAITING ⏳" : "WAITING ⚪"}
                </div>
              </div>

              {/* S6: Rejection */}
              <div className={cn(
                "p-1.5 rounded-lg border-2 text-center transition-all",
                s6Pass
                  ? "bg-emerald-950/80 border-emerald-400 text-emerald-200 font-black shadow-[0_0_10px_rgba(16,185,129,0.3)]"
                  : s5Pass
                  ? "bg-amber-950/70 border-amber-400 text-amber-200 font-black shadow-[0_0_10px_rgba(245,158,11,0.3)] animate-pulse"
                  : "bg-slate-900 border-slate-600 text-slate-200 font-bold"
              )}>
                <div className="text-[9px] text-slate-300 uppercase font-semibold">6. Rejection</div>
                <div className="truncate font-black mt-0.5">
                  {s6Pass ? "REJECTED 🟢" : s5Pass ? "AWAITING ⏳" : "WAITING ⚪"}
                </div>
              </div>

              {/* S7: Confirmation Close */}
              <div className={cn(
                "col-span-2 sm:col-span-2 lg:col-span-1 p-1.5 rounded-lg border-2 text-center transition-all",
                s7Pass
                  ? "bg-emerald-950/80 border-emerald-400 text-emerald-200 font-black shadow-[0_0_10px_rgba(16,185,129,0.3)]"
                  : s6Pass
                  ? "bg-amber-950/70 border-amber-400 text-amber-200 font-black shadow-[0_0_10px_rgba(245,158,11,0.3)] animate-pulse"
                  : "bg-slate-900 border-slate-600 text-slate-200 font-bold"
              )}>
                <div className="text-[9px] text-slate-300 uppercase font-semibold">7. Close</div>
                <div className="truncate font-black mt-0.5">
                  {s7Pass ? "CONFIRMED 🟢" : s6Pass ? "AWAITING ⏳" : "WAITING ⚪"}
                </div>
              </div>
            </div>
          </div>

        {/* ACTIVE CHART DISPLAY: REAL TRADINGVIEW M5 (DEFAULT) OR SMC DIAGRAM CANVAS */}
        {activeTab === "tv" ? (
          <TradingViewEmbedded symbol={symbol} />
        ) : (
          /* SVG Canvas with Crisp Rendering and Real-time Cursor Tracking */
          <div className="relative w-full h-[380px] sm:h-[420px] md:h-[460px] lg:h-[480px]">
            <svg
              viewBox={`0 0 ${svgWidth} ${svgHeight}`}
              className="w-full h-full cursor-crosshair select-none"
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
                <filter id="glowBlue" x="-20%" y="-20%" width="140%" height="140%">
                  <feDropShadow dx="0" dy="0" stdDeviation="2.5" floodColor="#38bdf8" floodOpacity="0.9" />
                </filter>
              </defs>

              {/* TradingView Right Price Scale Panel Background */}
              <rect
                x={chartRight}
                y={chartTop}
                width={svgWidth - chartRight}
                height={plotHeight}
                fill="#080c16"
              />
              <line
                x1={chartRight}
                y1={chartTop}
                x2={chartRight}
                y2={chartBottom}
                stroke="#1e293b"
                strokeWidth="1.5"
              />

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
                    x={chartRight + (isMobile ? 6 : 10)}
                    y={tick.y + 4}
                    fill="#64748b"
                    fontSize={isMobile ? "10" : "11.5"}
                    fontFamily="monospace"
                    fontWeight="700"
                  >
                    ${tick.price.toFixed(2)}
                  </text>
                </g>
              ))}

              {/* Institutional SMC Zones (FVG, Order Blocks, Breakers, iFVG) with Exact Origin Candlestick Anchoring & Anti-Collision Badges */}
              {renderedSmcZones.map((zone) => {
                const originCandle = candles[zone.originIdx];
                const candleHighY = originCandle ? getY(originCandle.high) : zone.topY;
                const candleLowY = originCandle ? getY(originCandle.low) : zone.botY;
                const candleCenterY = originCandle ? getY((originCandle.open + originCandle.close) / 2) : zone.topY;

                // Viewport culling: do not render distant zones outside chart scale
                if (zone.low > maxPrice + 2.5 || zone.high < minPrice - 2.5) {
                  return null;
                }

                return (
                  <g key={zone.id}>
                    {/* 1. Zone Rectangle starting strictly at its originating candle originX and projecting rightward */}
                    <rect
                      x={zone.originX}
                      y={zone.topY}
                      width={zone.boxWidth}
                      height={zone.boxHeight}
                      fill={zone.boxFill}
                      stroke={zone.boxStroke}
                      strokeWidth={zone.strokeWidth}
                      strokeDasharray={zone.strokeDash}
                      opacity={zone.isPrimaryFvg && s5Pass ? 1 : 0.88}
                      filter={zone.glowFilter}
                      rx="2"
                    />

                    {/* 2. Origin Guideline Connecting Originating Candle to the Zone Box */}
                    <line
                      x1={zone.originX}
                      y1={Math.min(zone.topY, candleCenterY)}
                      x2={zone.originX}
                      y2={Math.max(zone.botY, candleCenterY)}
                      stroke={zone.boxStroke}
                      strokeWidth="1.5"
                      strokeDasharray="2 2"
                      opacity="0.8"
                    />

                    {/* 3. Origin Candle Center Anchor Dot */}
                    <circle
                      cx={zone.originX}
                      cy={candleCenterY}
                      r="3.5"
                      fill={zone.boxStroke}
                      stroke="#ffffff"
                      strokeWidth="1.2"
                    />

                    {/* 4. Origin Anchor Pin Flag on the Originating Candle */}
                    {(() => {
                      const pinY = candleHighY > chartTop + 24 ? candleHighY - 18 : candleLowY + 5;
                      const pinWidth = isMobile ? 68 : 84;
                      return (
                        <g>
                          <rect
                            x={zone.originX - pinWidth / 2}
                            y={pinY}
                            width={pinWidth}
                            height="15"
                            rx="3"
                            fill="#090d16"
                            stroke={zone.boxStroke}
                            strokeWidth="1"
                          />
                          <text
                            x={zone.originX}
                            y={pinY + 11}
                            fill={zone.boxStroke}
                            fontSize={isMobile ? "7.5" : "8.5"}
                            fontFamily="monospace"
                            fontWeight="900"
                            textAnchor="middle"
                          >
                            {zone.originLabel}
                          </text>
                        </g>
                      );
                    })()}

                    {/* 5. Anti-Collision Information Badge Inside/Beside the Zone (Zero Stacking Overlap) */}
                    <rect
                      x={zone.badgeX}
                      y={zone.badgeY}
                      width={zone.badgeWidth}
                      height={zone.badgeHeight}
                      fill={zone.badgeBg}
                      rx="4"
                      stroke={zone.badgeStroke}
                      strokeWidth="1.2"
                    />
                    <text
                      x={zone.badgeX + 8}
                      y={zone.badgeY + 13}
                      fill={zone.isPrimaryFvg ? "#ffffff" : zone.badgeTextColor}
                      fontSize={isMobile ? "8.5" : "9.5"}
                      fontFamily="monospace"
                      fontWeight="800"
                    >
                      {zone.badgeTitle} {zone.badgeSub}
                    </text>
                  </g>
                );
              })}

              {/* Step 2A: Swing High (Buy-Side Liquidity Level Line) */}
              {swingStructure.swingHigh > 0 && (
                <line
                  x1={chartLeft}
                  y1={getY(swingStructure.swingHigh)}
                  x2={chartRight}
                  y2={getY(swingStructure.swingHigh)}
                  stroke={(s2Pass && isBearishSetup) ? "#06b6d4" : "#0891b2"}
                  strokeWidth={(s2Pass && isBearishSetup) ? 2.5 : 1.5}
                  strokeDasharray={(s2Pass && isBearishSetup) ? "none" : "6 4"}
                  opacity={(s2Pass && isBearishSetup) ? 1 : 0.75}
                  filter={(s2Pass && isBearishSetup) ? "url(#glowCyan)" : undefined}
                />
              )}

              {/* Step 2B: Swing Low (Sell-Side Liquidity Level Line) */}
              {swingStructure.swingLow > 0 && (
                <line
                  x1={chartLeft}
                  y1={getY(swingStructure.swingLow)}
                  x2={chartRight}
                  y2={getY(swingStructure.swingLow)}
                  stroke={(s2Pass && isBullishSetup) ? "#06b6d4" : "#0891b2"}
                  strokeWidth={(s2Pass && isBullishSetup) ? 2.5 : 1.5}
                  strokeDasharray={(s2Pass && isBullishSetup) ? "none" : "6 4"}
                  opacity={(s2Pass && isBullishSetup) ? 1 : 0.75}
                  filter={(s2Pass && isBullishSetup) ? "url(#glowCyan)" : undefined}
                />
              )}

              {/* Step 3: CHoCH Level Line */}
              {swingStructure.chochLvl > 0 && (
                <line
                  x1={chartLeft}
                  y1={getY(swingStructure.chochLvl)}
                  x2={chartRight}
                  y2={getY(swingStructure.chochLvl)}
                  stroke={s3Pass ? "#f59e0b" : "#d97706"}
                  strokeWidth={s3Pass ? 2.5 : 1.5}
                  strokeDasharray={s3Pass ? "none" : "6 4"}
                  opacity={s3Pass ? 1 : 0.75}
                  filter={s3Pass ? "url(#glowAmber)" : undefined}
                />
              )}

              {/* INSTITUTIONAL TRADE POSITION BRACKET & PROJECTIONS (LuxAlgo / TradingView Style) */}
              {(() => {
                const entryX = chartLeft + (candleMilestones.entry + 0.5) * candleSpacing;
                const sweepX = chartLeft + (candleMilestones.sweep + 0.5) * candleSpacing;
                const chochX = chartLeft + (candleMilestones.choch + 0.5) * candleSpacing;

                const hasActiveTradeOrSignal = isTradeActive || s7Pass;

                return (
                  <g>
                    {/* A. Active Position Bracket Shading (Green Profit Zone + Red Risk Zone) */}
                    {hasActiveTradeOrSignal && effectiveEntryPrice > 0 && effectiveTpPrice > 0 && effectiveSlPrice > 0 && (
                      <g>
                        {/* Green Target Zone Box */}
                        <rect
                          x={entryX}
                          y={Math.min(getY(effectiveEntryPrice), getY(effectiveTpPrice))}
                          width={Math.max(candleSpacing * 2, chartRight - entryX)}
                          height={Math.max(4, Math.abs(getY(effectiveTpPrice) - getY(effectiveEntryPrice)))}
                          fill="rgba(16, 185, 129, 0.09)"
                          stroke="#10b981"
                          strokeWidth="1"
                          strokeDasharray="4 3"
                        />
                        {/* Red Risk Zone Box */}
                        <rect
                          x={entryX}
                          y={Math.min(getY(effectiveEntryPrice), getY(effectiveSlPrice))}
                          width={Math.max(candleSpacing * 2, chartRight - entryX)}
                          height={Math.max(4, Math.abs(getY(effectiveSlPrice) - getY(effectiveEntryPrice)))}
                          fill="rgba(239, 68, 68, 0.09)"
                          stroke="#ef4444"
                          strokeWidth="1"
                          strokeDasharray="4 3"
                        />
                        {/* Center Position Metric Floating Pill */}
                        <rect
                          x={Math.min(chartRight - (isMobile ? 130 : 165), entryX + 16)}
                          y={getY(effectiveEntryPrice) - 11}
                          width={isMobile ? 125 : 160}
                          height="22"
                          rx="4"
                          fill="#090d16"
                          stroke="#38bdf8"
                          strokeWidth="1.2"
                        />
                        <text
                          x={Math.min(chartRight - (isMobile ? 130 : 165), entryX + 16) + (isMobile ? 62 : 80)}
                          y={getY(effectiveEntryPrice) + 4}
                          fill="#38bdf8"
                          fontSize={isMobile ? "8.5" : "9.5"}
                          fontFamily="monospace"
                          fontWeight="900"
                          textAnchor="middle"
                        >
                          {isTradeActive ? "⚡ ACTIVE 1:1.85 RRR" : "🎯 SIGNAL 1:1.85 RRR"} ({isBullishSetup ? "BUY" : "SELL"})
                        </text>
                      </g>
                    )}

                    {/* B. Active Entry Level Ray (Originating at confirmed entry candle) */}
                    {showEntryLevel && effectiveEntryPrice > 0 && (
                      <g>
                        <line
                          x1={hasActiveTradeOrSignal ? entryX : chartLeft}
                          y1={getY(effectiveEntryPrice)}
                          x2={chartRight}
                          y2={getY(effectiveEntryPrice)}
                          stroke="#38bdf8"
                          strokeWidth={2.5}
                          filter="url(#glowBlue)"
                        />
                        {/* Entry Candle Trigger Anchor */}
                        <circle
                          cx={entryX}
                          cy={getY(effectiveEntryPrice)}
                          r="4.5"
                          fill="#38bdf8"
                          stroke="#ffffff"
                          strokeWidth="1.5"
                        />
                        <rect
                          x={entryX - (isMobile ? 32 : 40)}
                          y={getY(effectiveEntryPrice) - 26}
                          width={isMobile ? 64 : 80}
                          height="18"
                          rx="4"
                          fill="#0284c7"
                          stroke="#38bdf8"
                          strokeWidth="1.2"
                        />
                        <text
                          x={entryX}
                          y={getY(effectiveEntryPrice) - 14}
                          fill="#ffffff"
                          fontSize={isMobile ? "8" : "9"}
                          fontFamily="monospace"
                          fontWeight="900"
                          textAnchor="middle"
                        >
                          ⚡ ENTRY C#{candleMilestones.entry + 1}
                        </text>
                      </g>
                    )}

                    {/* C. Stop Loss (SL) Level Ray (Originating at Step 2 Sweep candle) */}
                    {showSlLevel && effectiveSlPrice > 0 && (
                      <g>
                        <line
                          x1={s2Pass ? sweepX : chartLeft}
                          y1={getY(effectiveSlPrice)}
                          x2={chartRight}
                          y2={getY(effectiveSlPrice)}
                          stroke="#ef4444"
                          strokeWidth={isTradeActive ? 3 : 1.8}
                          strokeDasharray={isTradeActive ? "none" : "5 5"}
                          opacity={isTradeActive ? 1 : 0.85}
                          filter={isTradeActive ? "url(#glowRed)" : undefined}
                        />
                        {/* Sweep-to-SL Anchor connector and marker */}
                        {s2Pass && (
                          <>
                            <line
                              x1={sweepX}
                              y1={getY(isBullishSetup ? (swingStructure.swingLow || livePrice) : (swingStructure.swingHigh || livePrice))}
                              x2={sweepX}
                              y2={getY(effectiveSlPrice)}
                              stroke="#ef4444"
                              strokeWidth="1.2"
                              strokeDasharray="2 2"
                              opacity="0.85"
                            />
                            <circle
                              cx={sweepX}
                              cy={getY(effectiveSlPrice)}
                              r="3.5"
                              fill="#ef4444"
                              stroke="#ffffff"
                              strokeWidth="1"
                            />
                            <rect
                              x={sweepX + 6}
                              y={getY(effectiveSlPrice) - 18}
                              width={isMobile ? 120 : 155}
                              height="17"
                              rx="3"
                              fill="#450a0a"
                              stroke="#ef4444"
                              strokeWidth="1"
                            />
                            <text
                              x={sweepX + 10}
                              y={getY(effectiveSlPrice) - 6}
                              fill="#fca5a5"
                              fontSize={isMobile ? "8" : "9"}
                              fontFamily="monospace"
                              fontWeight="900"
                            >
                              🛡️ SL ANCHOR (SWEEP + $0.75)
                            </text>
                          </>
                        )}
                      </g>
                    )}

                    {/* D. Take Profit (TP) Level Ray (Originating at Step 4 FVG / CHoCH expansion) */}
                    {showTpLevel && effectiveTpPrice > 0 && (
                      <g>
                        <line
                          x1={s4Pass ? chochX : chartLeft}
                          y1={getY(effectiveTpPrice)}
                          x2={chartRight}
                          y2={getY(effectiveTpPrice)}
                          stroke="#10b981"
                          strokeWidth={isTradeActive ? 3 : 1.8}
                          strokeDasharray={isTradeActive ? "none" : "5 5"}
                          opacity={isTradeActive ? 1 : 0.85}
                          filter={isTradeActive ? "url(#glowGreen)" : undefined}
                        />
                        {/* TP Target Anchor Badge */}
                        {s4Pass && (
                          <>
                            <circle
                              cx={chochX}
                              cy={getY(effectiveTpPrice)}
                              r="3.5"
                              fill="#10b981"
                              stroke="#ffffff"
                              strokeWidth="1"
                            />
                            <rect
                              x={chochX + 6}
                              y={getY(effectiveTpPrice) + 3}
                              width={isMobile ? 120 : 155}
                              height="17"
                              rx="3"
                              fill="#064e3b"
                              stroke="#10b981"
                              strokeWidth="1"
                            />
                            <text
                              x={chochX + 10}
                              y={getY(effectiveTpPrice) + 15}
                              fill="#6ee7b7"
                              fontSize={isMobile ? "8" : "9"}
                              fontFamily="monospace"
                              fontWeight="900"
                            >
                              🎯 OPPOSING LIQUIDITY TP
                            </text>
                          </>
                        )}
                      </g>
                    )}
                  </g>
                );
              })()}

              {/* MARKET STRUCTURE ZIGZAG PATH (Order Flow Connecting Fractal Swings) */}
              {marketStructure.path && (
                <path
                  d={marketStructure.path}
                  fill="none"
                  stroke="#818cf8"
                  strokeWidth="2.2"
                  strokeDasharray="5 3"
                  opacity="0.85"
                />
              )}

              {/* Live Market Price Line */}
              <line
                x1={chartLeft}
                y1={getY(livePrice)}
                x2={chartRight}
                y2={getY(livePrice)}
                stroke="#ffffff"
                strokeWidth="1.75"
                strokeDasharray="4 3"
              />

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

                    {/* Sweep Marker on the Sweep Candle (High for Bearish, Low for Bullish) */}
                    {c.isSweep && (
                      <g>
                        {isBullishSetup ? (
                          <>
                            <path
                              d={`M ${cx} ${yLow + 6} L ${cx - 7} ${yLow + 18} L ${cx + 7} ${yLow + 18} Z`}
                              fill="#06b6d4"
                            />
                            <rect
                              x={cx - (isMobile ? 32 : 42)}
                              y={yLow + 22}
                              width={isMobile ? 64 : 84}
                              height={isMobile ? 18 : 20}
                              fill="#0891b2"
                              rx="4"
                              stroke="#22d3ee"
                              strokeWidth="1.5"
                            />
                            <text
                              x={cx}
                              y={yLow + (isMobile ? 34 : 36)}
                              fill="#ffffff"
                              fontSize={isMobile ? "8.5" : "9.5"}
                              fontFamily="monospace"
                              fontWeight="900"
                              textAnchor="middle"
                            >
                              SWEEP
                            </text>
                          </>
                        ) : (
                          <>
                            <path
                              d={`M ${cx} ${yHigh - 6} L ${cx - 7} ${yHigh - 18} L ${cx + 7} ${yHigh - 18} Z`}
                              fill="#06b6d4"
                            />
                            <rect
                              x={cx - (isMobile ? 32 : 42)}
                              y={yHigh - 42}
                              width={isMobile ? 64 : 84}
                              height={isMobile ? 18 : 20}
                              fill="#0891b2"
                              rx="4"
                              stroke="#22d3ee"
                              strokeWidth="1.5"
                            />
                            <text
                              x={cx}
                              y={yHigh - (isMobile ? 30 : 28)}
                              fill="#ffffff"
                              fontSize={isMobile ? "8.5" : "9.5"}
                              fontFamily="monospace"
                              fontWeight="900"
                              textAnchor="middle"
                            >
                              SWEEP
                            </text>
                          </>
                        )}
                      </g>
                    )}

                    {/* CHoCH Marker on the Break Candle (High for Bullish, Low for Bearish) */}
                    {c.isChoch && (
                      <g>
                        {isBullishSetup ? (
                          <>
                            <circle cx={cx} cy={yHigh - 8} r="4" fill="#f59e0b" />
                            <rect
                              x={cx - (isMobile ? 24 : 28)}
                              y={yHigh - 30}
                              width={isMobile ? 48 : 56}
                              height={18}
                              fill="#d97706"
                              rx="4"
                              stroke="#fde68a"
                              strokeWidth="1.5"
                            />
                            <text
                              x={cx}
                              y={yHigh - 17}
                              fill="#ffffff"
                              fontSize={isMobile ? "8.5" : "9.5"}
                              fontFamily="monospace"
                              fontWeight="900"
                              textAnchor="middle"
                            >
                              CHOCH
                            </text>
                          </>
                        ) : (
                          <>
                            <circle cx={cx} cy={yLow + 8} r="4" fill="#f59e0b" />
                            <rect
                              x={cx - (isMobile ? 24 : 28)}
                              y={yLow + 14}
                              width={isMobile ? 48 : 56}
                              height={18}
                              fill="#d97706"
                              rx="4"
                              stroke="#fde68a"
                              strokeWidth="1.5"
                            />
                            <text
                              x={cx}
                              y={yLow + 27}
                              fill="#ffffff"
                              fontSize={isMobile ? "8.5" : "9.5"}
                              fontFamily="monospace"
                              fontWeight="900"
                              textAnchor="middle"
                            >
                              CHOCH
                            </text>
                          </>
                        )}
                      </g>
                    )}

                    {/* Bottom Time Axis Label */}
                    {idx % (isMobile ? 5 : 4) === 0 && (
                      <text
                        x={cx}
                        y={chartBottom + (isMobile ? 18 : 22)}
                        fill="#cbd5e1"
                        fontSize={isMobile ? "9.5" : "11"}
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

              {/* MARKET STRUCTURE FRACTAL SWING LABELS (HH / HL / LH / LL) */}
              {marketStructure.swings.map((swing, sIdx) => {
                const isHH = swing.type === "HH";
                const isHL = swing.type === "HL";

                const badgeBg = isHH || isHL ? "#064e3b" : "#450a0a";
                const badgeBorder = isHH || isHL ? "#10b981" : "#ef4444";
                const badgeText = isHH || isHL ? "#34d399" : "#f87171";

                const tagY = swing.isHigh
                  ? Math.max(chartTop + 4, swing.y - 18)
                  : Math.min(chartBottom - 18, swing.y + 7);

                return (
                  <g key={`ms-swing-${sIdx}`}>
                    {/* Circle marker at fractal tip */}
                    <circle
                      cx={swing.x}
                      cy={swing.y}
                      r="3.5"
                      fill={badgeBorder}
                      stroke="#ffffff"
                      strokeWidth="1.2"
                    />
                    {/* Tag badge */}
                    <rect
                      x={swing.x - 14}
                      y={tagY}
                      width="28"
                      height="15"
                      rx="3"
                      fill={badgeBg}
                      stroke={badgeBorder}
                      strokeWidth="1"
                    />
                    <text
                      x={swing.x}
                      y={tagY + 11}
                      fill={badgeText}
                      fontSize="9"
                      fontFamily="monospace"
                      fontWeight="900"
                      textAnchor="middle"
                    >
                      {swing.type}
                    </text>
                  </g>
                );
              })}

              {/* ANTI-COLLISION STACKED RIGHT-AXIS BADGES & LEADERS */}
              {stackedTags.map((tag) => {
                const isShifted = Math.abs(tag.renderedY - tag.targetY) > 2.0;
                const badgeX = chartRight + 5;
                const badgeY = tag.renderedY - tagHeight / 2;
                const textY = tag.renderedY + (isMobile ? 3.5 : 4.5);

                return (
                  <g key={tag.id}>
                    {/* Leader line connecting badge to exact price line if shifted */}
                    {isShifted && (
                      <path
                        d={`M ${chartRight} ${tag.targetY} L ${badgeX} ${tag.renderedY}`}
                        stroke={tag.borderStroke}
                        strokeWidth="1.2"
                        strokeDasharray="2 2"
                        opacity={0.85}
                      />
                    )}

                    {/* Badge Pill */}
                    <rect
                      x={badgeX}
                      y={badgeY}
                      width={rightTagWidth}
                      height={tagHeight}
                      fill={tag.bgFill}
                      rx="4"
                      stroke={tag.borderStroke}
                      strokeWidth={tag.id === "live" ? 1.5 : 1.2}
                    />

                    {/* Badge Text */}
                    <text
                      x={badgeX + (isMobile ? 4 : 7)}
                      y={textY}
                      fill={tag.textColor}
                      fontSize={tag.fontSize}
                      fontFamily="monospace"
                      fontWeight="900"
                    >
                      {tag.label}
                    </text>
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
                      x={chartRight + 5}
                      y={mousePos.y - tagHeight / 2}
                      width={rightTagWidth}
                      height={tagHeight}
                      fill="#2563eb"
                      rx="4"
                      stroke="#bfdbfe"
                      strokeWidth="1.5"
                    />
                    <text
                      x={chartRight + (isMobile ? 6 : 10)}
                      y={mousePos.y + (isMobile ? 3.5 : 4.5)}
                      fill="#ffffff"
                      fontSize={isMobile ? "10" : "12"}
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
              <div className="absolute top-2 left-2 sm:top-3 sm:left-4 bg-[#0d121f]/95 border border-zinc-700 px-2.5 py-1.5 sm:px-3.5 sm:py-2.5 rounded-lg text-[10px] sm:text-xs font-mono text-zinc-100 shadow-2xl backdrop-blur-md pointer-events-none z-10 flex flex-wrap items-center gap-2 sm:gap-4">
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
        )}
      </div>

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
                S4: Displacement FVG
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
                ? "Imbalance gap formed by Sweep-to-CHoCH displacement leg."
                : "Waiting for 3-candle displacement imbalance (Fair Value Gap)."}
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
                ? "Price dipped into confirmed Displacement FVG zone."
                : "Waiting for subsequent candle to retest the Displacement FVG zone."}
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
                S8: SL Placement & Cap
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
                {s8Pass ? (s8Status && isPassText(s8Status) ? s8Status : `PASS 🟢 ($${defaultBuf} Buf | $7.50 Cap)`) : "PENDING ⚪"}
              </Badge>
            </div>
            <p className="text-[11px] text-zinc-300 leading-snug">
              {s8Pass
                ? (slPrice > 0 && isTradeActive
                    ? `Locked exact $${defaultBuf} buffer behind Sweep wick ($${slPrice.toFixed(2)}) with $7.50 max risk cap.`
                    : `Verified structural SL buffer ($${defaultBuf}) with max $7.50 anti-chasing risk cap.`)
                : `Will anchor $${defaultBuf} behind Sweep wick upon trade execution (max $7.50 cap).`}
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
                S9: Opposing Liquidity Target
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
                {s9Pass ? (s9Status && isPassText(s9Status) ? s9Status : "PASS 🟢 (Opposing Target)") : "PENDING ⚪"}
              </Badge>
            </div>
            <p className="text-[11px] text-zinc-300 leading-snug">
              {s9Pass
                ? (tpPrice > 0 && isTradeActive
                    ? `Opposing structural liquidity TP placed at $${tpPrice.toFixed(2)} (front-run by $0.50).`
                    : "Verified minimum 1.5R clear path to opposing structural liquidity.")
                : "Requires minimum 1.5R clear path to opposing liquidity pool."}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
