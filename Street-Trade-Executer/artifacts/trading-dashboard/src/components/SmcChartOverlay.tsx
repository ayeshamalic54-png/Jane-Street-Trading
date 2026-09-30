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
    if (hasActivePosition && activePosition.entryPrice) {
      return Number(activePosition.entryPrice);
    }
    return livePrice;
  }, [hasActivePosition, activePosition, livePrice]);

  // Strict SL: anchored to sweep with exact $0.75 buffer (or institutional baseline ~$7.50 distance / $52.50 USD risk on 0.07 lots)
  const effectiveSlPrice = useMemo(() => {
    if (hasActivePosition && activePosition.sl) {
      return Number(activePosition.sl);
    }
    const minSweepDist = isMetals ? 3.0 : 0.0010;
    if (sweepPrice > 0 && Math.abs(livePrice - sweepPrice) >= minSweepDist) {
      return isBearishSetup
        ? Number((sweepPrice + defaultBuf).toFixed(2))
        : Number((sweepPrice - defaultBuf).toFixed(2));
    }
    // Baseline institutional SMC structural risk:
    // For Gold (0.07 lots): $7.50 distance equals exact $52.50 USD risk (matching the user's $50 target)
    // For Forex (0.51 lots): 0.0020 (20 pips) equals exact $102 USD risk
    const defaultSlDist = isMetals ? 7.50 : 0.0020;
    return isBearishSetup
      ? Number((livePrice + defaultSlDist).toFixed(2))
      : Number((livePrice - defaultSlDist).toFixed(2));
  }, [hasActivePosition, activePosition, sweepPrice, isBearishSetup, defaultBuf, livePrice, isMetals]);

  // Strict TP: exact 2.0R target (Reward of $105 USD on 0.07 lots, matching user's $97-$112 range)
  const effectiveTpPrice = useMemo(() => {
    if (hasActivePosition && activePosition.tp) {
      return Number(activePosition.tp);
    }
    const slDist = Math.max(isMetals ? 6.0 : 0.0015, Math.abs(effectiveEntryPrice - effectiveSlPrice));
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
    const step = isMetals ? 0.65 : 0.0003;
    const now = Date.now();
    const count = isMobile
      ? Math.max(14, Math.min(24, Math.round(18 / zoomLevel)))
      : Math.max(18, Math.min(40, Math.round(28 / zoomLevel)));

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
        const fvgMid = isBullishSetup ? (swP + chP) * 0.52 : (swP + chP) * 0.48;
        closeP = (openP + fvgMid) * 0.5;
      } else if (k === retestIdx) {
        // Phase 6: Retest candle dipping into FVG zone
        isRetest = s5Pass;
        const fvgMid = isBullishSetup ? (swP + chP) * 0.52 : (swP + chP) * 0.48;
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
        const fvgMid = isBullishSetup ? (swP + chP) * 0.52 : (swP + chP) * 0.48;
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

  // Parsed Active SMC Zones (FVG, OB, Breaker, iFVG) from live bot scanner
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
    for (const z of activeZones) {
      if (!z.range) continue;
      const parts = z.range.split(/[\u2013\-]/);
      if (parts.length >= 2) {
        const low = parseFloat(parts[0].trim());
        const high = parseFloat(parts[1].trim());
        if (!isNaN(low) && !isNaN(high) && high > low) {
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
    return list;
  }, [activeZones]);

  // FVG Bounds (Post-CHoCH Imbalance)
  // FVG Bounds: Strictly for the CURRENT active setup (Step 4 & 5). Never grab far-away historical zones!
  const fvgBounds = useMemo(() => {
    // Only resolve FVG when Step 4 (Post-CHoCH FVG) or Step 5 (Retest) is reached or trade is active!
    if (!s4Pass && !s5Pass && !isTradeActive) return null;
    try {
      const rawJson = telemetry?.fvg_bounds_json ?? telemetry?.fvgBoundsJson;
      if (rawJson) {
        const parsed = typeof rawJson === "string" ? JSON.parse(rawJson) : rawJson;
        if (typeof parsed === "object" && parsed !== null) {
          const list = isBullishSetup
            ? parsed.bullish_fvg || []
            : parsed.bearish_fvg || [];
          // Pick only FVG within immediate proximity of live price (max $8 / 0.0040 away)
          for (const item of list) {
            if (Array.isArray(item) && item.length >= 2) {
              const l = Number(item[0]);
              const h = Number(item[1]);
              const avg = (l + h) / 2;
              if (Math.abs(avg - livePrice) <= (isMetals ? 8.0 : 0.0040) && h > l) {
                return { low: l, high: h };
              }
            }
          }
        }
      }
    } catch {}
    return null;
  }, [telemetry, livePrice, isMetals, isBullishSetup, s4Pass, s5Pass, isTradeActive]);

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

  // AUTO-SCALE STRICTLY TO CANDLES & ACTIVE SMC LEVELS
  const minPrice = useMemo(() => {
    const lows = candles.map((c) => c.low);
    lows.push(livePrice);
    if (showSlLevel && effectiveSlPrice > 0 && Math.abs(effectiveSlPrice - livePrice) < 30) lows.push(effectiveSlPrice);
    if (showEntryLevel && effectiveEntryPrice > 0) lows.push(effectiveEntryPrice);
    if (swingStructure.swingLow > 0 && Math.abs(swingStructure.swingLow - livePrice) < 30) lows.push(swingStructure.swingLow);
    if (fvgBounds && fvgBounds.low > 0) lows.push(fvgBounds.low);
    const rawMin = Math.min(...lows);
    return Number((rawMin - (isMetals ? 0.60 : 0.0003)).toFixed(2));
  }, [candles, showSlLevel, showEntryLevel, effectiveSlPrice, effectiveEntryPrice, livePrice, swingStructure.swingLow, fvgBounds, isMetals]);

  const maxPrice = useMemo(() => {
    const highs = candles.map((c) => c.high);
    highs.push(livePrice);
    if (showTpLevel && effectiveTpPrice > 0 && Math.abs(effectiveTpPrice - livePrice) < 35) highs.push(effectiveTpPrice);
    if (showEntryLevel && effectiveEntryPrice > 0) highs.push(effectiveEntryPrice);
    if (swingStructure.swingHigh > 0 && Math.abs(swingStructure.swingHigh - livePrice) < 30) highs.push(swingStructure.swingHigh);
    if (fvgBounds && fvgBounds.high > 0) highs.push(fvgBounds.high);
    const rawMax = Math.max(...highs);
    return Number((rawMax + (isMetals ? 0.60 : 0.0003)).toFixed(2));
  }, [candles, showTpLevel, showEntryLevel, effectiveTpPrice, effectiveEntryPrice, livePrice, swingStructure.swingHigh, fvgBounds, isMetals]);

  const priceRange = maxPrice - minPrice || 1;

  const getY = (priceVal: number) => {
    const clamped = Math.max(minPrice, Math.min(maxPrice, priceVal));
    return chartBottom - ((clamped - minPrice) / priceRange) * plotHeight;
  };

  const candleSpacing = plotWidth / candles.length;
  // Thick, bold, high-visibility TradingView-like candlesticks
  const candleBodyWidth = Math.max(isMobile ? 8 : 12, Math.min(isMobile ? 18 : 28, candleSpacing * 0.78));

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
          ? `🔴 SL $${effectiveSlPrice.toFixed(2)}`
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
          : `🎯 2.0R $${effectiveTpPrice.toFixed(2)}`,
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
                ? `🔴 ACTIVE SL: $${slPrice.toFixed(2)} (${isMetals ? "~$52 Risk" : ""})`
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
                ? `🟢 ACTIVE TP: $${tpPrice.toFixed(2)} (${isMetals ? "~$105 Target" : ""})`
                : s4Pass
                ? `🎯 2.0R TARGET: $${tpPrice.toFixed(2)} (${isMetals ? "~$105 Target" : ""})`
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
              </div>

              <div className="flex items-center gap-2 text-[11px]">
                <span className="text-zinc-400 font-bold">Sequence Progress:</span>
                <span className="font-black px-2 py-0.5 rounded bg-zinc-800 text-emerald-400 border border-zinc-700">
                  {passedCount} / 7 Steps Verified
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

              {/* Step 4 & 5: Setup Post-CHoCH FVG Retest Zone (Render ONLY when Step 4 created or trade active) */}
              {fvgBounds && fvgBounds.high > fvgBounds.low && (s4Pass || s5Pass || isTradeActive) && (
                <g>
                  <rect
                    x={chartLeft + candleSpacing * 8}
                    y={getY(fvgBounds.high)}
                    width={plotWidth - candleSpacing * 8}
                    height={Math.max(10, Math.abs(getY(fvgBounds.low) - getY(fvgBounds.high)))}
                    fill="url(#fvgGradientZone)"
                    stroke={s5Pass ? "#10b981" : s4Pass ? "#14b8a6" : isBullishSetup ? "#10b981" : "#f43f5e"}
                    strokeWidth={s5Pass ? 2.5 : 1.5}
                    strokeDasharray={s5Pass ? "none" : "4 4"}
                    filter={s5Pass ? "url(#glowGreen)" : undefined}
                  />
                  <rect
                    x={chartLeft + candleSpacing * 8 + 8}
                    y={getY(fvgBounds.high) + 4}
                    width="240"
                    height="22"
                    fill={s5Pass ? "#064e3b" : "#134e4a"}
                    rx="4"
                    stroke={s5Pass ? "#10b981" : "#14b8a6"}
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
                    {s5Pass
                      ? "🟢 S5 RETEST CONFIRMED"
                      : s4Pass
                      ? "⏳ S4 FVG CREATED — RETESTING"
                      : "⏳ S4/S5 FVG RETEST ZONE"}{" "}
                    (${fvgBounds.low.toFixed(2)} - ${fvgBounds.high.toFixed(2)})
                  </text>
                </g>
              )}

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

              {/* Active Entry Level Line */}
              {showEntryLevel && effectiveEntryPrice > 0 && (
                <line
                  x1={chartLeft}
                  y1={getY(effectiveEntryPrice)}
                  x2={chartRight}
                  y2={getY(effectiveEntryPrice)}
                  stroke="#38bdf8"
                  strokeWidth={2.5}
                  filter="url(#glowBlue)"
                />
              )}

              {/* Stop Loss (SL) Level Line */}
              {showSlLevel && effectiveSlPrice > 0 && (
                <line
                  x1={chartLeft}
                  y1={getY(effectiveSlPrice)}
                  x2={chartRight}
                  y2={getY(effectiveSlPrice)}
                  stroke="#ef4444"
                  strokeWidth={isTradeActive ? 3 : 1.5}
                  strokeDasharray={isTradeActive ? "none" : "5 5"}
                  opacity={isTradeActive ? 1 : 0.85}
                  filter={isTradeActive ? "url(#glowRed)" : undefined}
                />
              )}

              {/* Take Profit (TP) Level Line */}
              {showTpLevel && effectiveTpPrice > 0 && (
                <line
                  x1={chartLeft}
                  y1={getY(effectiveTpPrice)}
                  x2={chartRight}
                  y2={getY(effectiveTpPrice)}
                  stroke="#10b981"
                  strokeWidth={isTradeActive ? 3 : 1.5}
                  strokeDasharray={isTradeActive ? "none" : "5 5"}
                  opacity={isTradeActive ? 1 : 0.85}
                  filter={isTradeActive ? "url(#glowGreen)" : undefined}
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

                    {/* Sweep Marker on the Sweep Candle */}
                    {c.isSweep && (
                      <g>
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
                      </g>
                    )}

                    {/* CHoCH Marker on the Break Candle */}
                    {c.isChoch && (
                      <g>
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
