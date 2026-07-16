import { useGetMetrics, useGetMetricsSummary, getGetMetricsQueryKey, getGetMetricsSummaryQueryKey } from "@workspace/api-client-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, ReferenceLine } from "recharts";
import { cn } from "@/lib/utils";
import { format } from "date-fns";

const formatMoney = (val: number) => 
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val);

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    const pnl = payload[0].value;
    const isPos = pnl >= 0;
    return (
      <div className="bg-background/95 backdrop-blur-md border border-border/80 p-3 rounded-lg shadow-2xl font-mono text-xs space-y-1">
        <p className="text-muted-foreground">{format(new Date(label as string), "MMMM dd, yyyy")}</p>
        <p className={cn("font-bold text-sm", isPos ? "text-emerald-400" : "text-rose-400")}>
          P&L: {isPos ? "+" : ""}{formatMoney(pnl)}
        </p>
      </div>
    );
  }
  return null;
};

export default function Metrics() {
  const { data: metrics, isLoading: loadingMetrics } = useGetMetrics({ days: 14 }, {
    query: { queryKey: getGetMetricsQueryKey({ days: 14 }) }
  });

  const { data: summary, isLoading: loadingSummary } = useGetMetricsSummary({
    query: { queryKey: getGetMetricsSummaryQueryKey() }
  });

  return (
    <div className="flex flex-col h-full overflow-auto bg-background p-6 space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-foreground">Performance Metrics</h2>
        <p className="text-sm text-muted-foreground font-sans">Historical P&L, drawdown, and win rate analysis</p>
      </div>

      {loadingSummary || !summary ? (
        <Skeleton className="h-[120px] w-full" />
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <Card className="bg-card/40 border-border/80 backdrop-blur-sm shadow-md transition-all hover:border-emerald-500/30">
            <CardContent className="p-4 space-y-1">
              <div className="text-[10px] text-muted-foreground uppercase tracking-widest font-mono">Total P&L</div>
              <div className={cn("text-xl font-mono font-bold", summary.totalPnl >= 0 ? "text-emerald-400" : "text-rose-400")}>
                {summary.totalPnl > 0 ? "+" : ""}{formatMoney(summary.totalPnl)}
              </div>
            </CardContent>
          </Card>
          <Card className="bg-card/40 border-border/80 backdrop-blur-sm shadow-md transition-all hover:border-indigo-500/30">
            <CardContent className="p-4 space-y-1">
              <div className="text-[10px] text-muted-foreground uppercase tracking-widest font-mono">Win Rate</div>
              <div className="text-xl font-mono font-bold text-indigo-400">{summary.winRate.toFixed(1)}%</div>
            </CardContent>
          </Card>
          <Card className="bg-card/40 border-border/80 backdrop-blur-sm shadow-md transition-all hover:border-rose-500/30">
            <CardContent className="p-4 space-y-1">
              <div className="text-[10px] text-muted-foreground uppercase tracking-widest font-mono">Max Drawdown</div>
              <div className="text-xl font-mono font-bold text-rose-500">{summary.maxDrawdown.toFixed(2)}%</div>
            </CardContent>
          </Card>
          <Card className="bg-card/40 border-border/80 backdrop-blur-sm shadow-md transition-all hover:border-emerald-500/30">
            <CardContent className="p-4 space-y-1">
              <div className="text-[10px] text-muted-foreground uppercase tracking-widest font-mono">Best Trade</div>
              <div className="text-xl font-mono font-bold text-emerald-400">+{formatMoney(summary.bestTrade)}</div>
            </CardContent>
          </Card>
          <Card className="bg-card/40 border-border/80 backdrop-blur-sm shadow-md transition-all hover:border-border">
            <CardContent className="p-4 space-y-1">
              <div className="text-[10px] text-muted-foreground uppercase tracking-widest font-mono">Trades (W/L)</div>
              <div className="text-xl font-mono font-bold text-foreground/90">{summary.totalTrades} <span className="text-xs text-muted-foreground font-sans">({summary.winningTrades}/{summary.losingTrades})</span></div>
            </CardContent>
          </Card>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2 bg-card/30 border-border/80 backdrop-blur-sm shadow-lg">
          <CardHeader>
            <CardTitle className="text-xs font-semibold tracking-wider font-mono uppercase text-muted-foreground">Daily P&L History</CardTitle>
          </CardHeader>
          <CardContent>
            {loadingMetrics || !metrics ? (
              <Skeleton className="h-[300px] w-full" />
            ) : (
              <div className="h-[300px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={metrics} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="colorProfit" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#10B981" stopOpacity={0.85}/>
                        <stop offset="100%" stopColor="#059669" stopOpacity={0.25}/>
                      </linearGradient>
                      <linearGradient id="colorLoss" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#F43F5E" stopOpacity={0.85}/>
                        <stop offset="100%" stopColor="#E11D48" stopOpacity={0.25}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.3} vertical={false} />
                    <XAxis 
                      dataKey="tradingDate" 
                      tickFormatter={(val) => format(new Date(val), "MM/dd")} 
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
                    <RechartsTooltip 
                      content={<CustomTooltip />}
                      cursor={{ fill: 'rgba(255,255,255,0.03)' }}
                    />
                    <ReferenceLine y={0} stroke="hsl(var(--muted-foreground))" opacity={0.4} strokeDasharray="3 3" />
                    <Bar 
                      dataKey="pnl" 
                      radius={[4, 4, 0, 0]}
                      maxBarSize={45}
                    >
                      {metrics.map((entry, index) => (
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
          <CardHeader>
            <CardTitle className="text-xs font-semibold tracking-wider font-mono uppercase text-muted-foreground">Recent Days (7D)</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {loadingMetrics || !metrics ? (
              <div className="p-6 space-y-4">
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-8 w-full" />
              </div>
            ) : (
              <Table>
                <TableHeader className="bg-muted/40">
                  <TableRow className="border-border hover:bg-transparent">
                    <TableHead className="font-mono text-[10px] tracking-widest uppercase">DATE</TableHead>
                    <TableHead className="font-mono text-[10px] tracking-widest text-center uppercase">TRADES</TableHead>
                    <TableHead className="font-mono text-[10px] tracking-widest text-right uppercase">P&L</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {metrics.slice(0, 7).map((m) => (
                    <TableRow key={m.tradingDate} className="border-border hover:bg-muted/30 transition-colors">
                      <TableCell className="font-mono text-xs text-muted-foreground">{format(new Date(m.tradingDate), "MM/dd")}</TableCell>
                      <TableCell className="font-mono text-xs text-center">{m.tradesToday}</TableCell>
                      <TableCell className={cn(
                        "font-mono text-xs text-right font-bold",
                        m.pnl >= 0 ? "text-emerald-400" : "text-rose-400"
                      )}>
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
    </div>
  );
}
