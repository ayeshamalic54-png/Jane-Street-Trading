import { useGetDashboard, useExecuteTrade, getGetDashboardQueryKey } from "@workspace/api-client-react";
import { useLiveDashboard } from "@/hooks/use-ws";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { Activity, Wifi, WifiOff, Send, Zap, ZapOff } from "lucide-react";
import { useState, useEffect } from "react";
import { AreaChart, Area, ResponsiveContainer } from "recharts";
import { useToast } from "@/hooks/use-toast";
import { useQueryClient } from "@tanstack/react-query";

let tvScriptLoadingPromise: Promise<void> | null = null;

function TradingViewWidget({ symbol }: { symbol: string }) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const mapSymbolToTV = (sym: string): string => {
      const s = sym.toUpperCase().replace("/", "");
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
      return s;
    };

    const tvSymbol = mapSymbolToTV(symbol);

    if (!tvScriptLoadingPromise) {
      tvScriptLoadingPromise = new Promise((resolve) => {
        const script = document.createElement("script");
        script.id = "tradingview-widget-loading-script";
        script.src = "https://s3.tradingview.com/tv.js";
        script.type = "text/javascript";
        script.onload = () => resolve();
        document.head.appendChild(script);
      });
    }

    tvScriptLoadingPromise.then(() => {
      if (container.current && typeof (window as any).TradingView !== "undefined") {
        new (window as any).TradingView.widget({
          width: "100%",
          height: 450,
          symbol: tvSymbol,
          interval: "5",
          timezone: "Etc/UTC",
          theme: "dark",
          style: "1",
          locale: "en",
          toolbar_bg: "#18181b",
          enable_publishing: false,
          hide_side_toolbar: false,
          allow_symbol_change: true,
          container_id: container.current.id,
          studies: ["RSI@tv-basicstudies", "MASimple@tv-basicstudies"],
        });
      }
    });
  }, [symbol]);

  return (
    <div className="w-full bg-zinc-950 p-1 border border-zinc-800 rounded-md">
      <div id={`tv-chart-${symbol.replace("/", "-")}`} ref={container} className="h-[450px] w-full" />
    </div>
  );
}

import { useRef } from "react";

