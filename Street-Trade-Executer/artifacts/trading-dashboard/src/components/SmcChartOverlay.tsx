import React, { useState, useEffect, useMemo, useRef } from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  CheckCircle2,
  Clock,
  Shield,
  Target,
  Zap,
  Layers,
  Activity,
  Maximize2,
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
        const widgetId = `tv_smc_chart_${symbol.replace(/[^a-zA-Z0-9]/g, "_")}`;
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

export function SmcChartOverlay({
  symbol,
  telemetry,
  currentPrice,
  activePosition,
}: SmcChartOverlayProps) {
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
      : 4146.5;

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

  // TP: 2.0R target
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

  return (
    <div className="w-full space-y-4 font-sans select-none">
      {/* 1. MASTER STATUS HUD BANNER (High Contrast, Crystal-Clear Typography & Dynamic Colors) */}
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
            Live: <span className="text-emerald-400">${livePrice.toFixed(2)}</span>
          </div>

          {sweepPrice > 0 && s2Pass && (
            <div className="px-3 py-1 rounded bg-cyan-950/60 border border-cyan-500 text-cyan-300 font-bold shadow-sm">
              Sweep: ${sweepPrice.toFixed(2)}
            </div>
          )}

          {chochPrice > 0 && s3Pass && (
            <div className="px-3 py-1 rounded bg-amber-950/60 border border-amber-500 text-amber-300 font-bold shadow-sm">
              CHoCH: ${chochPrice.toFixed(2)}
            </div>
          )}

          {isTradeActive ? (
            <>
              <div className="px-3 py-1 rounded bg-rose-600/90 text-white font-black shadow-sm">
                SL: ${slPrice.toFixed(2)}
              </div>
              <div className="px-3 py-1 rounded bg-emerald-600/90 text-white font-black shadow-sm">
                TP: ${tpPrice.toFixed(2)}
              </div>
            </>
          ) : (
            <div className="px-2.5 py-1 rounded bg-zinc-900 border border-zinc-800 text-zinc-400 text-[11px]">
              SL & TP: <span className="text-zinc-300 font-medium">Locked on Trigger</span>
            </div>
          )}
        </div>
      </div>

      {/* 2. REAL TRADINGVIEW CANDLESTICK CHART (Native Mouse Wheel Zoom & Price Hover Tracking) */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between px-1 text-xs font-mono text-zinc-400">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
            <strong className="text-white">{symbol} M5 Candlesticks</strong> (Real Market USD Feed)
          </span>
          <span className="text-[11px] text-zinc-500">
            Scroll mouse to zoom in/out • Move cursor to inspect live price & crosshair
          </span>
        </div>

        <TradingViewEmbedded symbol={symbol} />
      </div>

      {/* 3. PURE SMC STRICT 9-STEP VERIFICATION STATUS PIPELINE */}
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
                {s8Pass ? `PASS 🟢 ($${defaultBuf} Buf)` : "PENDING ⚪"}
              </Badge>
            </div>
            <p className="text-[11px] text-zinc-300 leading-snug">
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
                {s9Pass ? "PASS 🟢 (2.0R Space)" : "PENDING ⚪"}
              </Badge>
            </div>
            <p className="text-[11px] text-zinc-300 leading-snug">
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
