import { useGetDashboard, useExecuteTrade, getGetDashboardQueryKey, useGetSignals, useGetConfig } from "@workspace/api-client-react";
import { useLiveDashboard } from "@/hooks/use-ws";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn, formatPktTime } from "@/lib/utils";
import { Activity, Wifi, WifiOff, Send, Zap, ZapOff, Power, PowerOff, ShieldCheck, ChevronDown, Plus, RefreshCw, UserCheck, AlertTriangle } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { useState, useEffect, useRef, useMemo } from "react";
import { AreaChart, Area, ResponsiveContainer } from "recharts";
import { useToast } from "@/hooks/use-toast";
import { useQueryClient } from "@tanstack/react-query";
import { SmcChartOverlay } from "@/components/SmcChartOverlay";
import { SessionGuardCard } from "@/components/SessionGuardCard";

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
      if (["NAS100", "USTEC", "US100", "NDX", "NQ100"].includes(s)) return "OANDA:NAS100USD";
      if (["US30", "DJ30", "WS30", "DOW30", "DJI"].includes(s)) return "OANDA:US30USD";
      return `FX:${s}`;
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
      <div className="relative overflow-hidden rounded-xl border border-purple-500/30 bg-gradient-to-br from-indigo-950/40 via-purple-950/30 to-zinc-950 p-3.5 sm:p-4 transition-all duration-300 hover:border-purple-500/60 hover:shadow-[0_0_20px_rgba(168,85,247,0.15)]">
        <div className="flex flex-wrap items-start justify-between gap-2 mb-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <span className="text-xl sm:text-2xl p-1.5 sm:p-2 rounded-lg bg-purple-500/10 border border-purple-500/20 shrink-0">🇺🇸</span>
            <div className="min-w-0">
              <div className="font-semibold text-sm text-zinc-100 font-sans truncate">US Stock Exchanges</div>
              <div className="text-[11px] text-purple-300/70 font-mono truncate">NYSE & NASDAQ (AAPL, NVDA, AMZN)</div>
            </div>
          </div>
          <span className={cn("shrink-0 whitespace-nowrap px-2.5 py-1 rounded-full text-[10px] font-extrabold uppercase tracking-wider border", isStocksOpen ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/40 shadow-[0_0_12px_rgba(52,211,153,0.3)] animate-pulse" : "bg-rose-500/20 text-rose-400 border-rose-500/40")}>
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
      <div className="relative overflow-hidden rounded-xl border border-sky-500/30 bg-gradient-to-br from-cyan-950/40 via-sky-950/30 to-zinc-950 p-3.5 sm:p-4 transition-all duration-300 hover:border-sky-500/60 hover:shadow-[0_0_20px_rgba(56,189,248,0.15)]">
        <div className="flex flex-wrap items-start justify-between gap-2 mb-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <span className="text-xl sm:text-2xl p-1.5 sm:p-2 rounded-lg bg-sky-500/10 border border-sky-500/20 shrink-0">💱</span>
            <div className="min-w-0">
              <div className="font-semibold text-sm text-zinc-100 font-sans truncate">Global Forex Market</div>
              <div className="text-[11px] text-sky-300/70 font-mono truncate">Currencies (EUR, USD, GBP, JPY)</div>
            </div>
          </div>
          <span className={cn("shrink-0 whitespace-nowrap px-2.5 py-1 rounded-full text-[10px] font-extrabold uppercase tracking-wider border", isForexOpen ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/40 shadow-[0_0_12px_rgba(52,211,153,0.3)] animate-pulse" : "bg-rose-500/20 text-rose-400 border-rose-500/40")}>
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
      <div className="relative overflow-hidden rounded-xl border border-amber-500/30 bg-gradient-to-br from-amber-950/40 via-yellow-950/30 to-zinc-950 p-3.5 sm:p-4 transition-all duration-300 hover:border-amber-500/60 hover:shadow-[0_0_20px_rgba(245,158,11,0.15)]">
        <div className="flex flex-wrap items-start justify-between gap-2 mb-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <span className="text-xl sm:text-2xl p-1.5 sm:p-2 rounded-lg bg-amber-500/10 border border-amber-500/20 shrink-0">🥇</span>
            <div className="min-w-0">
              <div className="font-semibold text-sm text-zinc-100 font-sans truncate">Precious Metals</div>
              <div className="text-[11px] text-amber-300/70 font-mono truncate">Commodities (XAU/Gold, XAG, XPT)</div>
            </div>
          </div>
          <span className={cn("shrink-0 whitespace-nowrap px-2.5 py-1 rounded-full text-[10px] font-extrabold uppercase tracking-wider border", isMetalsOpen ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/40 shadow-[0_0_12px_rgba(52,211,153,0.3)] animate-pulse" : isMetalBreak ? "bg-amber-500/20 text-amber-400 border-amber-500/40" : "bg-rose-500/20 text-rose-400 border-rose-500/40")}>
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
      <div className="relative overflow-hidden rounded-xl border border-emerald-500/30 bg-gradient-to-br from-emerald-950/40 via-teal-950/30 to-zinc-950 p-3.5 sm:p-4 transition-all duration-300 hover:border-emerald-500/60 hover:shadow-[0_0_20px_rgba(16,185,129,0.15)]">
        <div className="flex flex-wrap items-start justify-between gap-2 mb-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <span className="text-xl sm:text-2xl p-1.5 sm:p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 shrink-0">📊</span>
            <div className="min-w-0">
              <div className="font-semibold text-sm text-zinc-100 font-sans truncate">Stock Indices</div>
              <div className="text-[11px] text-emerald-300/70 font-mono truncate">US Indices (US30, NAS100)</div>
            </div>
          </div>
          <span className={cn("shrink-0 whitespace-nowrap px-2.5 py-1 rounded-full text-[10px] font-extrabold uppercase tracking-wider border", isIndicesOpen ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/40 shadow-[0_0_12px_rgba(52,211,153,0.3)] animate-pulse" : isIndexBreak ? "bg-amber-500/20 text-amber-400 border-amber-500/40" : "bg-rose-500/20 text-rose-400 border-rose-500/40")}>
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

  // Remote Bot Control & MT5 Account Switcher States
  const [isAccountModalOpen, setIsAccountModalOpen] = useState(false);
  const [accountsList, setAccountsList] = useState<any[]>([]);
  const [isLoadingAccounts, setIsLoadingAccounts] = useState(false);
  const [isSwitchingAccount, setIsSwitchingAccount] = useState(false);
  const [isTogglingBot, setIsTogglingBot] = useState(false);
  const [newLogin, setNewLogin] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newServer, setNewServer] = useState("");
  const [newName, setNewName] = useState("");
  const [newType, setNewType] = useState<"REAL" | "DEMO">("REAL");
  const [showAddForm, setShowAddForm] = useState(false);

  const fetchAccounts = async () => {
    try {
      setIsLoadingAccounts(true);
      const res = await fetch("/api/mt5/accounts");
      if (res.ok) {
        const data = await res.json();
        setAccountsList(data.accounts || []);
      }
    } catch (e) {
      console.error("Error fetching MT5 accounts:", e);
    } finally {
      setIsLoadingAccounts(false);
    }
  };

  useEffect(() => {
    fetchAccounts();
    const interval = setInterval(fetchAccounts, 10000);
    return () => clearInterval(interval);
  }, []);

  const getPipSize = (sym: string): number => {
    const s = sym.toUpperCase();
    if (s.includes("JPY")) return 0.01;
    if (["XAU", "XPT", "XPD", "PLAT", "PALL"].some(x => s.includes(x))) return 1.0;
    if (s.includes("XAG")) return 0.1;
    if (s.includes("BTC")) return 1.0;
    if (s.includes("ETH")) return 0.1;
    if (s.includes("SOL") || s.includes("BNB") || s.includes("AVAX")) return 0.01;
    if (s.includes("XRP") || s.includes("ADA") || s.includes("DOGE") || s.includes("MATIC")) return 0.0001;
    if (["US500", "US30", "DJ30", "WS30", "DOW", "NAS100", "USTEC", "US100", "GER30", "UK100", "SPX", "DJI", "NDX"].some(x => s.includes(x))) return 1.0;
    if (["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMD", "META", "AMZN"].some(x => s.includes(x))) return 0.1;
    return 0.0001;
  };

  const formatAssetPrice = (price: any, sym: string) => {
    const s = (sym || "").toUpperCase();
    const digits = ["XAU", "GOLD", "XAG", "SILVER", "US30", "DJ30", "WS30", "DOW", "NAS100", "USTEC", "US100", "NDX", "US500", "SPX", "GER30", "UK100"].some((k) => s.includes(k))
      ? 2
      : s.includes("JPY")
      ? 3
      : 5;
    return Number(price || 0).toFixed(digits);
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
  const [smcTelemetry, setSmcTelemetry] = useState<any>(null);
  const [chartViewMode, setChartViewMode] = useState<"smc" | "tv">("tv");

  useEffect(() => {
    let active = true;
    const fetchSmcData = async () => {
      try {
        const pair = selectedChartSymbol || "XAUUSD/XAGUSD";
        const res = await fetch(`/api/smc_telemetry?pair=${encodeURIComponent(pair)}`);
        if (res.ok) {
          const data = await res.json();
          if (active) setSmcTelemetry(data);
        }
      } catch (e) {}
    };
    fetchSmcData();
    const interval = setInterval(fetchSmcData, 2000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [selectedChartSymbol]);

  const symbolMatchesAlias = (candidate: string, selected: string) => {
    const c = (candidate || "").toUpperCase().split("/")[0].trim();
    const sel = (selected || "").toUpperCase().split("/")[0].trim();
    if (!c || !sel) return false;
    if (c === sel || c.startsWith(sel) || sel.startsWith(c)) return true;
    const us30Aliases = ["US30", "DJ30", "WS30", "DOW", "DJI"];
    const nasAliases = ["NAS100", "USTEC", "US100", "NDX", "NQ100"];
    const goldAliases = ["XAUUSD", "GOLD", "XAU"];
    if (us30Aliases.some((k) => sel.includes(k)) && us30Aliases.some((k) => c.includes(k))) return true;
    if (nasAliases.some((k) => sel.includes(k)) && nasAliases.some((k) => c.includes(k))) return true;
    if (goldAliases.some((k) => sel.includes(k)) && goldAliases.some((k) => c.includes(k))) return true;
    return false;
  };

  const activeSmcTel = useMemo(() => {
    const httpTelAll = (httpData as any)?.smcTelemetryAll || {};
    const wsTelAll = wsData?.smcTelemetryAll || {};
    const allMap: Record<string, any> = {
      ...httpTelAll,
      ...wsTelAll,
    };
    for (const [pairKey, telObj] of Object.entries(allMap)) {
      if (symbolMatchesAlias(pairKey, selectedChartSymbol) && telObj) {
        return telObj;
      }
    }
    const wsPair = (wsData?.smcTelemetry?.symbol_pair || "").toUpperCase();
    if (symbolMatchesAlias(wsPair, selectedChartSymbol)) {
      return wsData?.smcTelemetry;
    }
    const polledPair = (smcTelemetry?.symbol_pair || "").toUpperCase();
    if (symbolMatchesAlias(polledPair, selectedChartSymbol)) {
      return smcTelemetry;
    }
    return smcTelemetry || wsData?.smcTelemetry;
  }, [selectedChartSymbol, wsData?.smcTelemetry, wsData?.smcTelemetryAll, httpData, smcTelemetry]);

  useEffect(() => {
    if (!wsData) return;
    setPnlHistory(prev => {
      const next = [...prev, { t: Date.now(), pnl: wsData.floatingProfit, eq: wsData.equity }];
      return next.slice(-90);
    });
  }, [wsData]);

  useEffect(() => {
    const dbData = wsData ?? httpData;
    if (!dbData) return;
    const forexOn = dbData.forexEnabled ?? true;
    const metalsOn = dbData.metalsEnabled ?? true;
    const indicesOn = dbData.indicesEnabled ?? true;
    const stocksOn = (dbData as any).stocksEnabled ?? true;

    const isSymEnabled = (sym: string) => {
      const s = (sym || "").toUpperCase();
      if (s.includes("XAU") || s.includes("XAG") || s.includes("XPT") || s.includes("XPD")) return metalsOn;
      if (s.includes("AAPL") || s.includes("MSFT") || s.includes("GOOGL") || s.includes("TSLA") || s.includes("NVDA") || s.includes("AMD") || s.includes("META") || s.includes("AMZN")) return stocksOn;
      if (["US30", "DJ30", "WS30", "DOW", "DJI", "NAS100", "US100", "NDX", "US500", "GER30", "UK100", "USTEC"].some((k) => s.includes(k))) return indicesOn;
      return forexOn;
    };

    const curPairSym = (dbData.currentPair || "").split(/[\/\s]/)[0];
    if (curPairSym && isSymEnabled(curPairSym) && ((selectedChartSymbol === "EURUSD" && !forexOn) || !isSymEnabled(selectedChartSymbol))) {
      setSelectedChartSymbol(curPairSym);
    } else if (!isSymEnabled(selectedChartSymbol)) {
      if (metalsOn) setSelectedChartSymbol("XAUUSD");
      else if (indicesOn) setSelectedChartSymbol("US30");
      else if (stocksOn) setSelectedChartSymbol("AAPL");
      else if (forexOn) setSelectedChartSymbol("EURUSD");
    }
  }, [wsData, httpData, selectedChartSymbol]);

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
    (s: any) => ((s?.symbolA || "").toUpperCase().includes((selectedChartSymbol || "").toUpperCase())) ||
                ((s?.symbolB || "").toUpperCase().includes((selectedChartSymbol || "").toUpperCase()))
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

  const matchingAsset =
    dashboard?.scannedAssets?.find((a: any) =>
      symbolMatchesAlias(a?.symbolPair || "", selectedChartSymbol)
    ) ??
    dashboard?.scannedAssets?.find(
      (a: any) => (a?.symbolPair || "").startsWith(selectedChartSymbol) || (a?.symbolPair || "").endsWith(selectedChartSymbol)
    );

  const selectedAssetAction = matchingAsset?.action ?? "NONE";
  const selectedAssetZScore = matchingAsset?.zScore ?? 0.0;
  const selectedAssetWinRate = matchingAsset?.winRate ?? 50.0;

  const matchingPosition = dashboard?.activePositions?.find((p: any) =>
    symbolMatchesAlias(p?.symbol || "", selectedChartSymbol)
  );
  const hasActivePosition = matchingPosition != null;
  const activePositionType = matchingPosition?.type ?? "BUY";

  const selectedAssetZones = dashboard.activeZones?.filter((z: any) => {
    if (!z || !z.label) return false;
    if (z.label.toUpperCase().includes("USDT") || (z.type && z.type.toUpperCase().includes("USDT"))) return false;
    const labelUpper = z.label.toUpperCase();
    const chartUpper = selectedChartSymbol.toUpperCase();
    if (labelUpper.includes(`· ${chartUpper}`) || labelUpper.includes(` ${chartUpper} `) || labelUpper.endsWith(chartUpper)) return true;
    const afterDot = labelUpper.split("·").pop()?.trim() || "";
    return symbolMatchesAlias(afterDot, chartUpper);
  }) ?? [];

  const getStatusColor = (status: string) => {
    if (!status || typeof status !== "string") return "bg-gray-500";
    if (status.startsWith("RUNNING")) return "bg-green-500 shadow-[0_0_10px_rgba(34,197,94,0.5)]";
    if (status.startsWith("HALTED")) return "bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.5)]";
    return "bg-gray-500";
  };

  const formatMoney = (val: number) =>
    new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(val);

  const isBotActive = !String(systemStatus || "").toUpperCase().includes("STOPPED") && Boolean((dashboard as any)?.isBotRunning ?? (dashboard as any)?.is_bot_running ?? true);
  const safeAccountsList = Array.isArray(accountsList) ? accountsList : [];
  const activeAccount = safeAccountsList.find((a: any) => a?.is_active || Number(a?.login) === Number(mt5Login)) || safeAccountsList[0];

  const handleToggleBotRunning = async (forceState?: boolean) => {
    const nextState = typeof forceState === "boolean" ? forceState : !isBotActive;
    setIsTogglingBot(true);
    try {
      if (dashboard) {
        (dashboard as any).systemStatus = nextState ? "RUNNING (Active)" : "ENGINE STOPPED 🛑 (Standby)";
        (dashboard as any).isBotRunning = nextState;
        (dashboard as any).is_bot_running = nextState;
      }
      let ok = (
        await fetch("/api/bot/control", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ isRunning: nextState }),
        })
      ).ok;
      if (!ok) {
        ok = (
          await fetch("/api/execute-trade", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              symbol: "SYS_CTL",
              direction: "CLOSE",
              lots: 0.01,
              comment: nextState ? "BOTENGINE:ON" : "BOTENGINE:OFF",
            }),
          })
        ).ok;
      }
      if (ok) {
        toast({
          title: nextState ? "🟢 Trading Engine Started" : "🛑 Trading Engine Stopped",
          description: nextState
            ? "Live market scanning and Pure SMC execution is now ACTIVE."
            : "Engine paused in Standby mode. Zero trades will be opened.",
        });
        queryClient.invalidateQueries({ queryKey: getGetDashboardQueryKey() });
      } else {
        toast({ title: "Failed to toggle bot engine", variant: "destructive" });
      }
    } catch (e) {
      toast({ title: "Network error toggling bot", variant: "destructive" });
    } finally {
      setIsTogglingBot(false);
    }
  };

  const handleSwitchAccount = async (targetLogin: number, accountName: string) => {
    if (!window.confirm(`Switch trading bot to ${accountName} (Account #${targetLogin})?`)) return;
    setIsSwitchingAccount(true);
    try {
      const res = await fetch("/api/mt5/switch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ login: targetLogin }),
      });
      if (res.ok) {
        toast({
          title: "🔄 Switching Account...",
          description: `Switch command sent for #${targetLogin}. MT5 will connect in ~3s.`,
        });
        fetchAccounts();
        queryClient.invalidateQueries({ queryKey: getGetDashboardQueryKey() });
        setIsAccountModalOpen(false);
      } else {
        toast({ title: "Failed to switch account", variant: "destructive" });
      }
    } catch (e) {
      toast({ title: "Error switching account", variant: "destructive" });
    } finally {
      setIsSwitchingAccount(false);
    }
  };

  const handleAddAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newLogin || !newServer) {
      toast({ title: "Login & Server required", variant: "destructive" });
      return;
    }
    try {
      const res = await fetch("/api/mt5/accounts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          login: newLogin,
          server: newServer,
          password: newPassword,
          accountName: newName || (newType === "REAL" ? "Blue Guardian Real" : "Demo Account"),
          accountType: newType,
        }),
      });
      if (res.ok) {
        toast({ title: "✅ Account Saved", description: `Account #${newLogin} registered successfully.` });
        setNewLogin("");
        setNewPassword("");
        setNewServer("");
        setNewName("");
        setShowAddForm(false);
        fetchAccounts();
      } else {
        toast({ title: "Failed to save account", variant: "destructive" });
      }
    } catch (e) {
      toast({ title: "Error saving account", variant: "destructive" });
    }
  };

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
        "flex flex-col lg:flex-row lg:items-center lg:justify-between gap-2 px-3 sm:px-6 py-2.5 text-xs font-semibold tracking-wider",
        botOnline
          ? "bg-green-500/10 text-green-500 border-b border-green-500/20"
          : "bg-amber-500/10 text-amber-500 border-b border-amber-500/20"
      )}>
        <div className="flex flex-wrap items-center gap-2 sm:gap-3">
          {botOnline ? <Wifi className="h-4 w-4 shrink-0" /> : <WifiOff className="h-4 w-4 shrink-0" />}
          <span>{botOnline ? "BOT CONNECTED — LIVE DATA" : "BOT OFFLINE — LAST KNOWN DATA"}</span>
          <span className={cn(
            "flex items-center gap-1 px-2 py-0.5 rounded-sm text-[10px] border whitespace-nowrap",
            wsConnected
              ? "bg-cyan-500/10 text-cyan-400 border-cyan-500/20"
              : "bg-muted/30 text-muted-foreground border-border"
          )}>
            <Activity className="h-3 w-3" />
            {wsConnected ? "WS LIVE" : "POLLING"}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2 sm:gap-3">
          <div className="flex items-center gap-2">
            {autoExecute ? (
              <span className="flex items-center gap-1 text-green-400 whitespace-nowrap">
                <Zap className="h-3 w-3" />AUTO EXEC ON
              </span>
            ) : (
              <span className="flex items-center gap-1 text-amber-400 whitespace-nowrap">
                <ZapOff className="h-3 w-3" />SIGNALS ONLY
              </span>
            )}
          </div>
          <div className="flex items-center gap-1.5 max-w-full">
            <div className={cn("h-2 w-2 rounded-full shrink-0", getStatusColor(systemStatus))} />
            <span className="truncate max-w-[200px] sm:max-w-none">{systemStatus}</span>
          </div>
          <div className="text-zinc-500 font-mono text-[10px] uppercase flex flex-wrap items-center gap-1.5">
            <span>Scan Feed:</span>
            <span className={cn("px-1.5 py-0.5 rounded-sm text-[10px] font-bold border transition-all duration-300", dashboard.metalsEnabled ? "bg-amber-500/10 text-amber-400 border-amber-500/30 shadow-[0_0_10px_rgba(245,158,11,0.15)]" : "text-zinc-600 border-zinc-800 bg-zinc-900/20 opacity-50")}>Metals</span>
            <span className={cn("px-1.5 py-0.5 rounded-sm text-[10px] font-bold border transition-all duration-300", dashboard.forexEnabled ? "bg-cyan-500/10 text-cyan-400 border-cyan-500/30 shadow-[0_0_10px_rgba(6,182,212,0.15)]" : "text-zinc-600 border-zinc-800 bg-zinc-900/20 opacity-50")}>Forex</span>
            <span className={cn("px-1.5 py-0.5 rounded-sm text-[10px] font-bold border transition-all duration-300", dashboard.indicesEnabled ? "bg-blue-500/10 text-blue-400 border-blue-500/30 shadow-[0_0_10px_rgba(59,130,246,0.15)]" : "text-zinc-600 border-zinc-800 bg-zinc-900/20 opacity-50")}>Indices</span>
            <span className={cn("px-1.5 py-0.5 rounded-sm text-[10px] font-bold border transition-all duration-300", (dashboard as any)?.stocksEnabled ? "bg-purple-500/10 text-purple-400 border-purple-500/30 shadow-[0_0_10px_rgba(168,85,247,0.15)]" : "text-zinc-600 border-zinc-800 bg-zinc-900/20 opacity-50")}>Stocks</span>
          </div>
          <div className="font-mono bg-zinc-900/70 border border-zinc-800 px-2 py-0.5 rounded text-[11px] text-zinc-400 shadow-[0_0_8px_rgba(255,255,255,0.02)] whitespace-nowrap">
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
            className="bg-red-600 hover:bg-red-500 text-white font-mono text-[10px] font-bold h-7 px-2.5 shadow-[0_0_12px_rgba(239,68,68,0.25)] rounded border border-red-500/30 shrink-0"
            disabled={executeTrade.isPending || !botOnline || isReadOnly}
          >
            🚨 CLOSE ALL
          </Button>
        </div>
      </div>

      {/* ── REMOTE BOT CONTROL & ACCOUNT SWITCHER STRIP (Zero-Overlap Guarantee) ── */}
      <div className="bg-zinc-900/90 border-b border-zinc-800 px-3 sm:px-6 py-2.5 flex flex-wrap items-center justify-between gap-2.5 sm:gap-3 shrink-0">
        <div className="flex flex-wrap items-center gap-2 sm:gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={cn(
                "font-mono text-xs font-black h-8 px-3 rounded flex items-center gap-1.5 border",
                isBotActive
                  ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/40"
                  : "bg-rose-500/15 text-rose-400 border-rose-500/40 animate-pulse"
              )}
            >
              {isBotActive ? <Power className="h-3.5 w-3.5" /> : <PowerOff className="h-3.5 w-3.5" />}
              {isBotActive ? "ENGINE: ACTIVE 🟢" : "ENGINE: STOPPED 🛑"}
            </span>
            <Button
              onClick={() => handleToggleBotRunning(true)}
              size="sm"
              disabled={isTogglingBot || isReadOnly}
              className={cn(
                "font-mono text-xs font-black h-8 px-3 rounded shadow transition-all flex items-center gap-1.5",
                isBotActive
                  ? "bg-emerald-700/50 hover:bg-emerald-600 text-emerald-100 border border-emerald-500/30"
                  : "bg-emerald-600 hover:bg-emerald-500 text-white shadow-[0_0_14px_rgba(16,185,129,0.5)] border border-emerald-400 animate-bounce"
              )}
            >
              <Power className="h-3.5 w-3.5" />
              🟢 ON (START)
            </Button>
            <Button
              onClick={() => handleToggleBotRunning(false)}
              size="sm"
              disabled={isTogglingBot || isReadOnly}
              className={cn(
                "font-mono text-xs font-black h-8 px-3 rounded shadow transition-all flex items-center gap-1.5",
                !isBotActive
                  ? "bg-rose-900/40 hover:bg-rose-700 text-rose-200 border border-rose-500/30"
                  : "bg-rose-600 hover:bg-rose-500 text-white shadow-[0_0_12px_rgba(244,63,94,0.4)] border border-rose-400/50"
              )}
            >
              <PowerOff className="h-3.5 w-3.5" />
              🛑 OFF (STOP)
            </Button>
          </div>

          <div className="flex flex-col">
            <span className="text-[11px] font-bold text-zinc-200 flex items-center gap-1.5">
              {isBotActive ? (
                <>
                  <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                  Live Trading Engine Running
                </>
              ) : (
                <>
                  <span className="h-2 w-2 rounded-full bg-rose-400" />
                  Engine Halted (Standby Mode)
                </>
              )}
            </span>
            <span className="text-[10px] text-zinc-500 font-mono hidden sm:inline">
              {isBotActive
                ? ((dashboard as any)?.m1LtfEnabled ?? true)
                  ? "Scanning M15/M5 + M1 LTF Indices structure & executing orders"
                  : "Scanning M15/M5 market structure (M1 LTF OFF) & executing orders"
                : "No orders will be placed. Bot is paused safely."}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsAccountModalOpen(true)}
            className="h-8 px-3 bg-zinc-950 border-zinc-700 hover:border-zinc-500 text-zinc-100 font-mono text-xs font-bold rounded flex items-center gap-2 shadow-sm"
          >
            <ShieldCheck className="h-4 w-4 text-emerald-400" />
            <span className="max-w-[140px] sm:max-w-[220px] truncate">
              {activeAccount
                ? `${activeAccount.account_name || "MT5"} #${activeAccount.login}`
                : `MT5 #${mt5Login || "Connected"}`}
            </span>
            <Badge
              variant="outline"
              className={cn(
                "text-[9px] px-1.5 py-0 font-bold",
                activeAccount?.account_type === "REAL"
                  ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
                  : "bg-blue-500/20 text-blue-300 border-blue-500/40"
              )}
            >
              {activeAccount?.account_type || "DEMO"}
            </Badge>
            <ChevronDown className="h-3.5 w-3.5 text-zinc-400" />
          </Button>
        </div>
      </div>

      {/* ── MT5 ACCOUNT SWITCHER & MANAGER MODAL ── */}
      <Dialog open={isAccountModalOpen} onOpenChange={setIsAccountModalOpen}>
        <DialogContent className="max-w-md bg-zinc-950 border border-zinc-800 text-foreground p-6 rounded-lg shadow-2xl">
          <DialogHeader className="mb-4">
            <DialogTitle className="text-base font-black flex items-center gap-2 text-white">
              <ShieldCheck className="h-5 w-5 text-emerald-400" />
              MT5 Account Switcher & Manager
            </DialogTitle>
            <DialogDescription className="text-xs text-zinc-400">
              VPS par MetaTrader 5 me connected accounts select karein ya naya account add karein.
            </DialogDescription>
          </DialogHeader>

          {/* Accounts List */}
          <div className="space-y-2.5 max-h-[260px] overflow-y-auto pr-1">
            {safeAccountsList.length === 0 ? (
              <div className="p-4 rounded border border-zinc-800 bg-zinc-900/40 text-center text-xs text-zinc-400 font-mono">
                {isLoadingAccounts ? "Loading MT5 accounts..." : `Active Account: #${mt5Login || "None"}`}
              </div>
            ) : (
              safeAccountsList.map((acc: any) => {
                const isThisActive = acc.is_active || Number(acc.login) === Number(mt5Login);
                return (
                  <div
                    key={acc.login}
                    className={cn(
                      "p-3 rounded-lg border transition-all flex items-center justify-between gap-3",
                      isThisActive
                        ? "bg-emerald-950/30 border-emerald-500/50 shadow-[0_0_10px_rgba(16,185,129,0.15)]"
                        : "bg-zinc-900/50 border-zinc-800 hover:border-zinc-700"
                    )}
                  >
                    <div className="flex flex-col min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-xs text-white truncate">
                          {acc.account_name || "MT5 Account"}
                        </span>
                        <Badge
                          variant="outline"
                          className={cn(
                            "text-[8px] px-1 py-0 font-bold",
                            acc.account_type === "REAL"
                              ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
                              : "bg-blue-500/20 text-blue-300 border-blue-500/40"
                          )}
                        >
                          {acc.account_type || "DEMO"}
                        </Badge>
                      </div>
                      <div className="text-[10px] text-zinc-400 font-mono mt-0.5">
                        Login: <span className="text-zinc-200 font-bold">#{acc.login}</span> · {acc.server || "Server"}
                      </div>
                      {acc.equity > 0 && (
                        <div className="text-[10px] text-emerald-400 font-mono font-bold mt-0.5">
                          Equity: ${Number(acc.equity).toLocaleString("en-US", { minimumFractionDigits: 2 })}
                        </div>
                      )}
                    </div>

                    <div>
                      {isThisActive ? (
                        <Badge className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 text-[10px] font-bold px-2 py-1">
                          ACTIVE 🟢
                        </Badge>
                      ) : (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={isSwitchingAccount || isReadOnly}
                          onClick={() => handleSwitchAccount(Number(acc.login), acc.account_name || `Account #${acc.login}`)}
                          className="h-7 text-[10px] font-bold font-mono px-2.5 bg-zinc-900 hover:bg-zinc-800 border-zinc-700 text-zinc-200"
                        >
                          Switch 🔄
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Toggle Add Account Form */}
          <div className="mt-4 pt-3 border-t border-zinc-800">
            {!showAddForm ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowAddForm(true)}
                className="w-full text-xs font-bold text-zinc-300 hover:text-white hover:bg-zinc-900 border border-dashed border-zinc-700 h-8 flex items-center justify-center gap-1.5"
              >
                <Plus className="h-3.5 w-3.5 text-emerald-400" />
                + Connect Another Prop Firm / Broker Account
              </Button>
            ) : (
              <form onSubmit={handleAddAccount} className="space-y-3 bg-zinc-900/60 p-3 rounded-lg border border-zinc-800">
                <div className="text-xs font-bold text-zinc-200 flex items-center justify-between">
                  <span>Register New MT5 Account</span>
                  <button
                    type="button"
                    onClick={() => setShowAddForm(false)}
                    className="text-zinc-400 hover:text-zinc-200 text-[10px]"
                  >
                    Cancel
                  </button>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[10px] text-zinc-400 block mb-1">Login Number</label>
                    <Input
                      value={newLogin}
                      onChange={(e) => setNewLogin(e.target.value)}
                      placeholder="e.g. 482910"
                      className="h-7 text-xs bg-zinc-950 border-zinc-800 font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-zinc-400 block mb-1">Server Name</label>
                    <Input
                      value={newServer}
                      onChange={(e) => setNewServer(e.target.value)}
                      placeholder="e.g. BlueGuardian-Server"
                      className="h-7 text-xs bg-zinc-950 border-zinc-800 font-mono"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[10px] text-zinc-400 block mb-1">Password</label>
                    <Input
                      type="password"
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      placeholder="Trader Password"
                      className="h-7 text-xs bg-zinc-950 border-zinc-800 font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-zinc-400 block mb-1">Account Name</label>
                    <Input
                      value={newName}
                      onChange={(e) => setNewName(e.target.value)}
                      placeholder="e.g. Blue Guardian Real"
                      className="h-7 text-xs bg-zinc-950 border-zinc-800"
                    />
                  </div>
                </div>

                <div className="flex items-center justify-between pt-1">
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setNewType("REAL")}
                      className={cn("px-2 py-0.5 rounded text-[10px] font-bold border", newType === "REAL" ? "bg-emerald-500/20 text-emerald-300 border-emerald-500" : "bg-zinc-800 text-zinc-400 border-zinc-700")}
                    >
                      REAL
                    </button>
                    <button
                      type="button"
                      onClick={() => setNewType("DEMO")}
                      className={cn("px-2 py-0.5 rounded text-[10px] font-bold border", newType === "DEMO" ? "bg-blue-500/20 text-blue-300 border-blue-500" : "bg-zinc-800 text-zinc-400 border-zinc-700")}
                    >
                      DEMO
                    </button>
                  </div>
                  <Button type="submit" size="sm" className="h-7 px-3 text-xs bg-emerald-600 hover:bg-emerald-500 text-white font-bold">
                    Save Account
                  </Button>
                </div>
              </form>
            )}
          </div>
        </DialogContent>
      </Dialog>

      <div className="p-3 sm:p-6 space-y-4 sm:space-y-6">
        {/* High-Impact News Protection Card */}
        <Card className={cn(
          "bg-zinc-900 border transition-all rounded-md p-3.5 sm:p-4",
          systemStatus.includes("HALTED (News")
            ? "border-red-500/60 bg-red-950/20 text-red-400"
            : "border-emerald-500/40 bg-zinc-900/80 text-zinc-100"
        )}>
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2.5">
            <div className="flex items-start sm:items-center gap-2.5 sm:gap-3 min-w-0">
              <span className="text-xl shrink-0">📰</span>
              <div className="min-w-0">
                <div className="font-bold text-sm text-zinc-100">High-Impact News Protection (15-Min Buffer)</div>
                <div className="text-xs text-zinc-400">Real-time safeguard against NFP, CPI, FOMC volatility</div>
              </div>
            </div>
            <span className={cn(
              "self-start sm:self-auto shrink-0 whitespace-nowrap px-2.5 py-1 rounded text-xs font-bold border",
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

        {/* Pure Risk-Free Breakeven Guard Card (Trailing Stop & Stagnation Disabled) */}
        {(() => {
          const isBeLocked = Boolean(systemStatus && systemStatus.includes("Breakeven Active"));
          return (
            <Card className={cn(
              "bg-zinc-900 border transition-all rounded-md p-4",
              isBeLocked
                ? "border-emerald-500/60 bg-emerald-950/20 text-emerald-400 shadow-[0_0_20px_rgba(16,185,129,0.15)]"
                : "border-zinc-800 bg-zinc-900/80 text-zinc-100"
            )}>
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2.5">
                <div className="flex items-start sm:items-center gap-2.5 sm:gap-3 min-w-0">
                  <span className="text-xl shrink-0">🛡️</span>
                  <div className="min-w-0">
                    <div className="font-bold text-sm text-zinc-100">Pure Risk-Free Breakeven Guard (+$50.00 USD Trigger)</div>
                    <div className="text-xs text-zinc-400">Trailing Stop: DISABLED 🔴 | Stagnation Guard: DISABLED 🔴 | SL moves ONCE to Entry buffer only at +$50.00+</div>
                  </div>
                </div>
                <span className={cn(
                  "self-start sm:self-auto shrink-0 px-2.5 py-1 rounded text-xs font-bold border whitespace-normal sm:whitespace-nowrap",
                  isBeLocked
                    ? "bg-emerald-500/30 text-emerald-300 border-emerald-500 shadow-[0_0_12px_rgba(52,211,153,0.3)]"
                    : "bg-zinc-800 text-zinc-300 border-zinc-700"
                )}>
                  {isBeLocked ? "🛡️ BREAKEVEN LOCKED RISK-FREE" : "🟢 ARMED AT +$50.00 (TRAILING OFF)"}
                </span>
              </div>
              <div className="mt-3 p-2.5 rounded bg-zinc-950/60 border border-zinc-800 text-xs text-zinc-300">
                {isBeLocked ? (
                  <span>🛡️ <strong>BREAKEVEN ACTIVE:</strong> SL shifted ONCE past Entry (+$0.25 Gold / +2.15pt Indices). Trailing Stop & Stagnation OFF — TP runs untouched.</span>
                ) : (
                  <span>🛡️ <strong>Pure Breakeven Policy:</strong> No early $35 cuts and no 60m stagnation shifts — SL stays untouched until floating hits <strong>+$50.00 USD</strong> (Current Floating: {floatingProfit >= 0 ? "+" : ""}${floatingProfit.toFixed(2)})</span>
                )}
              </div>
            </Card>
          );
        })()}

        {/* Session Time Guard (PKT Trading Windows) Card */}
        <SessionGuardCard data={dashboard} isReadOnly={isReadOnly} />


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

          {(() => {
            const netGainUsd = equity - (initialBalance || 10000.0);
            const netGainPct = initialBalance > 0 ? (netGainUsd / initialBalance) * 100 : 0;
            const isNetGain = netGainUsd >= -0.001;

            return (
              <Card className={cn("bg-zinc-900 border-zinc-800 border-t-2 transition-all rounded-md overflow-hidden", 
                isNetGain 
                  ? "border-t-emerald-500 hover:border-emerald-400/40 shadow-[0_4px_24px_rgba(16,185,129,0.06)]" 
                  : "border-t-amber-500 hover:border-amber-400/40 shadow-[0_4px_24px_rgba(245,158,11,0.06)]"
              )}>
                <CardHeader className="pb-1">
                  <CardTitle className="text-xs text-zinc-500 uppercase tracking-wider font-mono flex flex-wrap items-center justify-between gap-1">
                    <span>{isNetGain ? "Daily Net Gain" : "Daily Drawdown"}</span>
                    <span className="text-[9px] text-zinc-500 font-mono">
                      Halt: <span className="text-amber-500">{Number((dashboard as any)?.halt_drawdown_limit ?? (dashboard as any)?.haltDrawdownLimit ?? 0.83).toFixed(2)}%</span> · Limit: <span className="text-red-500">{Number((dashboard as any)?.max_drawdown_limit ?? (dashboard as any)?.maxDrawdownLimit ?? 3.3).toFixed(1)}%</span>
                    </span>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 pb-3">
                  <div>
                    <div className={cn("text-xl font-mono font-bold leading-tight", isNetGain ? "text-emerald-400" : "text-amber-400")}>
                      {isNetGain ? `+${Math.abs(netGainPct).toFixed(2)}%` : `-${Math.abs(netGainPct).toFixed(2)}%`}
                    </div>
                    {isNetGain ? (
                      <div className="text-xs font-mono text-emerald-400/90 font-semibold mt-0.5">
                        (+${Math.abs(netGainUsd).toFixed(2)} USD)
                      </div>
                    ) : (
                      <div className="text-xs font-mono text-amber-400/90 font-semibold mt-0.5">
                        (-${Math.abs(netGainUsd).toFixed(2)} USD)
                      </div>
                    )}
                    {!isNetGain && (
                      <div className="text-[10px] font-mono text-zinc-400 mt-1">
                        Below Start Equity (${(initialBalance || 10000.0).toFixed(2)}) | Current DD: <span className="text-amber-400 font-semibold">-{Math.abs(netGainPct).toFixed(2)}%</span>
                      </div>
                    )}
                  </div>
                  <Progress 
                    value={isNetGain ? 0 : Math.min((drawdownPercent / 3.3) * 100, 100)} 
                    className="h-1.5 bg-zinc-800 [&>div]:bg-rose-500" 
                  />
                </CardContent>
              </Card>
            );
          })()}




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
          <Card className="bg-card border-border border-t-2 border-t-emerald-500 shadow-[0_4px_24px_rgba(16,185,129,0.06)]">
            <CardHeader className="pb-2">
              {(() => {
                const symHdr = (selectedChartSymbol || "").toUpperCase();
                const isIdxHdr = ["US30", "DJ30", "WS30", "DOW", "DJI", "NAS100", "USTEC", "US100", "NDX", "NQ100"].some((k) => symHdr.includes(k));
                const m1LtfOnHdr = Boolean((dashboard as any)?.m1LtfEnabled ?? true);
                const telHdr = activeSmcTel as any;
                const isM1Hdr = m1LtfOnHdr && (isIdxHdr || Boolean(telHdr?.m1_active || telHdr?.execution_mode === "M1_LTF"));
                return (
                  <CardTitle className="text-xs text-emerald-400 uppercase tracking-wider font-mono flex flex-wrap items-center justify-between gap-2">
                    <span>
                      {isM1Hdr
                        ? "Pure SMC / ICT 6-Condition M1 Telemetry Engine"
                        : "Pure SMC / ICT 7-Condition M5 Telemetry Engine"}
                    </span>
                    <Badge
                      className={cn(
                        "text-[10px] shrink-0",
                        isM1Hdr
                          ? "bg-cyan-500/20 text-cyan-300 border-cyan-500/40"
                          : "bg-emerald-500/20 text-emerald-400 border-emerald-500/40"
                      )}
                    >
                      {isM1Hdr ? "⚡ 6-COND M1 LTF ENGINE" : "🟢 7-COND M5 SMC ENGINE"}
                    </Badge>
                  </CardTitle>
                );
              })()}
            </CardHeader>
            <CardContent className="space-y-3">
              {(() => {
                const tel = activeSmcTel as any;
                const isPassText = (val: unknown) =>
                  typeof val === "string" && (val.includes("PASS") || val.includes("🟢"));
                const isFailText = (val: unknown) =>
                  typeof val === "string" && !val.includes("PASS") && (val.includes("🔴") || (val.includes("FAIL") && !val.includes("⚪")));

                const s1Text = tel?.m15_bias || "NEUTRAL ⚪";
                const isM15Bull = s1Text.includes("BULLISH");
                const isM15Bear = s1Text.includes("BEARISH");
                const s1Valid = (isM15Bull || isM15Bear) && !s1Text.includes("NEUTRAL");

                const sweepText = tel?.sweep_status || "";
                const chochText = tel?.choch_status || "";
                const fvgText = tel?.fvg_status || "";
                const retestText = tel?.retest_status || "";
                const s6Text = tel?.s6_status || tel?.rejection_status || "";
                const s7Text = tel?.s7_status || "";
                const s8Text = tel?.s8_status || "";
                const s9Text = tel?.s9_status || "";

                const s2Valid = s1Valid && isPassText(sweepText);
                const s3Valid = s2Valid && isPassText(chochText);
                const s4Valid = s3Valid && isPassText(fvgText);
                const s5Valid = s4Valid && isPassText(retestText);
                const s6Valid = s5Valid && isPassText(s6Text);
                const s7Valid = s6Valid && isPassText(s7Text);
                const closedRejectPass = s7Valid;
                const closedRejectFail = s4Valid && !closedRejectPass && (isFailText(retestText) || isFailText(s6Text) || isFailText(s7Text));

                const s8Failed = isFailText(s8Text);
                const s8Valid = !s8Failed && (isPassText(s8Text) || s2Valid);
                const s9Failed = isFailText(s9Text);
                const s9Valid = !s9Failed && (isPassText(s9Text) || (closedRejectPass && hasActivePosition));
                const slTpFail = s8Failed || s9Failed;
                const slTpPass = !slTpFail && s8Valid && (isPassText(s9Text) || (closedRejectPass && hasActivePosition));

                const getBoxClass = (isValid: boolean, isCurrent: boolean, isBearOrFail = false) => {
                  if (isBearOrFail) {
                    return "p-2.5 rounded-lg border-2 text-center transition-all duration-300 bg-rose-950/80 border-rose-500 text-rose-200 shadow-[0_0_10px_rgba(244,63,94,0.3)]";
                  }
                  if (isValid) {
                    return "p-2.5 rounded-lg border-2 text-center transition-all duration-300 bg-emerald-950/80 border-emerald-400 text-emerald-200 shadow-[0_0_14px_rgba(16,185,129,0.3)]";
                  }
                  if (isCurrent) {
                    return "p-2.5 rounded-lg border-2 text-center transition-all duration-300 bg-amber-950/70 border-amber-400 text-amber-200 shadow-[0_0_14px_rgba(245,158,11,0.3)] animate-pulse";
                  }
                  return "p-2.5 rounded-lg border-2 text-center transition-all duration-300 bg-slate-900 border-slate-600 shadow-sm";
                };

                const getTextColor = (isValid: boolean, isCurrent: boolean, isBearOrFail = false) => {
                  if (isBearOrFail) return "text-rose-300 font-black";
                  if (isValid) return "text-emerald-300 font-black";
                  if (isCurrent) return "text-amber-300 font-black";
                  return "text-white font-bold";
                };

                const symU = (selectedChartSymbol || "").toUpperCase();
                const isUs30Sel = ["US30", "DJ30", "WS30", "DOW", "DJI"].some((k) => symU.includes(k));
                const isNasSel = ["NAS100", "USTEC", "US100", "NDX", "NQ100"].some((k) => symU.includes(k));
                const isIdxSel = isUs30Sel || isNasSel;
                const isMetalSel = ["XAU", "GOLD", "XAG", "SILVER"].some((k) => symU.includes(k));
                const m1LtfOn = Boolean((dashboard as any)?.m1LtfEnabled ?? true);
                const isM1CardMode = m1LtfOn && (isIdxSel || Boolean(tel?.m1_active || tel?.execution_mode === "M1_LTF"));
                const pricePrefixSel = isIdxSel ? "" : "$";
                const s8BufTxt = isIdxSel ? "6.50pt" : isMetalSel ? "$0.75" : "4p";
                const s8CapTxt = isUs30Sel ? "105pt" : isNasSel ? "85pt" : isMetalSel ? "$10.00" : "50p";
                const s9BufTxt = isIdxSel ? "-9.35pt" : isMetalSel ? "-$1.10" : "-3.5p";

                return (
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 font-mono">
                    {/* C1: M15 Bias */}
                    <div className={getBoxClass(s1Valid && isM15Bull, !s1Valid, s1Valid && isM15Bear)}>
                      <div className="text-[10px] text-slate-300 uppercase font-semibold mb-1">C1: M15 Bias</div>
                      <div className={cn("text-xs truncate", getTextColor(s1Valid && isM15Bull, !s1Valid, s1Valid && isM15Bear))}>
                        {s1Valid ? (isM15Bull ? "BULLISH 🟢" : "BEARISH 🔴") : "NEUTRAL ⚪"}
                      </div>
                      <div className="text-[9px] text-slate-400 font-medium mt-0.5">
                        {s1Valid ? "HTF Structure Set" : "Awaiting Trend Confirmation"}
                      </div>
                    </div>

                    {/* C2: M5 Sweep */}
                    <div className={getBoxClass(s2Valid, s1Valid && !s2Valid)}>
                      <div className="text-[10px] text-slate-300 uppercase font-semibold mb-1">C2: M5 Sweep</div>
                      <div className={cn("text-xs truncate", getTextColor(s2Valid, s1Valid && !s2Valid))}>
                        {s2Valid ? "PASS 🟢 (Wick Sweep)" : s1Valid ? "SCANNING ⏳" : "WAITING ⚪"}
                      </div>
                      <div className="text-[9px] text-slate-400 font-medium mt-0.5">
                        {s2Valid ? `Sweep Price: ${pricePrefixSel}${Number(tel?.sweep_price ?? 0).toFixed(2)}` : "Awaiting Fresh Sweep"}
                      </div>
                    </div>

                    {/* C3: CHoCH Break */}
                    <div className={getBoxClass(s3Valid, s2Valid && !s3Valid)}>
                      <div className="text-[10px] text-slate-300 uppercase font-semibold mb-1">
                        {isM1CardMode ? "C3: M1 LTF CHoCH" : "C3: M5 CHoCH"}
                      </div>
                      <div title={chochText} className={cn("text-xs truncate", getTextColor(s3Valid, s2Valid && !s3Valid))}>
                        {s3Valid ? (chochText || "PASS 🟢 (Break)") : s2Valid ? "SCANNING ⏳" : "WAITING ⚪"}
                      </div>
                      <div className="text-[9px] text-slate-400 font-medium mt-0.5">
                        {s3Valid ? `CHoCH: ${pricePrefixSel}${Number(tel?.choch_price ?? 0).toFixed(2)}` : `Awaiting ${isM1CardMode ? "M1" : "M5"} CHoCH`}
                      </div>
                    </div>

                    {/* C4: Displacement FVG */}
                    <div className={getBoxClass(s4Valid, s3Valid && !s4Valid)}>
                      <div className="text-[10px] text-slate-300 uppercase font-semibold mb-1">
                        {isM1CardMode ? "C4: M1 FVG" : "C4: M5 FVG"}
                      </div>
                      <div title={fvgText} className={cn("text-xs truncate", getTextColor(s4Valid, s3Valid && !s4Valid))}>
                        {s4Valid ? (fvgText || "PASS 🟢 (Created)") : s3Valid ? "SCANNING ⏳" : "WAITING ⚪"}
                      </div>
                      <div className="text-[9px] text-slate-400 font-medium mt-0.5">
                        {s4Valid ? (String(fvgText).includes("M1") || isM1CardMode ? "M1 LTF FVG Ready" : "M5 FVG Ready") : `Awaiting ${isM1CardMode ? "M1" : "M5"} FVG`}
                      </div>
                    </div>

                    {/* C5: Unified Closed FVG Retest + Rejection + Close */}
                    <div className={getBoxClass(closedRejectPass, s4Valid && !closedRejectPass && !closedRejectFail, closedRejectFail)}>
                      <div className="text-[10px] text-slate-300 uppercase font-semibold mb-1">
                        {isM1CardMode ? "C5: Closed M1 Rej" : "C5: Closed M5 Rej"}
                      </div>
                      <div
                        title={s7Text || s6Text || retestText}
                        className={cn("text-xs truncate", getTextColor(closedRejectPass, s4Valid && !closedRejectPass && !closedRejectFail, closedRejectFail))}
                      >
                        {closedRejectPass
                          ? (s7Text && isPassText(s7Text) ? s7Text : "PASS 🟢 (Closed Rej)")
                          : closedRejectFail
                          ? (isFailText(s7Text) ? s7Text : isFailText(s6Text) ? s6Text : retestText)
                          : s6Valid
                          ? "WAIT CLOSE ⏳"
                          : s5Valid
                          ? "REJECTING ⏳"
                          : s4Valid
                          ? "AWAIT FVG TAP ⏳"
                          : "WAITING ⚪"}
                      </div>
                      <div className="text-[9px] text-slate-400 font-medium mt-0.5 truncate" title={s7Text || s6Text}>
                        {closedRejectPass
                          ? `${isM1CardMode || String(s7Text).includes("M1") ? "M1" : "M5"} Closed Rejection Confirmed`
                          : closedRejectFail
                          ? (s7Text || s6Text || "Rejection Failed")
                          : s4Valid
                          ? `Retest + Reject + ${isM1CardMode ? "M1" : "M5"} Close`
                          : "Awaiting Displacement FVG"}
                      </div>
                    </div>

                    {isM1CardMode ? (
                      /* C6 (M1 Mode): Unified SL Guard (38pt+ Floor / Cap) + M15 Opposing Target (>=1.85R) */
                      <div className={getBoxClass(slTpPass, closedRejectPass && !slTpPass && !slTpFail, slTpFail)}>
                        <div className="text-[10px] text-slate-300 uppercase font-semibold mb-1">C6: SL Guard &amp; M15 TP</div>
                        <div
                          title={`${s8Text} | ${s9Text}`}
                          className={cn("text-xs truncate", getTextColor(slTpPass, closedRejectPass && !slTpPass && !slTpFail, slTpFail))}
                        >
                          {slTpFail
                            ? (s8Failed ? (s8Text || "FAIL 🔴 (SL Cap)") : (s9Text || "FAIL 🔴 (<1.85R)"))
                            : slTpPass
                            ? "LOCKED 🟢 (>=1.85R)"
                            : s8Valid
                            ? "SL OK ⏳ (Check TP)"
                            : "WAITING ⚪"}
                        </div>
                        <div className="text-[9px] text-slate-400 font-medium mt-0.5 truncate" title={`${s8Text} ${s9Text}`}>
                          {slTpFail
                            ? (s8Failed ? `Exceeds ${s8CapTxt} / 38pt Floor` : "Below 1.85R Min R:R")
                            : slTpPass
                            ? `38pt+ M1 SL (${s8CapTxt}) · M15 TP`
                            : `38pt Min SL · ${s8CapTxt} Cap · >=1.85R`}
                        </div>
                      </div>
                    ) : (
                      <>
                        {/* C6 (M5 Mode): SL Buffer */}
                        <div className={getBoxClass(s8Valid, false, s8Failed)}>
                          <div className="text-[10px] text-slate-300 uppercase font-semibold mb-1">C6: SL Buffer</div>
                          <div title={s8Text} className={cn("text-xs truncate", getTextColor(s8Valid, false, s8Failed))}>
                            {s8Failed ? (s8Text || "FAIL 🔴 (SL Cap)") : s8Valid ? (isPassText(s8Text) ? s8Text : `PASS 🟢 (${s8BufTxt} Buf)`) : "WAITING SWEEP ⚪"}
                          </div>
                          <div className="text-[9px] text-slate-400 font-medium mt-0.5 truncate" title={s8Text}>
                            {s8Failed ? `Exceeds ${s8CapTxt} Max SL Cap` : s8Valid ? (String(s8Text).includes("FVG-Refined") ? `FVG-Defense Refined (${s8CapTxt} Cap)` : `Sweep ± ${s8BufTxt} (${s8CapTxt} Cap)`) : "Locks on M5 Sweep (C2)"}
                          </div>
                        </div>

                        {/* C7 (M5 Mode): Opposing Target */}
                        <div className={getBoxClass(s9Valid, false, s9Failed)}>
                          <div className="text-[10px] text-slate-300 uppercase font-semibold mb-1">C7: Opposing Target</div>
                          <div title={s9Text} className={cn("text-xs truncate", getTextColor(s9Valid, false, s9Failed))}>
                            {s9Failed ? (s9Text || "FAIL 🔴 (<1.85R)") : s9Valid ? (isPassText(s9Text) ? s9Text : "PASS 🟢 (M15 Target)") : (s9Text || "WAITING ⚪")}
                          </div>
                          <div className="text-[9px] text-slate-400 font-medium mt-0.5 truncate" title={s9Text}>
                            {s9Failed ? "Below 1.85R Min R:R" : s9Valid ? `M15 Opposing Liq (${s9BufTxt})` : "Min 1.85R M15 Structural TP"}
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                );
              })()}
              <div className="grid grid-cols-2 gap-4 pt-2 border-t border-border">
                <div>
                  <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Max Risk Cap</div>
                  <div className="font-mono text-sm font-bold text-amber-400">
                    {["US30", "DJ30", "WS30", "DOW", "DJI"].some((k) => (selectedChartSymbol || "").toUpperCase().includes(k))
                      ? "$52.00 USD (105pt Max US30 SL)"
                      : ["NAS100", "USTEC", "US100", "NDX", "NQ100"].some((k) => (selectedChartSymbol || "").toUpperCase().includes(k))
                      ? "$52.00 USD (85pt Max NAS100 SL)"
                      : "$52.00 USD ($10.00 Max Gold SL)"}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Hedge Ratio (β)</div>
                  <div className="font-mono text-sm font-bold text-sky-400">{hedgeRatio.toFixed(4)}</div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card border-border">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-xs text-muted-foreground uppercase tracking-wider">SMC Zones · FVG · OB · Breaker</CardTitle>
                {selectedAssetZones.length > 0 && (
                  <Badge variant="outline" className="text-[10px] rounded-sm bg-indigo-500/10 text-indigo-400 border-indigo-500/30 font-bold shadow-[0_0_8px_rgba(99,102,241,0.08)]">
                    {selectedAssetZones.length} ACTIVE ({selectedChartSymbol})
                  </Badge>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {selectedAssetZones.length === 0 ? (
                <div className="text-sm text-muted-foreground py-4 text-center border border-dashed border-border rounded">
                  No active zones for {selectedChartSymbol} — bot writes zones every ~20s when connected
                </div>
              ) : (
                <div className="space-y-2 max-h-[200px] overflow-y-auto">
                  {selectedAssetZones.map((zone, i) => {
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
            <CardHeader className="pb-2 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <div>
                <CardTitle className="text-xs text-muted-foreground uppercase tracking-wider font-mono">Live Market Chart & Pure SMC Structure</CardTitle>
                <p className="text-xs text-muted-foreground mt-1">
                  Institutional real-time charting for: <span className="font-mono font-bold text-indigo-400">{selectedChartSymbol}</span> (Click any pill or table asset below)
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-1.5">
                {[
                  ...(dashboard?.metalsEnabled ?? true ? ["XAUUSD"] : []),
                  ...(dashboard?.indicesEnabled ?? true ? ["US30", "NAS100"] : []),
                  ...(dashboard?.forexEnabled ? ["EURUSD", "GBPUSD"] : []),
                ].map((quickSym) => (
                  <Button
                    key={quickSym}
                    type="button"
                    size="sm"
                    variant={selectedChartSymbol.toUpperCase() === quickSym ? "default" : "outline"}
                    className={cn(
                      "h-7 px-2.5 text-[11px] font-mono font-bold",
                      selectedChartSymbol.toUpperCase() === quickSym
                        ? "bg-indigo-600 hover:bg-indigo-500 text-white border-indigo-400"
                        : "bg-zinc-900/70 border-zinc-700 text-zinc-300 hover:text-white"
                    )}
                    onClick={() => setSelectedChartSymbol(quickSym)}
                  >
                    {quickSym}
                  </Button>
                ))}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <SmcChartOverlay
                symbol={selectedChartSymbol}
                telemetry={activeSmcTel}
                currentPrice={Number(matchingAsset?.priceA || activeSmcTel?.sweep_price || 0)}
                activePosition={matchingPosition}
                activeZones={selectedAssetZones}
                m1LtfEnabled={Boolean((dashboard as any)?.m1LtfEnabled ?? true)}
              />
              
              {/* Signals Timeline for selected symbol */}
              <div className="p-3 bg-zinc-950 border border-zinc-900 rounded-md">
                <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-mono mb-2">Recent Execution Signals ({selectedChartSymbol})</div>
                {recentSymbolSignals.length === 0 ? (
                  <div className="text-xs text-zinc-500 italic font-mono">No recent signals recorded for {selectedChartSymbol}</div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                    {recentSymbolSignals.slice(0, 3).map((sig: any) => {
                      const isBuy = sig.action === "BUY_SPREAD";
                      const dateStr = formatPktTime(sig.timestamp);
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

        {/* Pure SMC Multi-Asset Live Scanner (Crypto-App Parity Layout) */}
        <Card className="bg-card border-border border-t-2 border-t-blue-500/70 hover:border-blue-500/40 transition-all rounded-md">
          <CardHeader className="pb-3 flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-xs text-muted-foreground uppercase tracking-wider font-mono">Multi-Asset Pure SMC Live Scanner</CardTitle>
              <p className="text-xs text-muted-foreground mt-1">
                {((dashboard as any)?.m1LtfEnabled ?? true)
                  ? "Click any asset row to load its M1/M5 candles, FVG, Sweep, CHoCH, SL, TP & C1–C6/C7 Pipeline"
                  : "Click any asset row to load its M5 candles, FVG, Sweep, CHoCH, SL, TP & C1–C7 Pipeline"}
              </p>
            </div>
            <Badge variant="outline" className="bg-blue-500/10 text-blue-400 border-blue-500/20 font-mono text-[10px] rounded-sm">
              {dashboard.scannedAssets?.length ?? 0} ASSETS SCANNED
            </Badge>
          </CardHeader>
          <CardContent>
            {!dashboard.scannedAssets || dashboard.scannedAssets.length === 0 ? (
              <div className="text-sm text-muted-foreground py-8 text-center border border-dashed border-border rounded font-mono">
                No scanned assets found. Ensure the MT5 VPS trading bot is running.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="border-border hover:bg-transparent">
                      <TableHead className="font-mono text-xs">ASSET (MT5)</TableHead>
                      <TableHead className="font-mono text-xs text-right">MARK PRICE</TableHead>
                      <TableHead className="font-mono text-xs text-right">M15 TARGET TP</TableHead>
                      <TableHead className="font-mono text-xs text-right">SMC SCORE</TableHead>
                      <TableHead className="font-mono text-xs text-right">R:R</TableHead>
                      <TableHead className="font-mono text-xs text-center">M15 BIAS / SIGNAL</TableHead>
                      <TableHead className="font-mono text-xs text-center">ACTION</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(dashboard?.scannedAssets || []).map((asset: any) => {
                      const pairStr = String(asset?.symbolPair || "");
                      const legA = String(asset?.symbol || pairStr.split("/")[0] || pairStr);
                      const isRowSelected = symbolMatchesAlias(legA, selectedChartSymbol);
                      const isMetalOrFx = !["US30", "DJ30", "WS30", "DOW", "DJI", "NAS100", "USTEC", "US100", "NDX"].some((k) => legA.toUpperCase().includes(k));
                      const pPrefix = isMetalOrFx ? "$" : "";
                      const markPx = Number(asset?.priceA || 0);
                      const tpPx = Number(asset?.opposingTp || 0);
                      const m1LtfOnRow = Boolean((dashboard as any)?.m1LtfEnabled ?? true);
                      const totalSteps = Number(asset?.conditionsCount ?? ((m1LtfOnRow && (!isMetalOrFx || asset?.m1Active)) ? 6 : 7));
                      const stepsPassed = Math.min(totalSteps, Number(asset?.stepsPassed ?? 0));
                      const targetRrr = Number(asset?.targetRrr ?? 0);
                      const rawBias = String(asset?.m15Bias || "NEUTRAL").toUpperCase();
                      const rawAct = String(asset?.action || "NONE").toUpperCase();
                      const badgeTxt =
                        rawAct === "BUY" || rawAct === "BUY_SPREAD"
                          ? "LONG EXECUTE 🟢"
                          : rawAct === "SELL" || rawAct === "SELL_SPREAD"
                          ? "SHORT EXECUTE 🔴"
                          : rawBias;

                      return (
                        <TableRow
                          key={pairStr}
                          onClick={() => setSelectedChartSymbol(legA)}
                          className={cn(
                            "cursor-pointer border-border transition-colors",
                            isRowSelected ? "bg-indigo-500/10 hover:bg-indigo-500/15" : "hover:bg-muted/30"
                          )}
                        >
                          <TableCell className="font-mono font-bold text-xs">
                            <div className="flex items-center gap-2">
                              <span className={cn(isRowSelected ? "text-indigo-300" : "text-zinc-100")}>{legA}</span>
                              {pairStr.includes("/") && (
                                <span className="text-[10px] font-normal text-zinc-500">({pairStr})</span>
                              )}
                            </div>
                          </TableCell>
                          <TableCell className="font-mono text-xs text-right">
                            {markPx > 0 ? `${pPrefix}${formatAssetPrice(markPx, legA)}` : "-"}
                          </TableCell>
                          <TableCell className="font-mono text-xs text-right text-emerald-400">
                            {tpPx > 0 ? `${pPrefix}${formatAssetPrice(tpPx, legA)}` : "-"}
                          </TableCell>
                          <TableCell className={cn(
                            "font-mono text-xs text-right font-semibold",
                            stepsPassed >= Math.max(4, totalSteps - 1) ? "text-emerald-400" : stepsPassed >= 3 ? "text-amber-300" : "text-zinc-200"
                          )}>
                            {stepsPassed} / {totalSteps} Steps
                          </TableCell>
                          <TableCell className="font-mono text-xs text-right text-sky-400 font-bold">
                            {targetRrr > 0 ? `${targetRrr.toFixed(2)}R` : "-"}
                          </TableCell>
                          <TableCell className="text-center">
                            <Badge
                              variant="outline"
                              className={cn(
                                "font-mono text-[10px] px-2.5 py-0.5 rounded-sm font-bold",
                                badgeTxt.includes("LONG") || badgeTxt === "BULL_BIAS"
                                  ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                                  : badgeTxt.includes("SHORT") || badgeTxt === "BEAR_BIAS"
                                  ? "bg-rose-500/15 text-rose-400 border-rose-500/30"
                                  : "bg-zinc-800 text-zinc-400 border-zinc-700"
                              )}
                            >
                              {badgeTxt}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-center">
                            {rawAct !== "NONE" && (
                              <Button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleOneClickExecute(pairStr, rawAct);
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
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
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
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4 text-xs font-mono">
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
                  {(activePositions || []).map((pos) => (
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
                      <TableCell className="font-mono text-right">{Number(pos?.lots || 0).toFixed(2)}</TableCell>
                      <TableCell className="font-mono text-right">{formatAssetPrice(pos?.entry, pos?.symbol || "")}</TableCell>
                      <TableCell className="font-mono text-right">{pos?.current != null ? formatAssetPrice(pos.current, pos?.symbol || "") : "-"}</TableCell>
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