export default function Dashboard() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [manualSymbol, setManualSymbol] = useState("");
  const [selectedChartSymbol, setSelectedChartSymbol] = useState("EURUSD");
  const [manualLots, setManualLots] = useState("0.01");
  const [manualSl, setManualSl] = useState("10");
  const [manualTp, setManualTp] = useState("20");
  const [manualEntry, setManualEntry] = useState("");

  const getPipSize = (sym: string): number => {
    const s = sym.toUpperCase();
    if (s.includes("JPY")) return 0.01;
    if (s.includes("XAU")) return 0.1;
    if (s.includes("XAG")) return 0.01;
    if (s.includes("BTC")) return 1.0;
    if (s.includes("ETH")) return 0.1;
    if (s.includes("SOL") || s.includes("BNB") || s.includes("AVAX")) return 0.01;
    if (s.includes("XRP") || s.includes("ADA") || s.includes("DOGE") || s.includes("MATIC")) return 0.0001;
    if (["US500", "US30", "NAS100", "GER30", "UK100", "SPX", "DJI", "NDX"].some(x => s.includes(x))) return 1.0;
    if (["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMD", "META", "AMZN"].some(x => s.includes(x))) return 0.1;
    return 0.0001;
  };

  const entryVal = parseFloat(manualEntry);
  const slPipsVal = parseFloat(manualSl);
  const tpPipsVal = parseFloat(manualTp);
  const s = manualSymbol.toUpperCase();
  const isCrypto = s.endsWith("USDT") || ["BTC", "ETH", "SOL", "BNB", "AVAX", "XRP", "ADA", "DOGE", "MATIC"].some(x => s.includes(x));
  const pipSize = getPipSize(manualSymbol);
  const hasCalc = !isNaN(entryVal) && entryVal > 0;
  
  const slDist = hasCalc ? (isCrypto ? entryVal * (slPipsVal / 100) : slPipsVal * pipSize) : 0;
  const tpDist = hasCalc ? (isCrypto ? entryVal * (tpPipsVal / 100) : tpPipsVal * pipSize) : 0;
  const pricePrecision = isCrypto ? 2 : (pipSize <= 0.0001 ? 5 : pipSize <= 0.01 ? 3 : 2);
  
  const buySlPrice = hasCalc && !isNaN(slPipsVal) ? (entryVal - slDist).toFixed(pricePrecision) : "—";
  const buyTp1Price = hasCalc && !isNaN(slPipsVal) ? (entryVal + slDist).toFixed(pricePrecision) : "—";
  const buyTp2Price = hasCalc && !isNaN(tpPipsVal) ? (entryVal + tpDist).toFixed(pricePrecision) : "—";
  const buyTp3Price = hasCalc && !isNaN(slPipsVal) ? (entryVal + slDist * 3.5).toFixed(pricePrecision) : "—";
  
  const sellSlPrice = hasCalc && !isNaN(slPipsVal) ? (entryVal + slDist).toFixed(pricePrecision) : "—";
  const sellTp1Price = hasCalc && !isNaN(slPipsVal) ? (entryVal - slDist).toFixed(pricePrecision) : "—";
  const sellTp2Price = hasCalc && !isNaN(tpPipsVal) ? (entryVal - tpDist).toFixed(pricePrecision) : "—";
  const sellTp3Price = hasCalc && !isNaN(slPipsVal) ? (entryVal - slDist * 3.5).toFixed(pricePrecision) : "—";

  const { data: httpData, isLoading } = useGetDashboard({
    query: {
      refetchInterval: 10000,
      queryKey: getGetDashboardQueryKey(),
    },
  });

  const { data: wsData, wsConnected } = useLiveDashboard();
  const [pnlHistory, setPnlHistory] = useState<{ t: number; pnl: number; eq: number }[]>([]);

  useEffect(() => {
    if (!wsData) return;
    setPnlHistory(prev => {
      const next = [...prev, { t: Date.now(), pnl: wsData.floatingProfit, eq: wsData.equity }];
      return next.slice(-90);
    });
  }, [wsData]);

  const executeTrade = useExecuteTrade();

  const dashboard = wsData ?? httpData;

  if (isLoading && !dashboard) {
    return (
      <div className="p-6 space-y-6">
        <Skeleton className="h-[48px] w-full" />
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-[120px] w-full" />)}
        </div>
      </div>
    );
  }

  if (!dashboard) return null;

  const {
    systemStatus,
    currentPair,
    equity,
    drawdownPercent,
    floatingProfit,
    zScore,
    hedgeRatio,
    obiA,
    obiB,
    tradesToday,
    maxTrades,
    activePositions,
    activeZones,
    botOnline,
    autoExecute,
  } = dashboard;

  const matchingAsset = dashboard.scannedAssets?.find(
    (a: any) => a.symbolPair.startsWith(selectedChartSymbol) || a.symbolPair.endsWith(selectedChartSymbol)
  );

  const selectedAssetAction = matchingAsset?.action ?? "NONE";
  const selectedAssetZScore = matchingAsset?.zScore ?? 0.0;
  const selectedAssetWinRate = matchingAsset?.winRate ?? 50.0;

  const matchingPosition = dashboard.activePositions?.find((p: any) => {
    const symUpper = p.symbol.toUpperCase();
    const chartUpper = selectedChartSymbol.toUpperCase();
    return symUpper.includes(chartUpper) || chartUpper.includes(symUpper);
  });
  const hasActivePosition = matchingPosition != null;
  const activePositionType = matchingPosition?.type ?? "BUY";

  const selectedAssetZones = dashboard.activeZones?.filter(
    (z: any) => z.label.includes(selectedChartSymbol)
  ) ?? [];

  const getStatusColor = (status: string) => {
    if (status.startsWith("RUNNING")) return "bg-green-500 shadow-[0_0_10px_rgba(34,197,94,0.5)]";
    if (status.startsWith("HALTED")) return "bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.5)]";
    return "bg-gray-500";
  };

  const formatMoney = (val: number) =>
    new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(val);

  const handleManualTrade = (direction: "BUY" | "SELL") => {
    const sym = manualSymbol.trim().toUpperCase();
    const lots = parseFloat(manualLots);
    const slPips = parseFloat(manualSl);
    const tpPips = parseFloat(manualTp);

    if (!sym || sym.length < 3) {
      toast({ title: "Symbol required", description: "Enter a valid MT5 symbol (e.g. EURUSD)", variant: "destructive" });
      return;
    }
    if (isNaN(lots) || lots <= 0) {
      toast({ title: "Invalid lot size", variant: "destructive" });
      return;
    }

    executeTrade.mutate(
      { data: { symbol: sym, direction, lots, slPips: isNaN(slPips) ? undefined : slPips, tpPips: isNaN(tpPips) ? undefined : tpPips } },
      {
        onSuccess: () => {
          toast({
            title: `${direction} order queued`,
            description: `${sym} · ${lots} lots · Bot executes in ~2s`,
          });
          queryClient.invalidateQueries({ queryKey: getGetDashboardQueryKey() });
        },
        onError: () => {
          toast({ title: "Failed to queue trade", description: "Check bot connectivity", variant: "destructive" });
        },
      }
    );
  };

  const zoneBullish = (type: string) => type.startsWith("BULLISH");

  return (
    <div className="flex flex-col h-full overflow-auto bg-zinc-950 text-foreground">
      {/* Top Banner */}
      <div className={cn(
        "flex items-center justify-between px-6 py-2 text-xs font-semibold tracking-wider",
        botOnline
          ? "bg-green-500/10 text-green-500 border-b border-green-500/20"
          : "bg-amber-500/10 text-amber-500 border-b border-amber-500/20"
      )}>
        <div className="flex items-center gap-3">
          {botOnline ? <Wifi className="h-4 w-4" /> : <WifiOff className="h-4 w-4" />}
          {botOnline ? "BOT CONNECTED — LIVE DATA" : "BOT OFFLINE — LAST KNOWN DATA"}
          <span className={cn(
            "flex items-center gap-1 px-2 py-0.5 rounded-sm text-[10px] border",
            wsConnected
              ? "bg-cyan-500/10 text-cyan-400 border-cyan-500/20"
              : "bg-muted/30 text-muted-foreground border-border"
          )}>
            <Activity className="h-3 w-3" />
            {wsConnected ? "WS LIVE" : "POLLING"}
          </span>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            {autoExecute ? (
              <span className="flex items-center gap-1 text-green-400">
                <Zap className="h-3 w-3" />AUTO EXEC ON
              </span>
            ) : (
              <span className="flex items-center gap-1 text-amber-400">
                <ZapOff className="h-3 w-3" />SIGNALS ONLY
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <div className={cn("h-2 w-2 rounded-full", getStatusColor(systemStatus))} />
            <span>{systemStatus}</span>
          </div>
          <div className="text-zinc-500 font-mono text-[10px] uppercase flex items-center gap-2">
            <span>Scan Feed:</span>
            <span className={cn("px-1.5 py-0.5 rounded-sm text-[10px] font-bold border transition-all duration-300", (dashboard.scannedAssets && dashboard.scannedAssets.some((s: any) => s.symbolPair.includes("USDT") || ["BTC", "ETH", "SOL", "BNB"].some((x) => s.symbolPair.includes(x)))) ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30 shadow-[0_0_10px_rgba(16,185,129,0.15)]" : "text-zinc-600 border-zinc-800 bg-zinc-900/20 opacity-50")}>Crypto</span>
            <span className={cn("px-1.5 py-0.5 rounded-sm text-[10px] font-bold border transition-all duration-300", (dashboard.scannedAssets && dashboard.scannedAssets.some((s: any) => s.symbolPair.includes("XAU") || s.symbolPair.includes("XAG"))) ? "bg-amber-500/10 text-amber-400 border-amber-500/30 shadow-[0_0_10px_rgba(245,158,11,0.15)]" : "text-zinc-600 border-zinc-800 bg-zinc-900/20 opacity-50")}>Metals</span>
            <span className={cn("px-1.5 py-0.5 rounded-sm text-[10px] font-bold border transition-all duration-300", (dashboard.scannedAssets && dashboard.scannedAssets.some((s: any) => !s.symbolPair.includes("USDT") && !s.symbolPair.includes("XAU") && !s.symbolPair.includes("XAG") && !["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "META", "AMZN"].some((x) => s.symbolPair.includes(x)))) ? "bg-cyan-500/10 text-cyan-400 border-cyan-500/30 shadow-[0_0_10px_rgba(6,182,212,0.15)]" : "text-zinc-600 border-zinc-800 bg-zinc-900/20 opacity-50")}>Forex</span>
            <span className={cn("px-1.5 py-0.5 rounded-sm text-[10px] font-bold border transition-all duration-300", (dashboard.scannedAssets && dashboard.scannedAssets.some((s: any) => ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "META", "AMZN"].some((x) => s.symbolPair.includes(x)))) ? "bg-blue-500/10 text-blue-400 border-blue-500/30 shadow-[0_0_10px_rgba(59,130,246,0.15)]" : "text-zinc-600 border-zinc-800 bg-zinc-900/20 opacity-50")}>Stocks</span>
          </div>
          <div className="font-mono bg-zinc-900/70 border border-zinc-800 px-2 py-0.5 rounded text-[11px] text-zinc-400 shadow-[0_0_8px_rgba(255,255,255,0.02)]">
            TARGET LEG: <span className="font-bold text-zinc-100">{currentPair}</span>
          </div>
        </div>
      </div>

      <div className="p-6 space-y-6">
        {/* Key Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card className="bg-zinc-900 border-zinc-800 border-t-2 border-t-sky-500 hover:border-sky-400/40 transition-all shadow-[0_4px_24px_rgba(14,165,233,0.06)] rounded-md">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs text-zinc-500 uppercase tracking-wider font-mono">Account Equity</CardTitle>
            </CardHeader>
            <CardContent className="pb-2">
              <div className="text-2xl font-mono text-sky-400 font-bold">{formatMoney(equity)}</div>
              {pnlHistory.length > 2 && (
                <ResponsiveContainer width="100%" height={36}>
                  <AreaChart data={pnlHistory} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <Area type="monotone" dataKey="eq" stroke="#0ea5e9" strokeWidth={1.5} fill="url(#eqGrad)" dot={false} isAnimationActive={false} />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>

          <Card className={cn(
            "bg-zinc-900 border-zinc-800 border-t-2 transition-all rounded-md",
            floatingProfit >= 0 
              ? "border-t-emerald-500 shadow-[0_4px_24px_rgba(16,185,129,0.06)] hover:border-emerald-400/40" 
              : "border-t-rose-500 shadow-[0_4px_24px_rgba(244,63,94,0.06)] hover:border-rose-400/40"
          )}>
            <CardHeader className="pb-2">
              <CardTitle className="text-xs text-zinc-500 uppercase tracking-wider font-mono">Floating P&L</CardTitle>
            </CardHeader>
            <CardContent className="pb-2">
              <div className={cn("text-2xl font-mono font-bold", floatingProfit >= 0 ? "text-emerald-400" : "text-rose-400")}>
                {floatingProfit > 0 ? "+" : ""}{formatMoney(floatingProfit)}
              </div>
              {pnlHistory.length > 2 && (
                <ResponsiveContainer width="100%" height={36}>
                  <AreaChart data={pnlHistory} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={floatingProfit >= 0 ? "#10b981" : "#f43f5e"} stopOpacity={0.3} />
                        <stop offset="95%" stopColor={floatingProfit >= 0 ? "#10b981" : "#f43f5e"} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <Area type="monotone" dataKey="pnl" stroke={floatingProfit >= 0 ? "#10b981" : "#f43f5e"} strokeWidth={1.5} fill="url(#pnlGrad)" dot={false} isAnimationActive={false} />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>

          <Card className="bg-zinc-900 border-zinc-800 border-t-2 border-t-amber-500 hover:border-amber-400/40 transition-all shadow-[0_4px_24px_rgba(245,158,11,0.06)] rounded-md">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs text-zinc-500 uppercase tracking-wider font-mono">Daily Drawdown</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex justify-between items-end">
                <div className="text-2xl font-mono text-amber-400">{drawdownPercent.toFixed(2)}%</div>
                <div className="text-[10px] text-zinc-500 mb-1 font-mono">
                  Halt: <span className="text-amber-500">4.2%</span> · Limit: <span className="text-red-500">5%</span>
                </div>
              </div>
              <Progress value={Math.min((drawdownPercent / 5) * 100, 100)} className="h-1.5 bg-zinc-800 [&>div]:bg-rose-500" />
            </CardContent>
          </Card>

          <Card className="bg-zinc-900 border-zinc-800 border-t-2 border-t-violet-500 hover:border-violet-400/40 transition-all shadow-[0_4px_24px_rgba(139,92,246,0.06)] rounded-md">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs text-zinc-500 uppercase tracking-wider font-mono">Trades Today</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-mono text-purple-400">{tradesToday} <span className="text-sm text-zinc-500">/ {maxTrades}</span></div>
              <div className="text-[10px] text-zinc-500 mt-1 font-mono">
                {autoExecute ? "Auto-exec active" : "Signals only"}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Quant Metrics + SMC Zones */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card className="bg-card border-border">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs text-muted-foreground uppercase tracking-wider">Kalman Filter · Statistical Arb</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div>
                <div className="flex justify-between items-end mb-2">
                  <span className="text-sm text-muted-foreground">Z-Score</span>
                  <span className={cn(
                    "font-mono text-lg font-bold",
                    Math.abs(zScore) >= 2 ? "text-red-400" : Math.abs(zScore) >= 1.5 ? "text-amber-400" : "text-foreground"
                  )}>{zScore.toFixed(3)}</span>
                </div>
                <div className="relative h-4 bg-muted rounded-sm overflow-hidden">
                  <div className="absolute left-1/2 top-0 bottom-0 w-px bg-foreground/30 z-10" />
                  <div className="absolute left-[16.66%] top-0 bottom-0 w-px bg-red-500/50 z-10" />
                  <div className="absolute left-[83.33%] top-0 bottom-0 w-px bg-red-500/50 z-10" />
                  <div
                    className={cn(
                      "absolute top-0 bottom-0 w-1 shadow-[0_0_8px_rgba(255,255,255,0.8)] z-20 transition-all duration-300",
                      Math.abs(zScore) >= 2 ? "bg-red-500" : "bg-primary"
                    )}
                    style={{ left: `${Math.max(0, Math.min(100, ((zScore + 3) / 6) * 100))}%` }}
                  />
                </div>
                <div className="flex justify-between text-xs text-muted-foreground mt-1 font-mono">
                  <span>-3.0</span><span>-2.0</span><span>0.0</span><span>+2.0</span><span>+3.0</span>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Hedge Ratio (β)</div>
                  <div className="font-mono text-lg">{hedgeRatio.toFixed(4)}</div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">OBI (A / B)</div>
                  <div className="font-mono text-sm grid grid-cols-2 gap-2">
                    <div><span className="text-muted-foreground">A:</span> <span className={obiA > 0 ? "text-green-500" : "text-red-500"}>{obiA.toFixed(2)}</span></div>
                    <div><span className="text-muted-foreground">B:</span> <span className={obiB > 0 ? "text-green-500" : "text-red-500"}>{obiB.toFixed(2)}</span></div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card border-border">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-xs text-muted-foreground uppercase tracking-wider">SMC Zones · FVG · OB · Breaker</CardTitle>
                {activeZones.length > 0 && (
                  <Badge variant="outline" className="text-[10px] rounded-sm bg-indigo-500/10 text-indigo-400 border-indigo-500/30 font-bold shadow-[0_0_8px_rgba(99,102,241,0.08)]">
                    {activeZones.length} ACTIVE
                  </Badge>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {activeZones.length === 0 ? (
                <div className="text-sm text-muted-foreground py-4 text-center border border-dashed border-border rounded">
                  No active zones — bot writes zones every ~20s when connected
                </div>
              ) : (
                <div className="space-y-2 max-h-[200px] overflow-y-auto">
                  {activeZones.map((zone, i) => {
                    const bull = zoneBullish(zone.type);
                    const zoneLabel = zone.type.replace("BULLISH_", "").replace("BEARISH_", "");
                    return (
                      <div key={i} className="flex items-center justify-between p-2 rounded bg-muted/30 border border-border">
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className={cn(
                            "font-mono rounded-sm text-[10px] px-1.5 py-0.5 border transition-all duration-300 font-bold",
                            bull
                              ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30 shadow-[0_0_8px_rgba(16,185,129,0.08)]"
                              : "bg-rose-500/10 text-rose-400 border-rose-500/30 shadow-[0_0_8px_rgba(244,63,94,0.08)]"
                          )}>
                            {zoneLabel}
                          </Badge>
                          <span className="text-xs text-muted-foreground">{zone.label.split("·")[1]?.trim()}</span>
                        </div>
                        <div className="font-mono text-xs text-foreground">{zone.range}</div>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Live Chart & Signals Confluence */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <Card className="lg:col-span-2 bg-card border-border border-t-2 border-t-indigo-500/70 hover:border-indigo-500/40 transition-all rounded-md shadow-[0_4px_20px_rgba(99,102,241,0.03)]">
            <CardHeader className="pb-2 flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-xs text-muted-foreground uppercase tracking-wider font-mono">Live Market Chart</CardTitle>
                <p className="text-xs text-muted-foreground mt-1">
                  Interactive real-time charting for: <span className="font-mono font-bold text-indigo-400">{selectedChartSymbol}</span> (Click on any asset below to view its chart)
                </p>
              </div>
              <Badge variant="outline" className="bg-indigo-500/10 text-indigo-400 border-indigo-500/20 font-mono text-[10px] rounded-sm">
                TRADINGVIEW FEED
              </Badge>
            </CardHeader>
            <CardContent>
              <TradingViewWidget symbol={selectedChartSymbol} />
            </CardContent>
          </Card>

          <Card className="bg-card border-border border-t-2 border-t-indigo-500/70 hover:border-indigo-500/40 transition-all rounded-md shadow-[0_4px_20px_rgba(99,102,241,0.03)]">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs text-muted-foreground uppercase tracking-wider font-mono">Signal & Confluence Matrix</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="p-3 bg-zinc-900/50 border border-zinc-800 rounded-md">
                <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-mono mb-2">Confluence Signal</div>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Auto-Scan Status:</span>
                  <Badge variant="outline" className={cn(
                    "text-xs font-mono px-3 py-1 font-extrabold rounded-sm border transition-all duration-300",
                    hasActivePosition
                      ? activePositionType === "BUY"
                        ? "bg-blue-500/15 text-blue-400 border-blue-500/40 shadow-[0_0_15px_rgba(59,130,246,0.2)]"
                        : "bg-purple-500/15 text-purple-400 border-purple-500/40 shadow-[0_0_15px_rgba(168,85,247,0.2)]"
                      : selectedAssetAction === "BUY_SPREAD"
                      ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/40 shadow-[0_0_15px_rgba(16,185,129,0.2)]"
                      : selectedAssetAction === "SELL_SPREAD"
                      ? "bg-rose-500/15 text-rose-400 border-rose-500/40 shadow-[0_0_15px_rgba(244,63,94,0.2)]"
                      : "bg-zinc-900/80 text-zinc-400 border-zinc-800"
                  )}>
                    {hasActivePosition 
                      ? `IN TRADE (${activePositionType})` 
                      : selectedAssetAction === "NONE" 
                      ? "WAITING (NO SIGNAL)" 
                      : selectedAssetAction.replace("_SPREAD", "")}
                  </Badge>
                </div>
              </div>

              <div className="p-3 bg-zinc-900/50 border border-zinc-800 rounded-md space-y-2">
                <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-mono">Statistical Metrics</div>
                <div className="flex justify-between text-xs font-mono">
                  <span>Current Z-Score:</span>
                  <span className={cn(
                    "font-bold font-mono",
                    Math.abs(selectedAssetZScore) >= 1.8 ? "text-red-400" : "text-zinc-300"
                  )}>{selectedAssetZScore.toFixed(3)}</span>
                </div>
                <div className="flex justify-between text-xs font-mono">
                  <span>Historical Win Rate:</span>
                  <span className="text-blue-400 font-bold font-mono">{selectedAssetWinRate.toFixed(1)}%</span>
                </div>
              </div>

              <div className="p-3 bg-zinc-900/50 border border-zinc-800 rounded-md space-y-2">
                <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-mono">Active SMC Confluence Zones</div>
                {selectedAssetZones.length === 0 ? (
                  <div className="text-[11px] text-zinc-500 italic font-mono">No active Order Blocks or Fair Value Gaps detected for {selectedChartSymbol}</div>
                ) : (
                  <div className="space-y-1.5 max-h-[160px] overflow-y-auto pr-1">
                    {selectedAssetZones.map((z: any, idx: number) => {
                      const isBull = z.type.includes("BULLISH");
                      const zoneName = z.type.replace("BULLISH_", "").replace("BEARISH_", "");
                      return (
                        <div key={idx} className="flex justify-between items-center text-xs p-1.5 bg-zinc-950 rounded border border-zinc-800">
                          <span className={cn("font-bold font-mono text-[10px]", isBull ? "text-green-400" : "text-red-400")}>
                            {isBull ? "🟢" : "🔴"} {zoneName}
                          </span>
                          <span className="font-mono text-[10px] text-zinc-400">{z.range}</span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Scanned Assets & Signals */}
        <Card className="bg-card border-border border-t-2 border-t-blue-500/70 hover:border-blue-500/40 transition-all rounded-md">
          <CardHeader className="pb-3 flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-xs text-muted-foreground uppercase tracking-wider font-mono">Multi-Asset Live Auto-Scan & Win Rates</CardTitle>
              <p className="text-xs text-muted-foreground mt-1">
                Bot scans enabled Forex, Crypto, Metals, and Stocks/Indices. Selects the highest win rate symbol with an active signal.
              </p>
            </div>
            <Badge variant="outline" className="bg-blue-500/10 text-blue-500 border-blue-500/20 font-mono text-[10px] rounded-sm">
              {dashboard.scannedAssets?.length ?? 0} ASSETS SCANNED
            </Badge>
          </CardHeader>
          <CardContent>
            {!dashboard.scannedAssets || dashboard.scannedAssets.length === 0 ? (
              <div className="text-sm text-muted-foreground py-8 text-center border border-dashed border-border rounded">
                No scanned assets found. Ensure the trading bot is running.
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow className="border-border hover:bg-transparent">
                    <TableHead className="font-mono text-xs">ASSET PAIR</TableHead>
                    <TableHead className="font-mono text-xs text-right">PRICE A</TableHead>
                    <TableHead className="font-mono text-xs text-right">PRICE B</TableHead>
                    <TableHead className="font-mono text-xs text-right">HISTORICAL WIN RATE</TableHead>
                    <TableHead className="font-mono text-xs text-center">CURRENT SIGNAL</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {dashboard.scannedAssets.map((asset: any) => (
                    <TableRow 
                      key={asset.symbolPair} 
                      className="border-border hover:bg-muted/30 cursor-pointer"
                      onClick={() => {
                        const parts = asset.symbolPair.split('/');
                        if (parts.length === 2) {
                          setSelectedChartSymbol(parts[0]);
                        }
                      }}
                    >
                      <TableCell className="font-mono font-medium">{asset.symbolPair}</TableCell>
                      <TableCell className="font-mono text-right">{asset.priceA.toFixed(5)}</TableCell>
                      <TableCell className="font-mono text-right">{asset.priceB.toFixed(5)}</TableCell>
                      <TableCell className="font-mono text-right font-semibold text-blue-400">
                        {asset.winRate.toFixed(1)}%
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge variant="outline" className={cn(
                          "rounded-sm text-xs font-mono px-2 py-0.5 border font-extrabold transition-all duration-300",
                          asset.action === "BUY_SPREAD"
                            ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30 shadow-[0_0_12px_rgba(16,185,129,0.12)]"
                            : asset.action === "SELL_SPREAD"
                            ? "bg-rose-500/10 text-rose-400 border-rose-500/30 shadow-[0_0_12px_rgba(244,63,94,0.12)]"
                            : "bg-zinc-900/60 text-zinc-500 border-zinc-800"
                        )}>
                          {asset.action === "NONE" ? "WAITING" : asset.action.replace("_SPREAD", "")}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* Manual Trade Execution */}
        <Card className="bg-card border-border border-primary/20">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <CardTitle className="text-xs text-muted-foreground uppercase tracking-wider">Manual Trade Execution</CardTitle>
              <Badge variant="outline" className="text-[10px] rounded-sm bg-blue-500/10 text-blue-500 border-blue-500/20">
                LIVE · MT5 via Bot · All Asset Classes
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              Queued to DB — bot executes within 2s. Works for Forex, Crypto, Metals, Stocks. Use exact MT5 symbol names.
            </p>
          </CardHeader>
          <CardContent className="space-y-3">
            {/* Row 1 — Symbol + Lots */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="md:col-span-2">
                <label className="text-[10px] uppercase tracking-wider text-muted-foreground block mb-1">Symbol</label>
                <Input
                  placeholder="EURUSD / BTCUSD / XAUUSD / AAPL"
                  value={manualSymbol}
                  onChange={(e) => setManualSymbol(e.target.value.toUpperCase())}
                  className="font-mono text-sm border-border bg-background"
                />
              </div>
              <div>
                <label className="text-[10px] uppercase tracking-wider text-muted-foreground block mb-1">Lot Size</label>
                <Input
                  type="number" step="0.01" min="0.01" placeholder="0.01"
                  value={manualLots}
                  onChange={(e) => setManualLots(e.target.value)}
                  className="font-mono text-sm border-border bg-background"
                />
              </div>
              <div>
                <label className="text-[10px] uppercase tracking-wider text-muted-foreground block mb-1">Entry Price</label>
                <Input
                  type="number" step="any" placeholder="e.g. 1.08500"
                  value={manualEntry}
                  onChange={(e) => setManualEntry(e.target.value)}
                  className="font-mono text-sm border-border bg-background"
                />
              </div>
            </div>

            {/* Row 2 — SL + TP Pips Settings */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[10px] uppercase tracking-wider text-muted-foreground block mb-1">SL (Pips)</label>
                <Input
                  type="number" min="5" placeholder="10"
                  value={manualSl}
                  onChange={(e) => setManualSl(e.target.value)}
                  className="font-mono text-sm border-border bg-background"
                />
              </div>
              <div>
                <label className="text-[10px] uppercase tracking-wider text-muted-foreground block mb-1">TP (Pips / Custom TP2)</label>
                <Input
                  type="number" min="1" placeholder="20"
                  value={manualTp}
                  onChange={(e) => setManualTp(e.target.value)}
                  className="font-mono text-sm border-border bg-background"
                />
              </div>
            </div>

            {/* Row 3 — Price Targets Preview */}
            {hasCalc && (
              <div className="p-3 bg-muted/20 border border-border rounded-md space-y-2">
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">Targets Price Preview</div>
                <div className="grid grid-cols-2 gap-4 text-xs font-mono">
                  <div className="space-y-1 bg-green-500/5 p-2 rounded border border-green-500/10">
                    <div className="text-green-400 font-bold mb-1">BUY TARGETS:</div>
                    <div className="flex justify-between"><span>Stop Loss:</span> <span className="text-red-400 font-semibold">{buySlPrice}</span></div>
                    <div className="flex justify-between"><span>TP1 (1x Risk):</span> <span className="text-green-400 font-semibold">{buyTp1Price}</span></div>
                    <div className="flex justify-between"><span>TP2 (Custom):</span> <span className="text-green-400 font-semibold">{buyTp2Price}</span></div>
                    <div className="flex justify-between"><span>TP3 (3.5x Risk):</span> <span className="text-green-400 font-semibold">{buyTp3Price}</span></div>
                  </div>
                  <div className="space-y-1 bg-red-500/5 p-2 rounded border border-red-500/10">
                    <div className="text-red-400 font-bold mb-1">SELL TARGETS:</div>
                    <div className="flex justify-between"><span>Stop Loss:</span> <span className="text-red-400 font-semibold">{sellSlPrice}</span></div>
                    <div className="flex justify-between"><span>TP1 (1x Risk):</span> <span className="text-green-400 font-semibold">{sellTp1Price}</span></div>
                    <div className="flex justify-between"><span>TP2 (Custom):</span> <span className="text-green-400 font-semibold">{sellTp2Price}</span></div>
                    <div className="flex justify-between"><span>TP3 (3.5x Risk):</span> <span className="text-green-400 font-semibold">{sellTp3Price}</span></div>
                  </div>
                </div>
              </div>
            )}

            {/* BUY / SELL */}
            <div className="flex gap-3 pt-1">
              <Button
                onClick={() => handleManualTrade("BUY")}
                disabled={executeTrade.isPending || !botOnline}
                className="flex-1 bg-green-600 hover:bg-green-700 text-white font-mono text-sm font-bold"
              >
                <Send className="h-4 w-4 mr-2" />
                BUY {hasCalc && <span className="ml-2 font-normal text-green-200">@ {entryVal.toFixed(pricePrecision)}</span>}
              </Button>
              <Button
                onClick={() => handleManualTrade("SELL")}
                disabled={executeTrade.isPending || !botOnline}
                className="flex-1 bg-red-600 hover:bg-red-700 text-white font-mono text-sm font-bold"
              >
                <Send className="h-4 w-4 mr-2" />
                SELL {hasCalc && <span className="ml-2 font-normal text-red-200">@ {entryVal.toFixed(pricePrecision)}</span>}
              </Button>
            </div>
            {!botOnline && (
              <p className="text-xs text-amber-500">⚠ Bot offline — commands queue and execute when bot reconnects</p>
            )}
          </CardContent>
        </Card>

        {/* Active Positions */}
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="text-xs text-muted-foreground uppercase tracking-wider">Active Positions</CardTitle>
          </CardHeader>
          <CardContent>
            {activePositions.length === 0 ? (
              <div className="text-sm text-muted-foreground py-8 text-center border border-dashed border-border rounded">
                No active positions open
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow className="border-border hover:bg-transparent">
                    <TableHead className="font-mono text-xs">TICKET</TableHead>
                    <TableHead className="font-mono text-xs">SYMBOL</TableHead>
                    <TableHead className="font-mono text-xs">TYPE</TableHead>
                    <TableHead className="font-mono text-xs text-right">LOTS</TableHead>
                    <TableHead className="font-mono text-xs text-right">ENTRY</TableHead>
                    <TableHead className="font-mono text-xs text-right">CURRENT</TableHead>
                    <TableHead className="font-mono text-xs text-right">PROFIT</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {activePositions.map((pos) => (
                    <TableRow key={pos.ticket} className="border-border hover:bg-muted/30">
                      <TableCell className="font-mono text-xs text-muted-foreground">#{pos.ticket}</TableCell>
                      <TableCell className="font-mono font-medium">{pos.symbol}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className={cn(
                          "rounded-sm text-xs",
                          pos.type === "BUY"
                            ? "bg-green-500/10 text-green-500 border-green-500/30"
                            : "bg-red-500/10 text-red-500 border-red-500/30"
                        )}>
                          {pos.type}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-mono text-right">{pos.lots.toFixed(2)}</TableCell>
                      <TableCell className="font-mono text-right">{pos.entry.toFixed(5)}</TableCell>
                      <TableCell className="font-mono text-right">{pos.current?.toFixed(5) || "-"}</TableCell>
                      <TableCell className={cn(
                        "font-mono text-right font-bold",
                        pos.profit >= 0 ? "text-green-500" : "text-red-500"
                      )}>
                        {pos.profit > 0 ? "+" : ""}{pos.profit.toFixed(2)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
