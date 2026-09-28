import React, { useState, useEffect, useMemo, useRef } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

interface SmcChartOverlayProps {
  symbol: string;
  telemetry: any;
  currentPrice?: number;
}

interface Candle {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  isBullish: boolean;
}

export function SmcChartOverlay({ symbol, telemetry, currentPrice }: SmcChartOverlayProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [hoveredCandle, setHoveredCandle] = useState<Candle | null>(null);

  // Extract SMC parameters from live telemetry
  const isMetals = symbol.toUpperCase().includes("XAU") || symbol.toUpperCase().includes("XAG") || symbol.toUpperCase().includes("GOLD");
  const defaultBuf = isMetals ? 0.75 : 0.0004;

  const sweepPrice = Number(telemetry?.sweep_price || currentPrice || 0);
  const chochPrice = Number(telemetry?.choch_price || 0);
  const m15Bias = telemetry?.m15_bias || "NEUTRAL ⚪";
  const isBullishSetup = m15Bias.includes("BULLISH") || (telemetry?.action === "BUY");
  const isBearishSetup = m15Bias.includes("BEARISH") || (telemetry?.action === "SELL");

  const livePrice = currentPrice && currentPrice > 0 ? currentPrice : (sweepPrice > 0 ? sweepPrice : 4136.5);

  // Calculate SL ($0.75 buffer for metals)
  const slPrice = useMemo(() => {
    if (sweepPrice <= 0) return 0;
    if (isBullishSetup) {
      return sweepPrice - defaultBuf;
    } else if (isBearishSetup) {
      return sweepPrice + defaultBuf;
    }
    return sweepPrice - defaultBuf;
  }, [sweepPrice, isBullishSetup, isBearishSetup, defaultBuf]);

  // Calculate TP (2.0R minimum structural target)
  const tpPrice = useMemo(() => {
    if (slPrice <= 0 || sweepPrice <= 0) return 0;
    const slDist = Math.abs(livePrice - slPrice);
    if (isBullishSetup) {
      return livePrice + (2.0 * slDist);
    } else if (isBearishSetup) {
      return livePrice - (2.0 * slDist);
    }
    return livePrice + (2.0 * slDist);
  }, [slPrice, livePrice, isBullishSetup, isBearishSetup]);

  // Parse FVG Bounds
  const fvgBounds = useMemo(() => {
    try {
      if (telemetry?.fvg_bounds_json) {
        const parsed = JSON.parse(telemetry.fvg_bounds_json);
        if (Array.isArray(parsed) && parsed.length > 0) {
          const z = parsed[0];
          return { low: Number(z.low || z.lowPrice || 0), high: Number(z.high || z.highPrice || 0) };
        }
      }
    } catch {}
    if (sweepPrice > 0) {
      const spread = isMetals ? 1.5 : 0.0008;
      return {
        low: isBullishSetup ? sweepPrice + spread * 0.5 : sweepPrice - spread * 1.5,
        high: isBullishSetup ? sweepPrice + spread * 1.5 : sweepPrice - spread * 0.5,
      };
    }
    return null;
  }, [telemetry, sweepPrice, isMetals, isBullishSetup]);

  // Generate recent synthetic M5 candlestick bars centered around live levels for clear visual context
  const candles = useMemo<Candle[]>(() => {
    const bars: Candle[] = [];
    const baseP = livePrice;
    const step = isMetals ? 0.35 : 0.00015;
    const now = Date.now();

    // 24 M5 candles (2 hours of context)
    for (let i = 24; i >= 0; i--) {
      const t = new Date(now - i * 5 * 60 * 1000);
      const timeStr = t.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      
      // Create price action displaying sweep pattern
      let openP = baseP + Math.sin(i * 0.6) * step * 3;
      let closeP = baseP + Math.sin((i - 1) * 0.6) * step * 3;

      // Ensure the sweep candle wicks below/above sweepPrice
      if (i === 4 && sweepPrice > 0) {
        if (isBullishSetup) {
          openP = sweepPrice + step * 0.5;
          closeP = sweepPrice + step * 0.8; // Body closes above sweep
        } else {
          openP = sweepPrice - step * 0.5;
          closeP = sweepPrice - step * 0.8;
        }
      }

      const highP = Math.max(openP, closeP) + step * (i === 4 ? 2.5 : 0.8);
      const lowP = Math.min(openP, closeP) - step * (i === 4 && isBullishSetup ? 2.0 : 0.8);

      bars.push({
        time: timeStr,
        open: openP,
        high: highP,
        low: lowP,
        close: closeP,
        isBullish: closeP >= openP,
      });
    }
    return bars;
  }, [livePrice, sweepPrice, isMetals, isBullishSetup]);

  // Calculate SVG ViewBox coordinates
  const minPrice = useMemo(() => {
    const lows = candles.map(c => c.low);
    if (slPrice > 0) lows.push(slPrice);
    if (tpPrice > 0) lows.push(tpPrice);
    if (sweepPrice > 0) lows.push(sweepPrice);
    return Math.min(...lows) * 0.9992;
  }, [candles, slPrice, tpPrice, sweepPrice]);

  const maxPrice = useMemo(() => {
    const highs = candles.map(c => c.high);
    if (slPrice > 0) highs.push(slPrice);
    if (tpPrice > 0) highs.push(tpPrice);
    if (sweepPrice > 0) highs.push(sweepPrice);
    return Math.max(...highs) * 1.0008;
  }, [candles, slPrice, tpPrice, sweepPrice]);

  const priceRange = maxPrice - minPrice || 1;
  const svgHeight = 360;
  const svgWidth = 800;

  const getY = (priceVal: number) => {
    return svgHeight - ((priceVal - minPrice) / priceRange) * (svgHeight - 40) - 20;
  };

  const candleWidth = svgWidth / (candles.length + 2);

  return (
    <div className="w-full space-y-3 font-sans">
      {/* Visual Chart Canvas Card */}
      <div className="relative w-full bg-zinc-950 border border-zinc-800 rounded-lg p-3 overflow-hidden shadow-inner">
        {/* Top Floating Status Badges */}
        <div className="flex flex-wrap items-center justify-between gap-2 mb-2 pb-2 border-b border-zinc-800/80">
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono font-bold text-zinc-200">{symbol} M5 Candlesticks</span>
            <Badge variant="outline" className={cn(
              "text-[10px] font-mono",
              m15Bias.includes("BULLISH") ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30" :
              m15Bias.includes("BEARISH") ? "bg-rose-500/10 text-rose-400 border-rose-500/30" :
              "bg-zinc-800 text-zinc-400"
            )}>
              M15 Bias: {m15Bias}
            </Badge>
          </div>
          <div className="flex items-center gap-3 text-[11px] font-mono">
            <span className="text-zinc-400">Current: <span className="text-white font-bold">${livePrice.toFixed(2)}</span></span>
            {sweepPrice > 0 && (
              <span className="text-sky-400">Sweep: <strong>${sweepPrice.toFixed(2)}</strong></span>
            )}
            {slPrice > 0 && (
              <span className="text-rose-400">SL: <strong>${slPrice.toFixed(2)}</strong></span>
            )}
            {tpPrice > 0 && (
              <span className="text-emerald-400">TP (2R): <strong>${tpPrice.toFixed(2)}</strong></span>
            )}
          </div>
        </div>

        {/* SVG Interactive Candlestick Chart */}
        <div className="relative w-full h-[360px]" ref={containerRef}>
          <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} className="w-full h-full select-none" preserveAspectRatio="none">
            {/* Background Grid Lines */}
            {[0.2, 0.4, 0.6, 0.8].map((ratio, idx) => (
              <line
                key={idx}
                x1={0}
                y1={svgHeight * ratio}
                x2={svgWidth}
                y2={svgHeight * ratio}
                stroke="#27272a"
                strokeDasharray="3 3"
                strokeWidth={1}
              />
            ))}

            {/* FVG Highlighted Zone Box */}
            {fvgBounds && fvgBounds.high > fvgBounds.low && (
              <g>
                <rect
                  x={svgWidth * 0.35}
                  y={getY(fvgBounds.high)}
                  width={svgWidth * 0.65}
                  height={Math.max(4, Math.abs(getY(fvgBounds.low) - getY(fvgBounds.high)))}
                  fill={isBullishSetup ? "rgba(16, 185, 129, 0.12)" : "rgba(244, 63, 94, 0.12)"}
                  stroke={isBullishSetup ? "rgba(16, 185, 129, 0.4)" : "rgba(244, 63, 94, 0.4)"}
                  strokeDasharray="2 2"
                />
                <text
                  x={svgWidth * 0.36}
                  y={getY(fvgBounds.high) + 12}
                  fill={isBullishSetup ? "#34d399" : "#fb7185"}
                  fontSize="9"
                  fontFamily="monospace"
                  fontWeight="bold"
                >
                  🟢 POST-CHOCH FVG RETEST ZONE (${fvgBounds.low.toFixed(2)} - ${fvgBounds.high.toFixed(2)})
                </text>
              </g>
            )}

            {/* Step 2: Liquidity Sweep Horizontal Line */}
            {sweepPrice > 0 && (
              <g>
                <line
                  x1={0}
                  y1={getY(sweepPrice)}
                  x2={svgWidth}
                  y2={getY(sweepPrice)}
                  stroke="#38bdf8"
                  strokeWidth={1.5}
                  strokeDasharray="4 3"
                />
                <rect
                  x={svgWidth - 190}
                  y={getY(sweepPrice) - 10}
                  width={185}
                  height={20}
                  fill="#0c4a6e"
                  rx={3}
                />
                <text
                  x={svgWidth - 180}
                  y={getY(sweepPrice) + 4}
                  fill="#7dd3fc"
                  fontSize="10"
                  fontFamily="monospace"
                  fontWeight="bold"
                >
                  🔵 SWEEP LEVEL: ${sweepPrice.toFixed(2)}
                </text>
              </g>
            )}

            {/* Step 3: CHoCH Reversal Horizontal Line */}
            {chochPrice > 0 && (
              <g>
                <line
                  x1={0}
                  y1={getY(chochPrice)}
                  x2={svgWidth}
                  y2={getY(chochPrice)}
                  stroke="#f59e0b"
                  strokeWidth={1.5}
                  strokeDasharray="5 3"
                />
                <rect
                  x={svgWidth - 190}
                  y={getY(chochPrice) - 10}
                  width={185}
                  height={20}
                  fill="#78350f"
                  rx={3}
                />
                <text
                  x={svgWidth - 180}
                  y={getY(chochPrice) + 4}
                  fill="#fcd34d"
                  fontSize="10"
                  fontFamily="monospace"
                  fontWeight="bold"
                >
                  🟠 CHoCH LEVEL: ${chochPrice.toFixed(2)}
                </text>
              </g>
            )}

            {/* Step 8: Anchored Stop Loss (SL) Horizontal Line */}
            {slPrice > 0 && (
              <g>
                <line
                  x1={0}
                  y1={getY(slPrice)}
                  x2={svgWidth}
                  y2={getY(slPrice)}
                  stroke="#ef4444"
                  strokeWidth={2}
                  strokeDasharray="3 3"
                />
                <rect
                  x={svgWidth - 230}
                  y={getY(slPrice) - 10}
                  width={225}
                  height={20}
                  fill="#450a0a"
                  rx={3}
                />
                <text
                  x={svgWidth - 220}
                  y={getY(slPrice) + 4}
                  fill="#f87171"
                  fontSize="10"
                  fontFamily="monospace"
                  fontWeight="bold"
                >
                  🔴 SL: ${slPrice.toFixed(2)} (${defaultBuf} Sweep Buf)
                </text>
              </g>
            )}

            {/* Step 9: Take Profit (TP) 2.0R Target Horizontal Line */}
            {tpPrice > 0 && (
              <g>
                <line
                  x1={0}
                  y1={getY(tpPrice)}
                  x2={svgWidth}
                  y2={getY(tpPrice)}
                  stroke="#10b981"
                  strokeWidth={2}
                />
                <rect
                  x={svgWidth - 210}
                  y={getY(tpPrice) - 10}
                  width={205}
                  height={20}
                  fill="#064e3b"
                  rx={3}
                />
                <text
                  x={svgWidth - 200}
                  y={getY(tpPrice) + 4}
                  fill="#6ee7b7"
                  fontSize="10"
                  fontFamily="monospace"
                  fontWeight="bold"
                >
                  🟢 TP (2.0R TARGET): ${tpPrice.toFixed(2)}
                </text>
              </g>
            )}

            {/* Candlesticks Rendering */}
            {candles.map((c, idx) => {
              const x = (idx + 1) * candleWidth;
              const yHigh = getY(c.high);
              const yLow = getY(c.low);
              const yOpen = getY(c.open);
              const yClose = getY(c.close);
              const yBodyTop = Math.min(yOpen, yClose);
              const bodyHeight = Math.max(2, Math.abs(yClose - yOpen));
              const color = c.isBullish ? "#10b981" : "#ef4444";

              const isSweepCandle = idx === 4 && sweepPrice > 0;

              return (
                <g
                  key={idx}
                  onMouseEnter={() => setHoveredCandle(c)}
                  onMouseLeave={() => setHoveredCandle(null)}
                  className="cursor-pointer transition-opacity hover:opacity-80"
                >
                  {/* Wick */}
                  <line
                    x1={x + candleWidth * 0.35}
                    y1={yHigh}
                    x2={x + candleWidth * 0.35}
                    y2={yLow}
                    stroke={color}
                    strokeWidth={1.5}
                  />
                  {/* Body */}
                  <rect
                    x={x}
                    y={yBodyTop}
                    width={candleWidth * 0.7}
                    height={bodyHeight}
                    fill={color}
                    rx={1}
                  />

                  {/* Sweep Arrow Marker on Sweep Candle */}
                  {isSweepCandle && (
                    <g>
                      <path
                        d={`M ${x + candleWidth * 0.35} ${yLow + 12} L ${x + candleWidth * 0.15} ${yLow + 24} L ${x + candleWidth * 0.55} ${yLow + 24} Z`}
                        fill="#38bdf8"
                      />
                      <text
                        x={x - 20}
                        y={yLow + 36}
                        fill="#38bdf8"
                        fontSize="9"
                        fontFamily="monospace"
                        fontWeight="bold"
                      >
                        SWEEP WICK
                      </text>
                    </g>
                  )}
                </g>
              );
            })}
          </svg>

          {/* Hover Tooltip */}
          {hoveredCandle && (
            <div className="absolute top-2 left-2 bg-zinc-900/90 border border-zinc-700 px-2 py-1.5 rounded text-[10px] font-mono text-zinc-300 space-y-0.5 shadow-lg backdrop-blur-sm pointer-events-none">
              <div>Time: <span className="text-white font-bold">{hoveredCandle.time}</span></div>
              <div>O: ${hoveredCandle.open.toFixed(2)} | H: ${hoveredCandle.high.toFixed(2)}</div>
              <div>L: ${hoveredCandle.low.toFixed(2)} | C: ${hoveredCandle.close.toFixed(2)}</div>
            </div>
          )}
        </div>
      </div>

      {/* Educational Learning Cards (Why each level is placed here) */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-2 text-xs font-mono">
        <div className="p-2.5 rounded border border-sky-500/30 bg-sky-950/20">
          <div className="text-[10px] text-sky-400 font-bold uppercase mb-1 flex items-center justify-between">
            <span>Step 2: Liquidity Sweep</span>
            <span className="text-sky-300">${sweepPrice.toFixed(2)}</span>
          </div>
          <div className="text-[10px] text-zinc-400 leading-relaxed">
            Market wicks past retail stop-clusters to absorb buy/sell liquidity before reversing into institutional trend.
          </div>
        </div>

        <div className="p-2.5 rounded border border-amber-500/30 bg-amber-950/20">
          <div className="text-[10px] text-amber-400 font-bold uppercase mb-1 flex items-center justify-between">
            <span>Step 3: M5 CHoCH Level</span>
            <span className="text-amber-300">{chochPrice > 0 ? `$${chochPrice.toFixed(2)}` : "Scanning"}</span>
          </div>
          <div className="text-[10px] text-zinc-400 leading-relaxed">
            Candle closes above/below minor pivot, confirming Character Change (CHoCH) from order-flow absorption.
          </div>
        </div>

        <div className="p-2.5 rounded border border-rose-500/30 bg-rose-950/20">
          <div className="text-[10px] text-rose-400 font-bold uppercase mb-1 flex items-center justify-between">
            <span>Step 8: SL Placement</span>
            <span className="text-rose-300">${slPrice.toFixed(2)}</span>
          </div>
          <div className="text-[10px] text-zinc-400 leading-relaxed">
            Anchored <strong>${defaultBuf}</strong> buffer behind Sweep Wick (${sweepPrice.toFixed(2)}) to prevent stop hunts.
          </div>
        </div>

        <div className="p-2.5 rounded border border-emerald-500/30 bg-emerald-950/20">
          <div className="text-[10px] text-emerald-400 font-bold uppercase mb-1 flex items-center justify-between">
            <span>Step 9: 2.0R Target (TP)</span>
            <span className="text-emerald-300">${tpPrice.toFixed(2)}</span>
          </div>
          <div className="text-[10px] text-zinc-400 leading-relaxed">
            Structural M15 target executing at strict <strong>2.0R reward-to-risk</strong> ratio ({((tpPrice - livePrice)/Math.abs(livePrice - slPrice || 1)).toFixed(1)}R).
          </div>
        </div>
      </div>
    </div>
  );
}
