import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, ReferenceLine } from "recharts";
import { Activity, RefreshCw } from "lucide-react";
import { cn, formatPktDateTime } from "@/lib/utils";
import { useLiveDashboard } from "@/hooks/use-ws";

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
  floatingProfit: number;
  openTradesCount: number;
  mt5Login: number;
  systemStatus: string;
  lastHeartbeat: string | null;
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
  return dt.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }) + " (PKT)";
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    const row = payload[0]?.payload as DailyMetricRow | undefined;
    const pnl = Number(payload[0]?.value ?? 0);
    const isPos = pnl >= 0;
    return (
      <div className="bg-background/95 backdrop-blur-md border border-border/80 p-3 rounded-lg shadow-2xl font-mono text-xs space-y-1">
        <p className="text-muted-foreground">{formatFullPktDate(String(label))}</p>
        <p className={cn("font-bold text-sm", isPos ? "text-emerald-400" : "text-rose-400")}>
          Realized P&amp;L: {isPos ? "+" : ""}{formatMoney(pnl)}
        </p>
        {row && (
          <p className="text-[11px] text-zinc-400">
            Trades: {row.tradesToday} ({row.wins ?? 0}W / {row.losses ?? 0}L) · DD: {row.maxDrawdownPercent.toFixed(2)}%
          </p>
        )}
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
  const queryClient = useQueryClient();
  const { data: wsData, wsConnected } = useLiveDashboard();

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

  // Trigger instant refresh whenever live WebSocket reports trade count / equity change
  useEffect(() => {
    if (!wsData) return;
    void queryClient.invalidateQueries({ queryKey: ["live-metrics"] });
    void queryClient.invalidateQueries({ queryKey: ["live-metrics-summary"] });
  }, [wsData?.tradesToday, wsData?.activePositions?.length, wsData?.recentTrades?.length, wsData?.equity, queryClient]);

  const chartData = metrics ? [...metrics].reverse() : [];
  const liveEq = wsData?.equity ?? summary?.liveEquity ?? 0;
  const liveFloat = wsData?.floatingProfit ?? summary?.floatingProfit ?? 0;
  const mt5Login = wsData?.mt5Login ?? summary?.mt5Login ?? 0;

  return (
    <div className="flex flex-col h-full overflow-auto bg-background p-3 sm:p-6 space-y-4 sm:space-y-6 w-full max-w-[1600px] mx-auto">
      {/* Header + Period Switch + Live Sync Status */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
        <div className="space-y-1">
          <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground">Performance Metrics</h2>
          <p className="text-xs sm:text-sm text-muted-foreground font-sans">
            Real-time synchronized P&amp;L, drawdown, and win rate from executed MT5 trades (PKT Timezone)
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
            {wsConnected ? "WS REAL-TIME SYNC" : "LIVE POLLING (2.5s)"}
            {mt5Login > 0 && ` · #${mt5Login}`}
          </Badge>

          <div className="flex items-center gap-1 bg-zinc-900 border border-zinc-800 rounded p-0.5">
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
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Card className="bg-zinc-900/60 border-zinc-800">
          <CardContent className="p-3 sm:p-4 space-y-1">
            <div className="text-[10px] text-zinc-500 uppercase tracking-widest font-mono">Live MT5 Equity</div>
            <div className="text-lg sm:text-xl font-mono font-bold text-sky-400">{formatMoney(liveEq)}</div>
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
        <Card className="bg-zinc-900/60 border-zinc-800">
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
                +{formatMoney(summary.bestTrade)}{" "}
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

      {/* Daily P&L Chart + Recent Active Trading Days Table */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
        <Card className="lg:col-span-2 bg-card/30 border-border/80 backdrop-blur-sm shadow-lg">
          <CardHeader className="p-4 sm:p-6 pb-2">
            <CardTitle className="text-xs font-semibold tracking-wider font-mono uppercase text-muted-foreground">
              Daily P&amp;L History (Real Closed Trades · PKT)
            </CardTitle>
          </CardHeader>
          <CardContent className="p-3 sm:p-6 pt-0">
            {errorMetrics ? (
              <div className="h-[280px] flex items-center justify-center text-xs font-mono text-rose-400">
                Failed to load Daily P&amp;L History.
              </div>
            ) : loadingMetrics || !metrics ? (
              <Skeleton className="h-[280px] w-full" />
            ) : chartData.length === 0 ? (
              <div className="h-[280px] flex items-center justify-center text-xs font-mono text-muted-foreground">
                No closed trades recorded in selected period ({days === 0 ? "ALL" : `${days}D`}).
              </div>
            ) : (
              <div className="h-[280px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} margin={{ top: 10, right: 10, left: -12, bottom: 0 }}>
                    <defs>
                      <linearGradient id="colorProfit" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#10B981" stopOpacity={0.85} />
                        <stop offset="100%" stopColor="#059669" stopOpacity={0.25} />
                      </linearGradient>
                      <linearGradient id="colorLoss" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#F43F5E" stopOpacity={0.85} />
                        <stop offset="100%" stopColor="#E11D48" stopOpacity={0.25} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.3} vertical={false} />
                    <XAxis
                      dataKey="tradingDate"
                      tickFormatter={formatShortPktDate}
                      stroke="hsl(var(--muted-foreground))"
                      fontSize={11}
                      fontFamily="monospace"
                      tickLine={false}
                      axisLine={false}
                      dy={10}
                    />
                    <YAxis
                      stroke="hsl(var(--muted-foreground))"
                      fontSize={11}
                      fontFamily="monospace"
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(val) => `$${val}`}
                      dx={-5}
                    />
                    <RechartsTooltip content={<CustomTooltip />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
                    <ReferenceLine y={0} stroke="hsl(var(--muted-foreground))" opacity={0.4} strokeDasharray="3 3" />
                    <Bar dataKey="pnl" radius={[4, 4, 0, 0]} maxBarSize={45}>
                      {chartData.map((entry, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={entry.pnl >= 0 ? "url(#colorProfit)" : "url(#colorLoss)"}
                          className="transition-all duration-300 hover:opacity-90 cursor-pointer"
                        />
                      ))}
                    </Bar>
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
              Exact sum of closed trades per PKT date
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
                No trading activity in selected period.
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

      {/* Live Audit Feed: Exact Real Closed Trades Backing These Metrics */}
      {summary?.recentTrades && summary.recentTrades.length > 0 && (
        <Card className="bg-card/30 border-border/80 backdrop-blur-sm shadow-lg">
          <CardHeader className="p-4 sm:p-6 pb-2">
            <CardTitle className="text-xs font-semibold tracking-wider font-mono uppercase text-muted-foreground">
              Verified Closed Trades Feed (Latest {summary.recentTrades.length} in Window)
            </CardTitle>
            <CardDescription className="text-[11px]">
              Every metric above is dynamically summed directly from these executed MT5 database records
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
