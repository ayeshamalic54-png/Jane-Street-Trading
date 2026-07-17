import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { Play, TrendingUp, Award, DollarSign, Activity, AlertCircle } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";

interface TradeSim {
  type: string;
  entryPriceA: number;
  exitPriceA: number;
  entryPriceB: number;
  exitPriceB: number;
  beta: number;
  zScoreAtExit: number;
  profitPercent: number;
  profitAmount: number;
  reason: string;
  time: string;
}

interface BacktestResponse {
  symbolA: string;
  symbolB: string;
  totalTrades: number;
  wins: number;
  losses: number;
  winRate: number;
  initialBalance: number;
  finalBalance: number;
  netProfit: number;
  profitFactor: number;
  equityCurve: Array<{ time: string; balance: number }>;
  trades: Array<TradeSim>;
}

export default function Backtest() {
  const { toast } = useToast();
  const isReadOnly = localStorage.getItem("wasee_role") === "user";
  const [symbolA, setSymbolA] = useState("BTCUSDT");
  const [symbolB, setSymbolB] = useState("ETHUSDT");
  const [zEntry, setZEntry] = useState("2.8");
  const [zExit, setZExit] = useState("0.2");
  const [zSl, setZSl] = useState("4.2");
  const [slPercent, setSlPercent] = useState("2.0");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<BacktestResponse | null>(null);

  const handleRunBacktest = async () => {
    if (!symbolA || !symbolB) {
      toast({ title: "Symbols required", description: "Please specify both symbols.", variant: "destructive" });
      return;
    }
    setLoading(true);
    try {
      const res = await fetch("/api/backtest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbolA: symbolA.trim().toUpperCase(),
          symbolB: symbolB.trim().toUpperCase(),
          zEntry: parseFloat(zEntry),
          zExit: parseFloat(zExit),
          zSl: parseFloat(zSl),
          slPercent: parseFloat(slPercent),
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || "Failed to run backtest");
      }

      const data = (await res.json()) as BacktestResponse;
      setResults(data);
      toast({ title: "Backtest Completed", description: `Simulated ${data.totalTrades} trades for ${data.symbolA}/${data.symbolB}` });
    } catch (err) {
      toast({ title: "Backtest Failed", description: (err as Error).message, variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full overflow-auto bg-background p-6 space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-foreground">Arbitrage Backtesting</h2>
        <p className="text-sm text-muted-foreground">Run co-integration Kalman Filter simulations on Binance Futures historical data</p>
      </div>

      {/* Control Panel Card */}
      <Card className="bg-card border-border border-t-2 border-t-indigo-500/70 shadow-[0_4px_20px_rgba(99,102,241,0.05)]">
        <CardHeader>
          <CardTitle className="text-sm text-muted-foreground uppercase tracking-wider">Backtest Parameters</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-6 gap-4 items-end">
            <div>
              <label className="text-xs text-muted-foreground uppercase font-mono block mb-1">Symbol A</label>
              <Input value={symbolA} onChange={(e) => setSymbolA(e.target.value)} className="font-mono text-xs uppercase" />
            </div>
            <div>
              <label className="text-xs text-muted-foreground uppercase font-mono block mb-1">Symbol B</label>
              <Input value={symbolB} onChange={(e) => setSymbolB(e.target.value)} className="font-mono text-xs uppercase" />
            </div>
            <div>
              <label className="text-xs text-muted-foreground uppercase font-mono block mb-1">Z Entry</label>
              <Input value={zEntry} onChange={(e) => setZEntry(e.target.value)} className="font-mono text-xs" />
            </div>
            <div>
              <label className="text-xs text-muted-foreground uppercase font-mono block mb-1">Z Exit</label>
              <Input value={zExit} onChange={(e) => setZExit(e.target.value)} className="font-mono text-xs" />
            </div>
            <div>
              <label className="text-xs text-muted-foreground uppercase font-mono block mb-1">Z Stop Loss</label>
              <Input value={zSl} onChange={(e) => setZSl(e.target.value)} className="font-mono text-xs" />
            </div>
            <div>
              <label className="text-xs text-muted-foreground uppercase font-mono block mb-1">SL % (Crypto)</label>
              <Input value={slPercent} onChange={(e) => setSlPercent(e.target.value)} className="font-mono text-xs" />
            </div>
          </div>
          <Button onClick={handleRunBacktest} disabled={loading || isReadOnly} className="w-full md:w-auto mt-4 gap-2 bg-indigo-600 hover:bg-indigo-700 font-mono text-xs tracking-wider">
            <Play className="h-3.5 w-3.5 fill-current" />
            {loading ? "SIMULATING..." : "RUN BACKTEST SIMULATION"}
          </Button>
        </CardContent>
      </Card>

      {results && (
        <>
          {/* Stats Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card className="bg-card border-border border-t-2 border-t-blue-500/70 shadow-[0_4px_20px_rgba(59,130,246,0.05)]">
              <CardHeader className="pb-2">
                <CardTitle className="text-xs text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                  <Activity className="h-3.5 w-3.5" /> Total Trades
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-mono font-bold text-blue-500">{results.totalTrades}</div>
                <div className="text-[10px] text-muted-foreground mt-1 font-mono">
                  Wins: {results.wins} · Losses: {results.losses}
                </div>
              </CardContent>
            </Card>

            <Card className="bg-card border-border border-t-2 border-t-green-500/70 shadow-[0_4px_20px_rgba(34,197,94,0.05)]">
              <CardHeader className="pb-2">
                <CardTitle className="text-xs text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                  <Award className="h-3.5 w-3.5" /> Win Rate
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-mono font-bold text-green-500">{results.winRate}%</div>
                <div className="text-[10px] text-muted-foreground mt-1 font-mono">
                  Win Rate target: &gt; 80%
                </div>
              </CardContent>
            </Card>

            <Card className="bg-card border-border border-t-2 border-t-emerald-500/70 shadow-[0_4px_20px_rgba(16,185,129,0.05)]">
              <CardHeader className="pb-2">
                <CardTitle className="text-xs text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                  <DollarSign className="h-3.5 w-3.5" /> Net Profit
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className={cn("text-2xl font-mono font-bold", results.netProfit >= 0 ? "text-green-500" : "text-red-500")}>
                  {results.netProfit >= 0 ? "+" : ""}${results.netProfit}
                </div>
                <div className="text-[10px] text-muted-foreground mt-1 font-mono">
                  Initial balance: $10,000
                </div>
              </CardContent>
            </Card>

            <Card className="bg-card border-border border-t-2 border-t-purple-500/70 shadow-[0_4px_20px_rgba(168,85,247,0.05)]">
              <CardHeader className="pb-2">
                <CardTitle className="text-xs text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                  <TrendingUp className="h-3.5 w-3.5" /> Final Balance
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-mono font-bold text-purple-500">${results.finalBalance}</div>
                <div className="text-[10px] text-muted-foreground mt-1 font-mono">
                  P&L Factor: {results.profitFactor}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Equity Chart & Simulated Trades */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Equity Curve Chart */}
            <Card className="md:col-span-1 bg-card border-border">
              <CardHeader>
                <CardTitle className="text-xs text-muted-foreground uppercase tracking-wider">Equity Curve</CardTitle>
              </CardHeader>
              <CardContent className="h-[250px] pb-4">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={results.equityCurve} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2a2f3a" />
                    <XAxis dataKey="time" stroke="#71717a" fontSize={10} />
                    <YAxis stroke="#71717a" fontSize={10} domain={["auto", "auto"]} />
                    <Tooltip contentStyle={{ backgroundColor: "#18181b", borderColor: "#27272a" }} />
                    <Line type="monotone" dataKey="balance" stroke="#3b82f6" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            {/* Simulated Trades List */}
            <Card className="md:col-span-2 bg-card border-border">
              <CardHeader>
                <CardTitle className="text-xs text-muted-foreground uppercase tracking-wider">Simulated Trades List (Last 30)</CardTitle>
              </CardHeader>
              <CardContent className="p-0 max-h-[250px] overflow-y-auto">
                <Table>
                  <TableHeader className="bg-muted/50 sticky top-0">
                    <TableRow className="border-border">
                      <TableHead className="font-mono text-[10px] py-2">TIME</TableHead>
                      <TableHead className="font-mono text-[10px] py-2">TYPE</TableHead>
                      <TableHead className="font-mono text-[10px] py-2 text-right">ENTRY A / B</TableHead>
                      <TableHead className="font-mono text-[10px] py-2 text-right">EXIT A / B</TableHead>
                      <TableHead className="font-mono text-[10px] py-2 text-right">RETURN</TableHead>
                      <TableHead className="font-mono text-[10px] py-2 text-center">REASON</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {results.trades.map((t, idx) => (
                      <TableRow key={idx} className="border-border hover:bg-muted/30">
                        <TableCell className="font-mono text-[10px] py-2 text-muted-foreground">
                          {new Date(t.time).toLocaleTimeString()}
                        </TableCell>
                        <TableCell className="py-2">
                          <Badge variant="outline" className={cn(
                            "rounded-sm text-[9px] font-mono px-1 py-0",
                            t.type === "BUY" ? "bg-green-500/10 text-green-500 border-green-500/20" : "bg-red-500/10 text-red-500 border-red-500/20"
                          )}>
                            {t.type}
                          </Badge>
                        </TableCell>
                        <TableCell className="font-mono text-[10px] py-2 text-right">
                          {t.entryPriceA.toFixed(2)} / {t.entryPriceB.toFixed(2)}
                        </TableCell>
                        <TableCell className="font-mono text-[10px] py-2 text-right">
                          {t.exitPriceA.toFixed(2)} / {t.exitPriceB.toFixed(2)}
                        </TableCell>
                        <TableCell className={cn(
                          "font-mono text-[10px] py-2 text-right font-bold",
                          t.profitPercent >= 0 ? "text-green-500" : "text-red-500"
                        )}>
                          {t.profitPercent >= 0 ? "+" : ""}{t.profitPercent.toFixed(2)}%
                        </TableCell>
                        <TableCell className="py-2 text-center">
                          <Badge variant="outline" className={cn(
                            "rounded-sm text-[9px] font-mono px-1 py-0",
                            t.reason === "TP_REVERSION" ? "bg-green-500/10 text-green-500 border-green-500/20" : "bg-red-500/10 text-red-500 border-red-500/20"
                          )}>
                            {t.reason}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
