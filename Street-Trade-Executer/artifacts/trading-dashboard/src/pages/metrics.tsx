import { useGetMetrics, useGetMetricsSummary, getGetMetricsQueryKey, getGetMetricsSummaryQueryKey } from "@workspace/api-client-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { LineChart, Line, BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, ReferenceLine } from "recharts";
import { cn } from "@/lib/utils";
import { format } from "date-fns";

export default function Metrics() {
  const { data: metrics, isLoading: loadingMetrics } = useGetMetrics({ days: 14 }, {
    query: { queryKey: getGetMetricsQueryKey({ days: 14 }) }
  });

  const { data: summary, isLoading: loadingSummary } = useGetMetricsSummary(undefined, {
    query: { queryKey: getGetMetricsSummaryQueryKey() }
  });

  const formatMoney = (val: number) => 
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val);

  return (
    <div className="flex flex-col h-full overflow-auto bg-background p-6 space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-foreground">Performance Metrics</h2>
        <p className="text-sm text-muted-foreground">Historical P&L, drawdown, and win rate analysis</p>
      </div>

      {loadingSummary || !summary ? (
        <Skeleton className="h-[120px] w-full" />
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <Card className="bg-card border-border">
            <CardContent className="p-4 space-y-1">
              <div className="text-xs text-muted-foreground uppercase tracking-wider">Total P&L</div>
              <div className={cn("text-xl font-mono font-bold", summary.totalPnl >= 0 ? "text-green-500" : "text-red-500")}>
                {summary.totalPnl > 0 ? "+" : ""}{formatMoney(summary.totalPnl)}
              </div>
            </CardContent>
          </Card>
          <Card className="bg-card border-border">
            <CardContent className="p-4 space-y-1">
              <div className="text-xs text-muted-foreground uppercase tracking-wider">Win Rate</div>
              <div className="text-xl font-mono font-bold text-primary">{summary.winRate.toFixed(1)}%</div>
            </CardContent>
          </Card>
          <Card className="bg-card border-border">
            <CardContent className="p-4 space-y-1">
              <div className="text-xs text-muted-foreground uppercase tracking-wider">Max Drawdown</div>
              <div className="text-xl font-mono font-bold text-red-500">{summary.maxDrawdown.toFixed(2)}%</div>
            </CardContent>
          </Card>
          <Card className="bg-card border-border">
            <CardContent className="p-4 space-y-1">
              <div className="text-xs text-muted-foreground uppercase tracking-wider">Best Trade</div>
              <div className="text-xl font-mono font-bold text-green-500">+{formatMoney(summary.bestTrade)}</div>
            </CardContent>
          </Card>
          <Card className="bg-card border-border">
            <CardContent className="p-4 space-y-1">
              <div className="text-xs text-muted-foreground uppercase tracking-wider">Trades (W/L)</div>
              <div className="text-xl font-mono font-bold">{summary.totalTrades} <span className="text-sm text-muted-foreground font-sans">({summary.winningTrades}/{summary.losingTrades})</span></div>
            </CardContent>
          </Card>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2 bg-card border-border">
          <CardHeader>
            <CardTitle className="text-sm font-semibold tracking-wide uppercase">Daily P&L History</CardTitle>
          </CardHeader>
          <CardContent>
            {loadingMetrics || !metrics ? (
              <Skeleton className="h-[300px] w-full" />
            ) : (
              <div className="h-[300px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={metrics} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                    <XAxis 
                      dataKey="tradingDate" 
                      tickFormatter={(val) => format(new Date(val), "MM/dd")} 
                      stroke="hsl(var(--muted-foreground))"
                      fontSize={12}
                      fontFamily="monospace"
                      tickLine={false}
                      axisLine={false}
                    />
                    <YAxis 
                      stroke="hsl(var(--muted-foreground))" 
                      fontSize={12}
                      fontFamily="monospace"
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(val) => `$${val}`}
                    />
                    <RechartsTooltip 
                      contentStyle={{ backgroundColor: 'hsl(var(--card))', borderColor: 'hsl(var(--border))', borderRadius: '4px' }}
                      itemStyle={{ fontFamily: 'monospace' }}
                      labelStyle={{ fontFamily: 'monospace', color: 'hsl(var(--muted-foreground))', marginBottom: '4px' }}
                      formatter={(value: number) => [formatMoney(value), "P&L"]}
                      labelFormatter={(label) => format(new Date(label as string), "MMM dd, yyyy")}
                    />
                    <ReferenceLine y={0} stroke="hsl(var(--muted-foreground))" strokeDasharray="3 3" />
                    <Bar 
                      dataKey="pnl" 
                      radius={[2, 2, 0, 0]}
                    >
                      {metrics.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.pnl >= 0 ? "hsl(var(--success))" : "hsl(var(--destructive))"} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="text-sm font-semibold tracking-wide uppercase">Recent Days (7D)</CardTitle>
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
                <TableHeader className="bg-muted/50">
                  <TableRow className="border-border hover:bg-transparent">
                    <TableHead className="font-mono text-xs">DATE</TableHead>
                    <TableHead className="font-mono text-xs text-center">TRADES</TableHead>
                    <TableHead className="font-mono text-xs text-right">P&L</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {metrics.slice(0, 7).map((m) => (
                    <TableRow key={m.tradingDate} className="border-border hover:bg-muted/30">
                      <TableCell className="font-mono text-xs text-muted-foreground">{format(new Date(m.tradingDate), "MM/dd")}</TableCell>
                      <TableCell className="font-mono text-xs text-center">{m.tradesToday}</TableCell>
                      <TableCell className={cn(
                        "font-mono text-xs text-right font-bold",
                        m.pnl >= 0 ? "text-green-500" : "text-red-500"
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
