import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { Activity, RefreshCw, RotateCcw } from "lucide-react";
import { cn, formatPktDateTime } from "@/lib/utils";
import { useLiveDashboard } from "@/hooks/use-ws";
import { useToast } from "@/hooks/use-toast";

interface DailyMetricRow {
  tradingDate: string;
  startEquity: number;
  currentEquity: number;
  maxDrawdownPercent: number;
  tradesToday: number;
  wins?: number;
  losses?: number;
  pnl: number;
}

interface EquityCurvePoint {
  label: string;
  pktTime: string;
  tradePnl: number;
  cumPnl: number;
  symbol: string;
  orderType: string;
}

interface RecentClosedTrade {
  symbol: string;
  orderType: string;
  lots: number;
  profit: number;
  closeTime: string;
  pktDate: string;
  comment: string;
}

interface LiveMetricsSummary {
  days: number;
  totalTrades: number;
  winningTrades: number;
  losingTrades: number;
  winRate: number;
  totalPnl: number;
  avgPnl: number;
  bestTrade: number;
  worstTrade: number;
  profitFactor: number;
  maxDrawdown: number;
  liveEquity: number;
  initialBalance?: number;
  maxEquityPeak?: number;
  overallDrawdown?: number;
  accountNetProfit?: number;
  accountNetPct?: number;
  dailyDrawdown?: number;
  floatingProfit: number;
  openTradesCount: number;
  mt5Login: number;
  systemStatus: string;
  lastHeartbeat: string | null;
  metricsResetAt?: string | null;
  equityCurve?: EquityCurvePoint[];
  recentTrades: RecentClosedTrade[];
}

const formatMoney = (val: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(val);

function formatShortPktDate(dateStr: string): string {
  const parts = String(dateStr).slice(0, 10).split("-");
  if (parts.length !== 3) return dateStr;
  return `${parts[2]}/${parts[1]}`;
}

function formatFullPktDate(dateStr: string): string {
  const parts = String(dateStr).slice(0, 10).split("-");
  if (parts.length !== 3) return dateStr;
  const [y, m, d] = parts.map(Number);
  const dt = new Date(Date.UTC(y!, m! - 1, d!));
  return (
    dt.toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      timeZone: "UTC",
    }) + " (PKT)"
  );
}

const CurveTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    const pt = payload[0]?.payload as EquityCurvePoint | undefined;
    if (!pt) return null;
    const isPos = pt.cumPnl >= 0;
    const isTradePos = pt.tradePnl >= 0;
    return (
      <div className="bg-background/95 backdrop-blur-md border border-border/80 p-3 rounded-lg shadow-2xl font-mono text-xs space-y-1">
        <p className="text-muted-foreground">
          {pt.label} {pt.symbol !== "BASELINE" ? `· ${pt.symbol} (${pt.orderType})` : ""}
        </p>
        {pt.pktTime && <p className="text-[10px] text-zinc-400">{pt.pktTime} PKT</p>}
        <p className={cn("font-bold text-sm", isPos ? "text-emerald-400" : "text-rose-400")}>
          Cumulative P&amp;L: {isPos ? "+" : ""}{formatMoney(pt.cumPnl)}
        </p>
        {pt.symbol !== "BASELINE" && (
          <p className={cn("text-[11px]", isTradePos ? "text-emerald-400" : "text-rose-400")}>
            Trade P&amp;L: {isTradePos ? "+" : ""}{formatMoney(pt.tradePnl)}
          </p>
        )}
      </div>
    );
  }
  return null;
};

const BarTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    const row = payload[0]?.payload as DailyMetricRow | undefined;
    if (!row) return null;
    const isPos = row.pnl >= 0;
    return (
      <div className="bg-background/95 backdrop-blur-md border border-border/80 p-3 rounded-lg shadow-2xl font-mono text-xs space-y-1">
        <p className="text-muted-foreground">{formatFullPktDate(String(label))}</p>
        <p className={cn("font-bold text-sm", isPos ? "text-emerald-400" : "text-rose-400")}>
          Realized P&amp;L: {isPos ? "+" : ""}{formatMoney(row.pnl)}
        </p>
        <p className="text-[11px] text-zinc-400">
          Trades: {row.tradesToday} ({row.wins ?? 0}W / {row.losses ?? 0}L) · DD: {row.maxDrawdownPercent.toFixed(2)}%
        </p>
      </div>
    );
  }
  return null;
};

const PERIOD_OPTIONS = [
  { label: "7D", days: 7 },
  { label: "14D", days: 14 },
  { label: "30D", days: 30 },
  { label: "ALL", days: 0 },
];

export default function Metrics() {
  const [days, setDays] = useState<number>(30);
  const [chartView, setChartView] = useState<"curve" | "bars">("curve");
  const [isResetting, setIsResetting] = useState(false);
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const { data: wsData, wsConnected } = useLiveDashboard();
  const isReadOnly = localStorage.getItem("wasee_role")?.toLowerCase() === "user";

  const { data: metrics, isLoading: loadingMetrics, isError: errorMetrics, refetch: refetchMetrics } = useQuery<DailyMetricRow[]>({
    queryKey: ["live-metrics", days],
    queryFn: async () => {
      const res = await fetch(`/api/metrics?days=${days}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    refetchInterval: 2500,
  });

  const { data: summary, isLoading: loadingSummary, isError: errorSummary, refetch: refetchSummary } = useQuery<LiveMetricsSummary>({
    queryKey: ["live-metrics-summary", days],
    queryFn: async () => {
      const res = await fetch(`/api/metrics/summary?days=${days}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    refetchInterval: 2500,
  });

  // Refresh immediately when MT5 account switches or trades open/close on WebSocket
  const firstTradeTicket = wsData?.recentTrades?.[0]?.ticket;
  const firstTradeStatus = wsData?.recentTrades?.[0]?.status;
  useEffect(() => {
    if (!wsData) return;
    void queryClient.invalidateQueries({ queryKey: ["live-metrics"] });
    void queryClient.invalidateQueries({ queryKey: ["live-metrics-summary"] });
  }, [wsData?.mt5Login, wsData?.tradesToday, wsData?.activePositions?.length, firstTradeTicket, firstTradeStatus, queryClient]);

  const handleResetMetrics = async () => {
    if (isReadOnly || isResetting) return;
    if (!window.confirm("Clear old Performance Metrics history and start fresh from the next trade?")) return;
    setIsResetting(true);
    try {
      const res = await fetch("/api/metrics/reset", { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["live-metrics"] }),
        queryClient.invalidateQueries({ queryKey: ["live-metrics-summary"] }),
      ]);
      toast({
        title: "Metrics Blanked Cleanly",
        description: "Starting fresh — all stats & P&L Curve will dynamically track from the next executed trade.",
      });
    } catch (e: any) {
      toast({
        title: "Failed to reset metrics",
        description: e?.message || "Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsResetting(false);
    }
  };

  const liveEq = wsData?.equity ?? summary?.liveEquity ?? 0;
  const liveInitial = wsData?.initialBalance ?? summary?.initialBalance ?? 10000;
  const liveAccountNetProfit = liveInitial > 0 ? Number((liveEq - liveInitial).toFixed(2)) : (summary?.accountNetProfit ?? 0);
  const liveAccountNetPct = liveInitial > 0 ? Number(((liveAccountNetProfit / liveInitial) * 100).toFixed(2)) : (summary?.accountNetPct ?? 0);
  const liveOverallDd = wsData?.overallDrawdown ?? summary?.overallDrawdown ?? 0;
  const liveDailyDd = wsData?.drawdownPercent ?? summary?.dailyDrawdown ?? 0;
  const liveFloat = wsData?.floatingProfit ?? summary?.floatingProfit ?? 0;
  const mt5Login = wsData?.mt5Login ?? summary?.mt5Login ?? 0;

  const rawCurve = summary?.equityCurve ?? [];
  const hasRealTrades = rawCurve.length > 0;
  const curveData: EquityCurvePoint[] = hasRealTrades
    ? rawCurve
    : [
        { label: "Baseline", pktTime: "", tradePnl: 0, cumPnl: 0, symbol: "BASELINE", orderType: "BASE" },
        { label: "Next Trade", pktTime: "", tradePnl: 0, cumPnl: 0, symbol: "BASELINE", orderType: "BASE" },
      ];
  const curveStroke = (summary?.totalPnl ?? 0) >= 0 ? "#10B981" : "#F43F5E";

  const barData = (metrics ? [...metrics].reverse() : []).map((d) => ({
    ...d,
    winPnl: d.pnl >= 0 ? d.pnl : 0,
    lossPnl: d.pnl < 0 ? d.pnl : 0,
  }));

  return (
    <div className="flex flex-col h-full overflow-auto bg-background p-3 sm:p-6 space-y-4 sm:space-y-6 w-full max-w-[1600px] mx-auto">
      {/* Header + Period Switch + Reset + Live Sync Status */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
        <div className="space-y-1">
          <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground">Performance Metrics</h2>
          <p className="text-xs sm:text-sm text-muted-foreground font-sans">
            Real-time synchronized P&amp;L curve, drawdown, and win rate from executed MT5 trades (PKT Timezone)
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Badge
            variant="outline"
            className={cn(
              "font-mono text-[10px] px-2.5 py-1 flex items-center gap-1.5",
              wsConnected
                ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                : "bg-sky-500/10 text-sky-400 border-sky-500/30"
            )}
          >
            <Activity className="h-3 w-3 animate-pulse" />
            {wsConnected ? "LIVE WS + 2.5s SYNC" : "2.5s LIVE POLL"}
            {mt5Login > 0 ? ` · #${mt5Login}` : ""}
          </Badge>

          {summary?.metricsResetAt && (
            <Badge variant="outline" className="font-mono text-[10px] px-2 py-1 border-zinc-700 text-zinc-400">
              Clean From: {formatPktDateTime(summary.metricsResetAt).replace(/^[^,]+,\s*/, "")}
            </Badge>
          )}

          <div className="flex items-center bg-zinc-900 border border-zinc-800 rounded-md p-0.5">
            {PERIOD_OPTIONS.map((opt) => (
              <button
                key={opt.days}
                type="button"
                onClick={() => setDays(opt.days)}
                className={cn(
                  "px-2.5 py-1 rounded-sm font-mono text-[11px] font-bold transition-colors",
                  days === opt.days
                    ? "bg-primary text-primary-foreground"
                    : "text-zinc-400 hover:text-foreground"
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {!isReadOnly && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={isResetting}
              onClick={handleResetMetrics}
              className="h-7 px-2.5 font-mono text-[11px] border-rose-500/30 text-rose-300 hover:bg-rose-500/15"
              title="Blank historical metrics and track fresh from the next trade"
            >
              <RotateCcw className="h-3 w-3 mr-1" />
              Reset / Blank
            </Button>
          )}

          <button
            type="button"
            onClick={() => {
              void refetchMetrics();
              void refetchSummary();
            }}
            className="p-1.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-foreground"
            title="Refresh Now"
          >
            <RefreshCw className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Live Account & Floating Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <Card className="bg-zinc-900/60 border-zinc-800">
          <CardContent className="p-3 sm:p-4 space-y-1">
            <div className="text-[10px] text-zinc-500 uppercase tracking-widest font-mono">Live MT5 Equity</div>
            <div className="text-lg sm:text-xl font-mono font-bold text-sky-400">{formatMoney(liveEq)}</div>
            <div className="text-[10px] text-zinc-500 font-mono">Base: {formatMoney(liveInitial)}</div>
          </CardContent>
        </Card>
        <Card className="bg-zinc-900/60 border-zinc-800">
          <CardContent className="p-3 sm:p-4 space-y-1">
            <div className="text-[10px] text-zinc-500 uppercase tracking-widest font-mono">Account Net / DD</div>
            <div className={cn("text-base sm:text-lg font-mono font-bold", liveAccountNetProfit >= 0 ? "text-emerald-400" : "text-amber-400")}>
              {liveAccountNetProfit > 0 ? "+" : ""}{formatMoney(liveAccountNetProfit)}{" "}
              <span className="text-xs">({liveAccountNetPct > 0 ? "+" : ""}{liveAccountNetPct.toFixed(2)}%)</span>
            </div>
            <div className="text-[10px] text-zinc-400 font-mono">
              Daily DD: <span className="text-rose-400 font-bold">{liveDailyDd.toFixed(2)}%</span> · Overall: <span className="text-rose-400 font-bold">{liveOverallDd.toFixed(2)}%</span>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-zinc-900/60 border-zinc-800">
          <CardContent className="p-3 sm:p-4 space-y-1">
            <div className="text-[10px] text-zinc-500 uppercase tracking-widest font-mono">Floating Open P&amp;L</div>
            <div className={cn("text-lg sm:text-xl font-mono font-bold", liveFloat >= 0 ? "text-emerald-400" : "text-rose-400")}>
              {liveFloat > 0 ? "+" : ""}{formatMoney(liveFloat)}
            </div>
          </CardContent>
        </Card>
        <Card className="bg-zinc-900/60 border-zinc-800">
          <CardContent className="p-3 sm:p-4 space-y-1">
            <div className="text-[10px] text-zinc-500 uppercase tracking-widest font-mono">Profit Factor ({days === 0 ? "ALL" : `${days}D`})</div>
            <div className="text-lg sm:text-xl font-mono font-bold text-cyan-400">{summary ? summary.profitFactor.toFixed(2) : "—"}</div>
          </CardContent>
        </Card>
        <Card className="col-span-2 sm:col-span-1 bg-zinc-900/60 border-zinc-800">
          <CardContent className="p-3 sm:p-4 space-y-1">
            <div className="text-[10px] text-zinc-500 uppercase tracking-widest font-mono">Avg Trade P&amp;L</div>
            <div className={cn("text-lg sm:text-xl font-mono font-bold", (summary?.avgPnl ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400")}>
              {summary ? `${summary.avgPnl > 0 ? "+" : ""}${formatMoney(summary.avgPnl)}` : "—"}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Period Realized KPI Summary */}
      {errorSummary ? (
        <Card className="bg-rose-500/5 border-rose-500/30 p-4 text-xs font-mono text-rose-400">
          Could not load realized trade summary right now. Click refresh to retry.
        </Card>
      ) : loadingSummary || !summary ? (
        <Skeleton className="h-[110px] w-full" />
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 sm:gap-4">
          <Card className="bg-card/40 border-border/80 backdrop-blur-sm shadow-md transition-all hover:border-emerald-500/30">
            <CardContent className="p-3 sm:p-4 space-y-1">
              <div className="text-[10px] text-muted-foreground uppercase tracking-widest font-mono">
                Realized P&amp;L ({days === 0 ? "ALL" : `${days}D`})
              </div>
              <div className={cn("text-lg sm:text-xl font-mono font-bold", summary.totalPnl >= 0 ? "text-emerald-400" : "text-rose-400")}>
                {summary.totalPnl > 0 ? "+" : ""}{formatMoney(summary.totalPnl)}
              </div>
            </CardContent>
          </Card>
          <Card className="bg-card/40 border-border/80 backdrop-blur-sm shadow-md transition-all hover:border-indigo-500/30">
            <CardContent className="p-3 sm:p-4 space-y-1">
              <div className="text-[10px] text-muted-foreground uppercase tracking-widest font-mono">Win Rate</div>
              <div className="text-lg sm:text-xl font-mono font-bold text-indigo-400">{summary.winRate.toFixed(1)}%</div>
            </CardContent>
          </Card>
          <Card className="bg-card/40 border-border/80 backdrop-blur-sm shadow-md transition-all hover:border-rose-500/30">
            <CardContent className="p-3 sm:p-4 space-y-1">
              <div className="text-[10px] text-muted-foreground uppercase tracking-widest font-mono">Max Drawdown</div>
              <div className="text-lg sm:text-xl font-mono font-bold text-rose-500">{summary.maxDrawdown.toFixed(2)}%</div>
            </CardContent>
          </Card>
          <Card className="bg-card/40 border-border/80 backdrop-blur-sm shadow-md transition-all hover:border-emerald-500/30">
            <CardContent className="p-3 sm:p-4 space-y-1">
              <div className="text-[10px] text-muted-foreground uppercase tracking-widest font-mono">Best / Worst</div>
              <div className="text-sm sm:text-base font-mono font-bold text-emerald-400 truncate">
                {summary.bestTrade > 0 ? "+" : ""}{formatMoney(summary.bestTrade)}{" "}
                <span className="text-rose-400 text-xs">/ {formatMoney(summary.worstTrade)}</span>
              </div>
            </CardContent>
          </Card>
          <Card className="col-span-2 md:col-span-1 bg-card/40 border-border/80 backdrop-blur-sm shadow-md transition-all hover:border-border">
            <CardContent className="p-3 sm:p-4 space-y-1">
              <div className="text-[10px] text-muted-foreground uppercase tracking-widest font-mono">Trades (W/L)</div>
              <div className="text-lg sm:text-xl font-mono font-bold text-foreground/90">
                {summary.totalTrades}{" "}
                <span className="text-xs text-muted-foreground font-sans">
                  ({summary.winningTrades}W / {summary.losingTrades}L)
                </span>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Realized P&L Curve / Daily Bars + Recent Active Trading Days Table */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
        <Card className="lg:col-span-2 bg-card/30 border-border/80 backdrop-blur-sm shadow-lg">
          <CardHeader className="p-4 sm:p-6 pb-2 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
            <div>
              <CardTitle className="text-xs font-semibold tracking-wider font-mono uppercase text-muted-foreground">
                {chartView === "curve"
                  ? "Realized P&L Curve (Live Closed Trades · PKT)"
                  : "Daily P&L History (Real Closed Trades · PKT)"}
              </CardTitle>
              <CardDescription className="text-[11px]">
                {hasRealTrades
                  ? `Showing ${summary?.totalTrades ?? 0} real closed setup(s) dynamically from MT5 DB`
                  : "Clean baseline active ($0.00) — curve & metrics update automatically on next trade"}
              </CardDescription>
            </div>
            <div className="flex items-center bg-zinc-900 border border-zinc-800 rounded-md p-0.5 self-start">
              <button
                type="button"
                onClick={() => setChartView("curve")}
                className={cn(
                  "px-2.5 py-1 rounded-sm font-mono text-[10px] font-bold transition-colors",
                  chartView === "curve" ? "bg-emerald-600 text-white" : "text-zinc-400 hover:text-foreground"
                )}
              >
                P&amp;L Curve
              </button>
              <button
                type="button"
                onClick={() => setChartView("bars")}
                className={cn(
                  "px-2.5 py-1 rounded-sm font-mono text-[10px] font-bold transition-colors",
                  chartView === "bars" ? "bg-sky-600 text-white" : "text-zinc-400 hover:text-foreground"
                )}
              >
                Daily Bars
              </button>
            </div>
          </CardHeader>
          <CardContent className="p-3 sm:p-6 pt-0">
            {errorMetrics || errorSummary ? (
              <div className="h-[280px] flex items-center justify-center text-xs font-mono text-rose-400">
                Failed to load P&amp;L chart data.
              </div>
            ) : loadingMetrics || loadingSummary ? (
              <Skeleton className="h-[280px] w-full" />
            ) : chartView === "curve" ? (
              <div className="w-full" style={{ height: 280 }}>
                <ResponsiveContainer width="100%" height={280}>
                  <AreaChart data={curveData} margin={{ top: 14, right: 16, left: -8, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                    <XAxis
                      dataKey="label"
                      stroke="#71717a"
                      fontSize={11}
                      fontFamily="monospace"
                      tickLine={false}
                      axisLine={false}
                      dy={8}
                    />
                    <YAxis
                      stroke="#71717a"
                      fontSize={11}
                      fontFamily="monospace"
                      tickLine={false}
                      axisLine={false}
                      domain={hasRealTrades ? ["auto", "auto"] : [-50, 50]}
                      tickFormatter={(val) => `$${val}`}
                    />
                    <RechartsTooltip content={<CurveTooltip />} />
                    <ReferenceLine y={0} stroke="#52525b" strokeDasharray="3 3" />
                    <Area
                      type="monotone"
                      dataKey="cumPnl"
                      stroke={hasRealTrades ? curveStroke : "#38bdf8"}
                      strokeWidth={2.5}
                      fill={hasRealTrades ? curveStroke : "#38bdf8"}
                      fillOpacity={0.16}
                      dot={hasRealTrades ? { r: 3.5, fill: curveStroke } : { r: 3, fill: "#38bdf8" }}
                      activeDot={{ r: 5 }}
                      isAnimationActive={false}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            ) : barData.length === 0 ? (
              <div className="h-[280px] flex items-center justify-center text-xs font-mono text-muted-foreground">
                No closed trades since clean reset — waiting for next executed trade.
              </div>
            ) : (
              <div className="w-full" style={{ height: 280 }}>
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={barData} margin={{ top: 14, right: 16, left: -8, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                    <XAxis
                      dataKey="tradingDate"
                      tickFormatter={formatShortPktDate}
                      stroke="#71717a"
                      fontSize={11}
                      fontFamily="monospace"
                      tickLine={false}
                      axisLine={false}
                      dy={8}
                    />
                    <YAxis
                      stroke="#71717a"
                      fontSize={11}
                      fontFamily="monospace"
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(val) => `$${val}`}
                    />
                    <RechartsTooltip content={<BarTooltip />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
                    <ReferenceLine y={0} stroke="#52525b" strokeDasharray="3 3" />
                    <Bar dataKey="winPnl" fill="#10B981" radius={[4, 4, 0, 0]} maxBarSize={42} isAnimationActive={false} />
                    <Bar dataKey="lossPnl" fill="#F43F5E" radius={[0, 0, 4, 4]} maxBarSize={42} isAnimationActive={false} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="bg-card/30 border-border/80 backdrop-blur-sm shadow-lg">
          <CardHeader className="p-4 sm:p-6 pb-2">
            <CardTitle className="text-xs font-semibold tracking-wider font-mono uppercase text-muted-foreground">
              Recent Days ({days === 0 ? "ALL" : `${days}D`})
            </CardTitle>
            <CardDescription className="text-[11px]">
              Exact sum of post-reset closed trades per PKT date
            </CardDescription>
          </CardHeader>
          <CardContent className="p-0 max-h-[320px] overflow-y-auto">
            {loadingMetrics || !metrics ? (
              <div className="p-6 space-y-4">
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-8 w-full" />
              </div>
            ) : metrics.length === 0 ? (
              <div className="p-6 text-center text-xs font-mono text-muted-foreground">
                Clean baseline active — waiting for next closed trade.
              </div>
            ) : (
              <Table>
                <TableHeader className="bg-muted/40 sticky top-0">
                  <TableRow className="border-border hover:bg-transparent">
                    <TableHead className="font-mono text-[10px] tracking-widest uppercase">DATE (PKT)</TableHead>
                    <TableHead className="font-mono text-[10px] tracking-widest text-center uppercase">TRADES</TableHead>
                    <TableHead className="font-mono text-[10px] tracking-widest text-right uppercase">DD%</TableHead>
                    <TableHead className="font-mono text-[10px] tracking-widest text-right uppercase">P&amp;L</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {metrics.map((m) => (
                    <TableRow key={m.tradingDate} className="border-border hover:bg-muted/30 transition-colors">
                      <TableCell className="font-mono text-xs text-muted-foreground whitespace-nowrap">
                        {formatShortPktDate(m.tradingDate)}
                      </TableCell>
                      <TableCell className="font-mono text-xs text-center whitespace-nowrap">
                        {m.tradesToday}
                        {m.wins !== undefined && m.losses !== undefined && m.tradesToday > 0 && (
                          <span className="text-[10px] text-zinc-500 ml-1">
                            ({m.wins}W/{m.losses}L)
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="font-mono text-[11px] text-right text-amber-400">
                        {m.maxDrawdownPercent.toFixed(2)}%
                      </TableCell>
                      <TableCell
                        className={cn(
                          "font-mono text-xs text-right font-bold whitespace-nowrap",
                          m.pnl >= 0 ? "text-emerald-400" : "text-rose-400"
                        )}
                      >
                        {m.pnl > 0 ? "+" : ""}{formatMoney(m.pnl)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Live Audit Feed: Exact Real Closed Trades Since Reset */}
      {summary?.recentTrades && summary.recentTrades.length > 0 && (
        <Card className="bg-card/30 border-border/80 backdrop-blur-sm shadow-lg">
          <CardHeader className="p-4 sm:p-6 pb-2">
            <CardTitle className="text-xs font-semibold tracking-wider font-mono uppercase text-muted-foreground">
              Verified Closed Trades Feed (Latest {summary.recentTrades.length})
            </CardTitle>
            <CardDescription className="text-[11px]">
              Every metric &amp; curve point above is dynamically calculated from these closed MT5 records
            </CardDescription>
          </CardHeader>
          <CardContent className="p-0 max-h-[300px] overflow-y-auto">
            <Table>
              <TableHeader className="bg-muted/40 sticky top-0">
                <TableRow className="border-border hover:bg-transparent">
                  <TableHead className="font-mono text-[10px] uppercase whitespace-nowrap">CLOSE TIME (PKT)</TableHead>
                  <TableHead className="font-mono text-[10px] uppercase">SYMBOL</TableHead>
                  <TableHead className="font-mono text-[10px] uppercase">SIDE</TableHead>
                  <TableHead className="font-mono text-[10px] uppercase text-right">LOTS</TableHead>
                  <TableHead className="font-mono text-[10px] uppercase">SOURCE</TableHead>
                  <TableHead className="font-mono text-[10px] uppercase text-right">REALIZED P&amp;L</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {summary.recentTrades.map((t, idx) => (
                  <TableRow key={idx} className="border-border hover:bg-muted/30">
                    <TableCell className="font-mono text-[11px] text-muted-foreground whitespace-nowrap">
                      {formatPktDateTime(t.closeTime)}
                    </TableCell>
                    <TableCell className="font-mono text-xs font-bold">{t.symbol}</TableCell>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className={cn(
                          "rounded-sm text-[9px] font-mono px-1.5 py-0 font-bold",
                          t.orderType === "BUY"
                            ? "bg-green-500/10 text-green-400 border-green-500/30"
                            : "bg-red-500/10 text-red-400 border-red-500/30"
                        )}
                      >
                        {t.orderType}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-mono text-xs text-right">{t.lots.toFixed(2)}</TableCell>
                    <TableCell className="font-mono text-[10px] text-zinc-400 whitespace-nowrap">{t.comment || "MT5"}</TableCell>
                    <TableCell
                      className={cn(
                        "font-mono text-xs text-right font-bold whitespace-nowrap",
                        t.profit >= 0 ? "text-emerald-400" : "text-rose-400"
                      )}
                    >
                      {t.profit > 0 ? "+" : ""}{formatMoney(t.profit)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
