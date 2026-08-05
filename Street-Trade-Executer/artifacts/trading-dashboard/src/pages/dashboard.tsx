import { useGetDashboard, useExecuteTrade, getGetDashboardQueryKey, useGetSignals, useGetConfig } from "@workspace/api-client-react";
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
import { useState, useEffect, useRef } from "react";
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

function MarketHoursCards() {
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 5000);
    return () => clearInterval(timer);
  }, []);

  const day = now.getUTCDay();
  const utcHours = now.getUTCHours();
  const utcMins = now.getUTCMinutes();
  const totalMins = utcHours * 60 + utcMins;

  // 1. Stocks: Mon-Fri, 13:30 - 20:00 UTC (9:30 AM - 4:00 PM EST / 6:30 PM - 1:00 AM PKT)
  const isStocksOpen = day >= 1 && day <= 5 && totalMins >= 810 && totalMins < 1200;

  // 2. Forex: Sun 22:00 UTC to Fri 22:00 UTC
  const isForexOpen = !(day === 6 || (day === 0 && totalMins < 1320) || (day === 5 && totalMins >= 1320));

  // 3. Metals: Sun 23:00 to Fri 22:00 UTC (Daily break 21:00-22:00 UTC / 2am-3am PKT)
  const isMetalBreak = totalMins >= 1260 && totalMins < 1320;
  const isMetalsOpen = isForexOpen && !isMetalBreak;

  // 4. Indices: Sun 23:00 to Fri 22:00 UTC (Break 20:15-20:30 & 21:00-22:00 UTC)
  const isIndexBreak = (totalMins >= 1215 && totalMins < 1230) || (totalMins >= 1260 && totalMins < 1320);
  const isIndicesOpen = isForexOpen && !isIndexBreak;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-2">
      {/* STOCKS CARD */}
      <div className="relative overflow-hidden rounded-xl border border-purple-500/30 bg-gradient-to-br from-indigo-950/40 via-purple-950/30 to-zinc-950 p-4 transition-all duration-300 hover:border-purple-500/60 hover:shadow-[0_0_20px_rgba(168,85,247,0.15)]">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <span className="text-2xl p-2 rounded-lg bg-purple-500/10 border border-purple-500/20">🇺🇸</span>
            <div>
              <div className="font-semibold text-sm text-zinc-100 font-sans">US Stock Exchanges</div>
              <div className="text-[11px] text-purple-300/70 font-mono">NYSE & NASDAQ (AAPL, NVDA, AMZN)</div>
            </div>
          </div>
          <span className={cn("px-2.5 py-1 rounded-full text-[10px] font-extrabold uppercase tracking-wider border", isStocksOpen ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/40 shadow-[0_0_12px_rgba(52,211,153,0.3)] animate-pulse" : "bg-rose-500/20 text-rose-400 border-rose-500/40")}>
            {isStocksOpen ? "LIVE OPEN 🟢" : "MARKET CLOSED 🔴"}
          </span>
        </div>
        <div className="grid grid-cols-2 gap-2 bg-zinc-900/60 border border-zinc-800/60 rounded-lg p-2.5 mb-2 font-mono text-[11px]">
          <div>
            <div className="text-[10px] text-zinc-500 uppercase font-semibold">Opening</div>
            <div className="text-zinc-200 font-bold mt-0.5">6:30 PM PKT</div>
            <div className="text-[9px] text-zinc-500">9:30 AM EST</div>
          </div>
          <div>
            <div className="text-[10px] text-zinc-500 uppercase font-semibold">Closing</div>
            <div className="text-zinc-200 font-bold mt-0.5">1:00 AM PKT</div>
            <div className="text-[9px] text-zinc-500">4:00 PM EST</div>
          </div>
        </div>
        <div className="text-[11px] text-zinc-400 flex items-center gap-1.5 font-sans">
          <span>🗓️ Mon - Fri • 6.5 Hours Regular Session</span>
        </div>
      </div>

      {/* FOREX CARD */}
      <div className="relative overflow-hidden rounded-xl border border-sky-500/30 bg-gradient-to-br from-cyan-950/40 via-sky-950/30 to-zinc-950 p-4 transition-all duration-300 hover:border-sky-500/60 hover:shadow-[0_0_20px_rgba(56,189,248,0.15)]">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <span className="text-2xl p-2 rounded-lg bg-sky-500/10 border border-sky-500/20">💱</span>
            <div>
              <div className="font-semibold text-sm text-zinc-100 font-sans">Global Forex Market</div>
              <div className="text-[11px] text-sky-300/70 font-mono">Currencies (EUR, USD, GBP, JPY)</div>
            </div>
          </div>
          <span className={cn("px-2.5 py-1 rounded-full text-[10px] font-extrabold uppercase tracking-wider border", isForexOpen ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/40 shadow-[0_0_12px_rgba(52,211,153,0.3)] animate-pulse" : "bg-rose-500/20 text-rose-400 border-rose-500/40")}>
            {isForexOpen ? "LIVE OPEN 🟢" : "MARKET CLOSED 🔴"}
          </span>
        </div>
        <div className="grid grid-cols-2 gap-2 bg-zinc-900/60 border border-zinc-800/60 rounded-lg p-2 mb-2 font-mono text-[11px]">
          <div>
            <div className="text-[9px] text-zinc-500 uppercase font-semibold">Weekly Open</div>
            <div className="text-zinc-200 font-bold mt-0.5">2:00 AM PKT Mon</div>
          </div>
          <div>
            <div className="text-[9px] text-zinc-500 uppercase font-semibold">Weekly Close</div>
            <div className="text-zinc-200 font-bold mt-0.5">2:00 AM PKT Sat</div>
          </div>
        </div>

        {/* 4 Global Sessions Grid */}
        <div className="bg-zinc-950/60 border border-sky-500/20 rounded-lg p-2 mb-2">
          <div className="text-[9px] uppercase font-bold text-sky-400 mb-1 flex justify-between">
            <span>4 Global Sessions (PKT)</span>
            <span>24/5 Live</span>
          </div>
          <div className="grid grid-cols-2 gap-1.5 font-mono text-[10px]">
            <div className="bg-zinc-900/80 p-1 px-1.5 rounded flex justify-between items-center border border-zinc-800/50">
              <span className="text-zinc-300">🇦🇺 Sydney</span>
              <span className="text-zinc-500 text-[9px]">2am - 11am</span>
            </div>
            <div className="bg-zinc-900/80 p-1 px-1.5 rounded flex justify-between items-center border border-zinc-800/50">
              <span className="text-zinc-300">🇯🇵 Tokyo</span>
              <span className="text-zinc-500 text-[9px]">5am - 2pm</span>
            </div>
            <div className="bg-zinc-900/80 p-1 px-1.5 rounded flex justify-between items-center border border-zinc-800/50">
              <span className="text-zinc-300">🇬🇧 London</span>
              <span className="text-zinc-500 text-[9px]">1pm - 10pm</span>
            </div>
            <div className="bg-zinc-900/80 p-1 px-1.5 rounded flex justify-between items-center border border-zinc-800/50">
              <span className="text-zinc-300">🇺🇸 New York</span>
              <span className="text-zinc-500 text-[9px]">6pm - 3am</span>
            </div>
          </div>
        </div>

        <div className="text-[11px] text-zinc-400 flex items-center gap-1.5 font-sans">
          <span>🌍 24/5 Continuous • Sydney / Tokyo / London / NY</span>
        </div>
      </div>

      {/* METALS CARD */}
      <div className="relative overflow-hidden rounded-xl border border-amber-500/30 bg-gradient-to-br from-amber-950/40 via-yellow-950/30 to-zinc-950 p-4 transition-all duration-300 hover:border-amber-500/60 hover:shadow-[0_0_20px_rgba(245,158,11,0.15)]">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <span className="text-2xl p-2 rounded-lg bg-amber-500/10 border border-amber-500/20">🥇</span>
            <div>
              <div className="font-semibold text-sm text-zinc-100 font-sans">Precious Metals</div>
              <div className="text-[11px] text-amber-300/70 font-mono">Commodities (XAU/Gold, XAG, XPT)</div>
            </div>
          </div>
          <span className={cn("px-2.5 py-1 rounded-full text-[10px] font-extrabold uppercase tracking-wider border", isMetalsOpen ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/40 shadow-[0_0_12px_rgba(52,211,153,0.3)] animate-pulse" : isMetalBreak ? "bg-amber-500/20 text-amber-400 border-amber-500/40" : "bg-rose-500/20 text-rose-400 border-rose-500/40")}>
            {isMetalsOpen ? "LIVE OPEN 🟢" : isMetalBreak ? "DAILY BREAK ⏸" : "MARKET CLOSED 🔴"}
          </span>
        </div>
        <div className="grid grid-cols-2 gap-2 bg-zinc-900/60 border border-zinc-800/60 rounded-lg p-2.5 mb-2 font-mono text-[11px]">
          <div>
            <div className="text-[10px] text-zinc-500 uppercase font-semibold">Opening</div>
            <div className="text-zinc-200 font-bold mt-0.5">3:00 AM PKT</div>
            <div className="text-[9px] text-zinc-500">6:00 PM EST Sun</div>
          </div>
          <div>
            <div className="text-[10px] text-zinc-500 uppercase font-semibold">Closing / Break</div>
            <div className="text-zinc-200 font-bold mt-0.5">2:00 AM PKT</div>
            <div className="text-[9px] text-zinc-500">Daily Break 2am-3am</div>
          </div>
        </div>
        <div className="text-[11px] text-zinc-400 flex items-center gap-1.5 font-sans">
          <span>⏱️ 23 Hours / Day • Daily 1-Hour Maintenance</span>
        </div>
      </div>

      {/* INDICES CARD */}
      <div className="relative overflow-hidden rounded-xl border border-emerald-500/30 bg-gradient-to-br from-emerald-950/40 via-teal-950/30 to-zinc-950 p-4 transition-all duration-300 hover:border-emerald-500/60 hover:shadow-[0_0_20px_rgba(16,185,129,0.15)]">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <span className="text-2xl p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20">📊</span>
            <div>
              <div className="font-semibold text-sm text-zinc-100 font-sans">Stock Indices</div>
              <div className="text-[11px] text-emerald-300/70 font-mono">Futures (US500, US30, USTEC)</div>
            </div>
          </div>
          <span className={cn("px-2.5 py-1 rounded-full text-[10px] font-extrabold uppercase tracking-wider border", isIndicesOpen ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/40 shadow-[0_0_12px_rgba(52,211,153,0.3)] animate-pulse" : isIndexBreak ? "bg-amber-500/20 text-amber-400 border-amber-500/40" : "bg-rose-500/20 text-rose-400 border-rose-500/40")}>
            {isIndicesOpen ? "LIVE OPEN 🟢" : isIndexBreak ? "DAILY BREAK ⏸" : "MARKET CLOSED 🔴"}
          </span>
        </div>
        <div className="grid grid-cols-2 gap-2 bg-zinc-900/60 border border-zinc-800/60 rounded-lg p-2.5 mb-2 font-mono text-[11px]">
          <div>
            <div className="text-[10px] text-zinc-500 uppercase font-semibold">Opening</div>
            <div className="text-zinc-200 font-bold mt-0.5">3:00 AM PKT</div>
            <div className="text-[9px] text-zinc-500">6:00 PM EST Sun</div>
          </div>
          <div>
            <div className="text-[10px] text-zinc-500 uppercase font-semibold">Closing</div>
            <div className="text-zinc-200 font-bold mt-0.5">2:15 AM PKT</div>
            <div className="text-[9px] text-zinc-500">Break 2:15am-3am</div>
          </div>
        </div>
        <div className="text-[11px] text-zinc-400 flex items-center gap-1.5 font-sans">
          <span>⚡ 23 Hours / Day • Brief Daily Maint. Break</span>
        </div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { toast } = useToast();
  const isReadOnly = localStorage.getItem("wasee_role")?.toLowerCase() === "user";
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
    if (["XAU", "XPT", "XPD", "PLAT", "PALL"].some(x => s.includes(x))) return 1.0;
    if (s.includes("XAG")) return 0.1;
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
      refetchInterval: 2000,
      queryKey: getGetDashboardQueryKey(),
    },
  });

  const { data: config } = useGetConfig();

  useEffect(() => {
    if (config) {
      if (config.defaultLots !== undefined) {
        setManualLots(config.defaultLots.toString());
      }
      if (config.slPips !== undefined) {
        setManualSl(config.slPips.toString());
      }
      if (config.tpPips !== undefined) {
        setManualTp(config.tpPips.toString());
      }
    }
  }, [config]);

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
  const { data: signalsData } = useGetSignals({ limit: 50 });

  const dashboard = wsData ?? httpData;

  if (isLoading && !dashboard) {
    return (
      <div className="p-6 space-y-6">
        <Skeleton className="h-[48px] w-full" />
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-[120px] w-full" />)}
        </div>
      </div>
    );
  }

  if (!dashboard) return null;

  const recentSymbolSignals = signalsData?.filter(
    (s: any) => s.symbolA.toUpperCase().includes(selectedChartSymbol.toUpperCase()) || s.symbolB.toUpperCase().includes(selectedChartSymbol.toUpperCase())
  ) ?? [];

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
    initialBalance = 100000.00,
    overallDrawdown = 0.00,
    maxEquityPeak = 0.00,
    mt5Login = 0,
  } = dashboard;

  const overallGain = equity - (initialBalance ?? 100000.00);
  const overallGainPercent = (initialBalance ?? 100000.00) > 0 ? (overallGain / (initialBalance ?? 100000.00)) * 100 : 0;

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

  const handleOneClickExecute = (symbolPair: string, action: string) => {
    const parts = symbolPair.split("/");
    if (parts.length !== 2) return;
    
    const [symA, symB] = parts;
    const isBuy = action === "BUY_SPREAD";
    
    const dirA = isBuy ? "BUY" : "SELL";
    const dirB = isBuy ? "SELL" : "BUY";
    
    const slPips = parseFloat(manualSl);
    const tpPips = parseFloat(manualTp);
    const lots = parseFloat(manualLots);
    
    if (isNaN(lots) || lots <= 0) {
      toast({ title: "Lots required", description: "Set a valid Lot size in the input field first.", variant: "destructive" });
      return;
    }
    
    const ts = Date.now();
    const commentA = `JS_HEDGE_MANUAL_LEGA_${ts}`;
    const commentB = `JS_HEDGE_MANUAL_LEGB_${ts}`;
    
    executeTrade.mutate(
      { data: { symbol: symA, direction: dirA, lots, slPips: isNaN(slPips) ? undefined : slPips, tpPips: isNaN(tpPips) ? undefined : tpPips, comment: commentA } },
      {
        onSuccess: () => {
          executeTrade.mutate(
            { data: { symbol: symB, direction: dirB, lots, slPips: isNaN(slPips) ? undefined : slPips, tpPips: isNaN(tpPips) ? undefined : tpPips, comment: commentB } },
            {
              onSuccess: () => {
                toast({
                  title: "🚀 One-Click Spread Executed",
                  description: `Queued: 3 Leg A (${symA}) + 1 Leg B (${symB}) orders successfully!`,
                });
                queryClient.invalidateQueries({ queryKey: getGetDashboardQueryKey() });
              },
              onError: () => {
                toast({ title: `Failed to queue second leg ${symB}`, variant: "destructive" });
              }
            }
          );
        },
        onError: () => {
          toast({ title: `Failed to queue first leg ${symA}`, variant: "destructive" });
        }
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
            
            <span className={cn("px-1.5 py-0.5 rounded-sm text-[10px] font-bold border transition-all duration-300", dashboard.metalsEnabled ? "bg-amber-500/10 text-amber-400 border-amber-500/30 shadow-[0_0_10px_rgba(245,158,11,0.15)]" : "text-zinc-600 border-zinc-800 bg-zinc-900/20 opacity-50")}>Metals</span>
            <span className={cn("px-1.5 py-0.5 rounded-sm text-[10px] font-bold border transition-all duration-300", dashboard.forexEnabled ? "bg-cyan-500/10 text-cyan-400 border-cyan-500/30 shadow-[0_0_10px_rgba(6,182,212,0.15)]" : "text-zinc-600 border-zinc-800 bg-zinc-900/20 opacity-50")}>Forex</span>
            <span className={cn("px-1.5 py-0.5 rounded-sm text-[10px] font-bold border transition-all duration-300", dashboard.indicesEnabled ? "bg-blue-500/10 text-blue-400 border-blue-500/30 shadow-[0_0_10px_rgba(59,130,246,0.15)]" : "text-zinc-600 border-zinc-800 bg-zinc-900/20 opacity-50")}>Indices</span>
            <span className={cn("px-1.5 py-0.5 rounded-sm text-[10px] font-bold border transition-all duration-300", (dashboard as any).stocksEnabled !== false ? "bg-purple-500/10 text-purple-400 border-purple-500/30 shadow-[0_0_10px_rgba(168,85,247,0.15)]" : "text-zinc-600 border-zinc-800 bg-zinc-900/20 opacity-50")}>Stocks</span>
          </div>
          <div className="font-mono bg-zinc-900/70 border border-zinc-800 px-2 py-0.5 rounded text-[11px] text-zinc-400 shadow-[0_0_8px_rgba(255,255,255,0.02)]">
            TARGET LEG: <span className="font-bold text-zinc-100">{currentPair}</span>
          </div>
          <Button
            onClick={() => {
              if (window.confirm("ARE YOU SURE YOU WANT TO EMERGENCY CLOSE ALL MT5 POSITIONS?")) {
                executeTrade.mutate(
                  { data: { symbol: "ALL", direction: "CLOSE", lots: 0.0, comment: "CLOSE_ALL" } },
                  {
                    onSuccess: () => {
                      toast({ title: "Emergency Close All triggered", description: "Sent CLOSE ALL command to MT5 bot" });
                    },
                    onError: () => {
                      toast({ title: "Failed to trigger close command", variant: "destructive" });
                    }
                  }
                );
              }
            }}
            size="sm"
            variant="destructive"
            className="bg-red-600 hover:bg-red-500 text-white font-mono text-[10px] font-bold h-6 px-2 shadow-[0_0_12px_rgba(239,68,68,0.25)] rounded border border-red-500/30 ml-2"
            disabled={executeTrade.isPending || !botOnline || isReadOnly}
          >
            🚨 CLOSE ALL
          </Button>
        </div>
      </div>

      <div className="p-6 space-y-6">
        {/* High-Impact News Protection Card */}
        <Card className={cn(
          "bg-zinc-900 border transition-all rounded-md p-4",
          systemStatus.includes("HALTED (News")
            ? "border-red-500/60 bg-red-950/20 text-red-400"
            : "border-emerald-500/40 bg-zinc-900/80 text-zinc-100"
        )}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-xl">📰</span>
              <div>
                <div className="font-bold text-sm text-zinc-100">High-Impact News Protection (15-Min Buffer)</div>
                <div className="text-xs text-zinc-400">Real-time safeguard against NFP, CPI, FOMC volatility</div>
              </div>
            </div>
            <span className={cn(
              "px-2.5 py-1 rounded text-xs font-bold border",
              systemStatus.includes("HALTED (News")
                ? "bg-red-500/20 text-red-400 border-red-500/40 animate-pulse"
                : "bg-emerald-500/20 text-emerald-400 border-emerald-500/40"
            )}>
              {systemStatus.includes("HALTED (News") ? "🔴 TRADING HALTED (15-MIN NEWS BUFFER)" : "🟢 NORMAL TRADING ACTIVE"}
            </span>
          </div>
          <div className="mt-3 p-2.5 rounded bg-zinc-950/60 border border-zinc-800 text-xs text-zinc-300">
            {systemStatus.includes("HALTED (News") ? (
              <span>⚠️ <strong>HIGH-IMPACT NEWS DETECTED:</strong> {systemStatus.replace("HALTED (News: ", "").replace(")", "")} — New entries blocked for capital safety.</span>
            ) : (
              <span>✨ <strong>Normal Trading Status:</strong> No high-impact news within 15-minute window. Signals active to 50 TP targets.</span>
            )}
          </div>
        </Card>

        {/* Equity Trailing Stop Guard Card */}
        {(() => {
          const isTrailActiveText = systemStatus && systemStatus.includes("Trail Active");
          const isTier2 = floatingProfit >= 100.0 || (isTrailActiveText && systemStatus.includes("Tier 2"));
          const isTier1 = floatingProfit >= 75.0 || isTrailActiveText;
          return (
            <Card className={cn(
              "bg-zinc-900 border transition-all rounded-md p-4",
              isTier2
                ? "border-emerald-500/60 bg-emerald-950/20 text-emerald-400"
                : isTier1
                ? "border-blue-500/60 bg-blue-950/20 text-blue-400"
                : "border-zinc-800 bg-zinc-900/80 text-zinc-100"
            )}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-xl">🛡️</span>
                  <div>
                    <div className="font-bold text-sm text-zinc-100">Multi-Tier Equity Profit Lock Guard (Dual Tier)</div>
                    <div className="text-xs text-zinc-400">Tier 1 (+ $75 peak locks + $69) | Tier 2 (+ $100+ peak locks 91%)</div>
                  </div>
                </div>
                <span className={cn(
                  "px-2.5 py-1 rounded text-xs font-bold border",
                  isTier2
                    ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/40 animate-pulse"
                    : isTier1
                    ? "bg-blue-500/20 text-blue-400 border-blue-500/40"
                    : "bg-zinc-800 text-zinc-400 border-zinc-700"
                )}>
                  {isTier2 ? "🟢 TIER 2 TRAILING ACTIVE (91% LOCK)" : isTier1 ? "🔵 TIER 1 SAFETY FLOOR (+$69 LOCK)" : "⚪ TRAILING STOP INACTIVE"}
                </span>
              </div>
              <div className="mt-3 p-2.5 rounded bg-zinc-950/60 border border-zinc-800 text-xs text-zinc-300">
                {isTier2 ? (
                  <span>🛡️ <strong>TIER 2 PROFIT LOCK ACTIVE:</strong> Peak Profit: <strong>+${Math.max(floatingProfit, 100.0).toFixed(2)}</strong> | Locked Floor (91%): <strong>+${(Math.max(floatingProfit, 100.0) * 0.91).toFixed(2)}</strong> — Position is locking 91% of peak earnings!</span>
                ) : isTier1 ? (
                  <span>🛡️ <strong>TIER 1 SAFETY FLOOR ACTIVE:</strong> Peak Profit: <strong>+${Math.max(floatingProfit, 75.0).toFixed(2)}</strong> | Safety Floor: <strong>+$69.00</strong> — If market reverses from $75–$99, bot will auto-close at +$69.00+ to lock first target profit!</span>
                ) : (
                  <span>⚪ <strong>Multi-Tier Mode:</strong> Reversing from $75–$99 locks +$69.00+ cash profit! Reaching +$100+ locks 91% of peak earnings! (Current Floating: {floatingProfit >= 0 ? "+" : ""}${floatingProfit.toFixed(2)})</span>
                )}
              </div>
            </Card>
          );
        })()}

        {/* Global Market Operating Hours Cards */}
        <MarketHoursCards />

        {/* Key Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <Card className="bg-zinc-900 border-zinc-800 border-t-2 border-t-sky-500 hover:border-sky-400/40 transition-all shadow-[0_4px_24px_rgba(14,165,233,0.06)] rounded-md">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs text-zinc-500 uppercase tracking-wider font-mono flex items-center justify-between">
                <span>Account Equity</span>
                {mt5Login > 0 && <span className="text-[9px] text-zinc-500 font-mono">ID: {mt5Login}</span>}
              </CardTitle>
            </CardHeader>
            <CardContent className="pb-2">
              <div className="text-2xl font-mono text-sky-400 font-bold">{formatMoney(equity)}</div>
              <div className="text-[10px] text-zinc-500 mt-1 mb-2 font-mono">
                Start: <span className="text-zinc-300">{formatMoney(initialBalance)}</span>
              </div>
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

          <Card className={cn("bg-zinc-900 border-zinc-800 border-t-2 transition-all rounded-md", 
            drawdownPercent < 0 
              ? "border-t-emerald-500 hover:border-emerald-400/40 shadow-[0_4px_24px_rgba(16,185,129,0.06)]" 
              : "border-t-amber-500 hover:border-amber-400/40 shadow-[0_4px_24px_rgba(245,158,11,0.06)]"
          )}>
            <CardHeader className="pb-2">
              <CardTitle className="text-xs text-zinc-500 uppercase tracking-wider font-mono">
                {drawdownPercent < 0 ? "Daily Gain" : "Daily Drawdown"}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex justify-between items-end">
                <div className={cn("text-2xl font-mono", drawdownPercent < 0 ? "text-emerald-400" : "text-amber-400")}>
                  {drawdownPercent < 0 ? "+" : ""}{Math.abs(drawdownPercent).toFixed(2)}%
                </div>
                <div className="text-[10px] text-zinc-500 mb-1 font-mono">
                  Halt: <span className="text-amber-500">3.2%</span> · Limit: <span className="text-red-500">4%</span>
                </div>
              </div>
              <Progress 
                value={drawdownPercent < 0 ? 0 : Math.min((drawdownPercent / 4) * 100, 100)} 
                className="h-1.5 bg-zinc-800 [&>div]:bg-rose-500" 
              />
            </CardContent>
          </Card>

          <Card className="bg-zinc-900 border-zinc-800 border-t-2 border-t-emerald-500 hover:border-emerald-400/40 transition-all shadow-[0_4px_24px_rgba(16,185,129,0.06)] rounded-md">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs text-zinc-500 uppercase tracking-wider font-mono">Overall Gain</CardTitle>
            </CardHeader>
            <CardContent>
              <div className={cn("text-2xl font-mono font-bold", overallGain >= 0 ? "text-emerald-400" : "text-rose-400")}>
                {overallGain >= 0 ? "+" : ""}{formatMoney(overallGain)}
              </div>
              <div className="text-[10px] text-zinc-500 mt-1 font-mono">
                Gain %: <span className={overallGain >= 0 ? "text-emerald-400" : "text-rose-400"}>{overallGainPercent.toFixed(2)}%</span>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-zinc-900 border-zinc-800 border-t-2 border-t-rose-500 hover:border-rose-400/40 transition-all shadow-[0_4px_24px_rgba(244,63,94,0.06)] rounded-md">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs text-zinc-500 uppercase tracking-wider font-mono">Overall Drawdown</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex justify-between items-end">
                <div className="text-2xl font-mono text-rose-400">{overallDrawdown.toFixed(2)}%</div>
                <div className="text-[10px] text-zinc-500 mb-1 font-mono">
                  Peak: <span className="text-zinc-300">{formatMoney(maxEquityPeak)}</span>
                </div>
              </div>
              <Progress value={Math.min((overallDrawdown / 10) * 100, 100)} className="h-1.5 bg-zinc-800 [&>div]:bg-rose-500" />
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
            <CardContent className="space-y-4">
              <TradingViewWidget symbol={selectedChartSymbol} />
              
              {/* Signals Timeline for selected symbol */}
              <div className="p-3 bg-zinc-950 border border-zinc-900 rounded-md">
                <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-mono mb-2">Recent Execution Signals ({selectedChartSymbol})</div>
                {recentSymbolSignals.length === 0 ? (
                  <div className="text-xs text-zinc-500 italic font-mono">No recent signals recorded for {selectedChartSymbol}</div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                    {recentSymbolSignals.slice(0, 3).map((sig: any) => {
                      const isBuy = sig.action === "BUY_SPREAD";
                      const dateStr = new Date(sig.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
                      return (
                        <div key={sig.id} className={cn(
                          "flex items-center justify-between p-2 rounded-sm border text-xs font-mono",
                          isBuy 
                            ? "bg-emerald-500/5 border-emerald-500/20 text-emerald-400" 
                            : "bg-rose-500/5 border-rose-500/20 text-rose-400"
                        )}>
                          <div className="flex items-center gap-1.5">
                            <span className={cn(
                              "h-1.5 w-1.5 rounded-full",
                              isBuy ? "bg-emerald-400 animate-pulse" : "bg-rose-400 animate-pulse"
                            )} />
                            <span className="font-bold">{isBuy ? "BUY" : "SELL"}</span>
                          </div>
                          <span>Z: {sig.zScore.toFixed(2)}</span>
                          <span className="text-[10px] text-zinc-500">{dateStr}</span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
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

              {/* One-Click Execute Button for manual spread entry */}
              {selectedAssetAction !== "NONE" && !hasActivePosition && (
                <Button
                  onClick={() => handleOneClickExecute(matchingAsset ? matchingAsset.symbolPair : selectedChartSymbol, selectedAssetAction)}
                  className="w-full bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-mono font-bold shadow-[0_0_15px_rgba(16,185,129,0.25)] animate-pulse rounded-md py-4 text-xs"
                  disabled={executeTrade.isPending || !botOnline || isReadOnly}
                >
                  🚀 ONE-CLICK EXECUTE {selectedAssetAction.replace("_SPREAD", "")}
                </Button>
              )}

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
                Bot scans enabled Forex, Metals, and Stocks/Indices. Selects the highest win rate symbol with an active signal.
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
                    <TableHead className="font-mono text-xs text-center">ACTION</TableHead>
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
                      <TableCell className="text-center">
                        {asset.action !== "NONE" && (
                          <Button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleOneClickExecute(asset.symbolPair, asset.action);
                            }}
                            size="sm"
                            className="bg-emerald-600 hover:bg-emerald-500 text-white font-mono text-[10px] font-bold h-7 px-2"
                            disabled={executeTrade.isPending || !botOnline || isReadOnly}
                          >
                            ⚡ EXECUTE
                          </Button>
                        )}
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
                disabled={executeTrade.isPending || !botOnline || isReadOnly}
                className="flex-1 bg-green-600 hover:bg-green-700 text-white font-mono text-sm font-bold"
              >
                <Send className="h-4 w-4 mr-2" />
                BUY {hasCalc && <span className="ml-2 font-normal text-green-200">@ {entryVal.toFixed(pricePrecision)}</span>}
              </Button>
              <Button
                onClick={() => handleManualTrade("SELL")}
                disabled={executeTrade.isPending || !botOnline || isReadOnly}
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
                    <TableHead className="font-mono text-xs text-center">ACTION</TableHead>
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
                      <TableCell className="text-center">
                        <Button
                          onClick={(e) => {
                            e.stopPropagation();
                            executeTrade.mutate(
                              { data: { symbol: pos.symbol, direction: "CLOSE", lots: pos.lots, comment: `CLOSE_${pos.ticket}` } },
                              {
                                onSuccess: () => {
                                  toast({ title: "Close command queued", description: `Queued exit for Ticket #${pos.ticket}` });
                                },
                                onError: () => {
                                  toast({ title: "Failed to queue exit", variant: "destructive" });
                                }
                              }
                            );
                          }}
                          size="sm"
                          variant="destructive"
                          className="h-7 px-2 font-mono text-[10px] uppercase font-bold"
                          disabled={executeTrade.isPending || !botOnline || isReadOnly}
                        >
                          Emergency Close
                        </Button>
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
