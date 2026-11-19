import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { Play, TrendingUp, Award, DollarSign, Activity, ShieldCheck, Clock, Target } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { cn, formatPktDateTime } from "@/lib/utils";

interface SmcTradeSim {
  type: "BUY" | "SELL";
  symbol: string;
  lotUsed: number;
  entryPrice: number;
  exitPrice: number;
  slPrice: number;
  tpPrice: number;
  targetRrr: number;
  achievedRrr: number;
  profitUsd: number;
  profitPercent: number;
  breakevenTriggered: boolean;
  sessionLabel: string;
  reason: "TP_HIT" | "BREAKEVEN_LOCKED" | "SL_HIT" | "OPEN_END";
  entryTime: string;
  exitTime: string;
}

interface SmcBacktestResponse {
  symbol: string;
  label: string;
  category: "metals" | "forex" | "indices";
  totalTrades: number;
  wins: number;
  losses: number;
  breakevens: number;
  winRate: number;
  avgRrr: number;
  maxDrawdownPct: number;
  initialBalance: number;
  finalBalance: number;
  netProfit: number;
  profitFactor: number;
  lookbackDays: number;
  lotSize: number;
  maxSlDist: number;
  minRrr: number;
  sessionFilterEnabled: boolean;
  breakevenEnabled: boolean;
  smartRiskCapEnabled?: boolean;
  barsScannedM5: number;
  barsScannedM15: number;
  equityCurve: Array<{ time: string; balance: number }>;
  trades: Array<SmcTradeSim>;
}

interface InstrumentOption {
  symbol: string;
  label: string;
  category: "metals" | "forex" | "indices";
  defaultMaxSl: string;
  digits: number;
}

const INSTRUMENTS: InstrumentOption[] = [
  { symbol: "XAUUSD", label: "Gold (XAU/USD)", category: "metals", defaultMaxSl: "10.00", digits: 2 },
  { symbol: "XAGUSD", label: "Silver (XAG/USD)", category: "metals", defaultMaxSl: "0.50", digits: 3 },
  { symbol: "US30", label: "Dow Jones 30 (US30)", category: "indices", defaultMaxSl: "105.00", digits: 2 },
  { symbol: "NAS100", label: "Nasdaq 100 (NAS100)", category: "indices", defaultMaxSl: "85.00", digits: 2 },
  { symbol: "EURUSD", label: "EUR/USD", category: "forex", defaultMaxSl: "0.0050", digits: 5 },
  { symbol: "GBPUSD", label: "GBP/USD", category: "forex", defaultMaxSl: "0.0050", digits: 5 },
  { symbol: "USDJPY", label: "USD/JPY", category: "forex", defaultMaxSl: "0.50", digits: 3 },
  { symbol: "EURJPY", label: "EUR/JPY", category: "forex", defaultMaxSl: "0.50", digits: 3 },
  { symbol: "GBPJPY", label: "GBP/JPY", category: "forex", defaultMaxSl: "0.50", digits: 3 },
  { symbol: "AUDUSD", label: "AUD/USD", category: "forex", defaultMaxSl: "0.0050", digits: 5 },
  { symbol: "USDCAD", label: "USD/CAD", category: "forex", defaultMaxSl: "0.0050", digits: 5 },
  { symbol: "USDCHF", label: "USD/CHF", category: "forex", defaultMaxSl: "0.0050", digits: 5 },
  { symbol: "EURGBP", label: "EUR/GBP", category: "forex", defaultMaxSl: "0.0050", digits: 5 },
  { symbol: "NZDUSD", label: "NZD/USD", category: "forex", defaultMaxSl: "0.0050", digits: 5 },
];

export default function Backtest() {
  const { toast } = useToast();
  const isReadOnly = localStorage.getItem("wasee_role")?.toLowerCase() === "user";

  const [selectedSymbol, setSelectedSymbol] = useState("XAUUSD");
  const [lookbackDays, setLookbackDays] = useState<number>(30);
  const [lotSize, setLotSize] = useState("0.07");
  const [maxSlDist, setMaxSlDist] = useState("10.00");
  const [minRrr, setMinRrr] = useState("1.85");
  const [initialBalance, setInitialBalance] = useState("10000");
  const [sessionFilterEnabled, setSessionFilterEnabled] = useState(true);
  const [breakevenEnabled, setBreakevenEnabled] = useState(true);
  const [smartRiskCapEnabled, setSmartRiskCapEnabled] = useState(true);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<SmcBacktestResponse | null>(null);

  const activeInstrument = INSTRUMENTS.find((i) => i.symbol === selectedSymbol) ?? INSTRUMENTS[0]!;

  const handleSelectSymbol = (sym: string) => {
    setSelectedSymbol(sym);
    const found = INSTRUMENTS.find((i) => i.symbol === sym);
    if (found) {
      setMaxSlDist(found.defaultMaxSl);
      if (found.category === "indices") setLotSize("5.00");
      else if (found.category === "metals") setLotSize("0.07");
      else setLotSize("0.50");
    }
  };

  const handleRunBacktest = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/backtest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol: selectedSymbol,
          lookbackDays,
          lotSize: parseFloat(lotSize) || 0.07,
          maxSlDist: parseFloat(maxSlDist) || Number(activeInstrument.defaultMaxSl),
          minRrr: parseFloat(minRrr) || 1.85,
          initialBalance: parseFloat(initialBalance) || 10000,
          sessionFilterEnabled,
          breakevenEnabled,
          smartRiskCapEnabled,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || "Failed to run SMC backtest");
      }

      const data = (await res.json()) as SmcBacktestResponse;
      setResults(data);
      toast({
        title: `SMC Backtest Complete (${data.symbol})`,
        description: `${data.totalTrades} trades over ${data.lookbackDays}D · Win Rate ${data.winRate}% · Net ${data.netProfit >= 0 ? "+" : ""}$${data.netProfit}`,
      });
    } catch (err) {
      toast({ title: "Backtest Failed", description: (err as Error).message, variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  const formatPrice = (val: number, sym: string) => {
    const inst = INSTRUMENTS.find((i) => i.symbol === sym);
    const digits = inst?.digits ?? (val > 500 ? 2 : val > 20 ? 3 : 5);
    return val.toFixed(digits);
  };

  const getOutcomeBadge = (reason: SmcTradeSim["reason"]) => {
    if (reason === "TP_HIT") {
      return "bg-emerald-500/15 text-emerald-400 border-emerald-500/30";
    }
    if (reason === "BREAKEVEN_LOCKED") {
      return "bg-sky-500/15 text-sky-400 border-sky-500/30";
    }
    if (reason === "SL_HIT") {
      return "bg-rose-500/15 text-rose-400 border-rose-500/30";
    }
    return "bg-zinc-800 text-zinc-400 border-zinc-700";
  };

  return (
    <div className="flex flex-col h-full overflow-auto bg-background p-3 sm:p-6 space-y-4 sm:space-y-6 w-full max-w-[1600px] mx-auto">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="space-y-1">
          <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground">
            Pure SMC / ICT Backtesting
          </h2>
          <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed">
            9-Condition M15 + M5 Forex &amp; Metals Simulator · Sweep → CHoCH → FVG Retest → M15 Liquidity Target (Zero Crypto / Zero Z-Score)
          </p>
        </div>
        <Badge variant="outline" className="font-mono text-[10px] border-emerald-500/30 bg-emerald-500/10 text-emerald-400 shrink-0">
          FOREX &amp; METALS ONLY · SMC 9-STEP ENGINE
        </Badge>
      </div>

      {/* Control Panel Card */}
      <Card className="bg-card border-border border-t-2 border-t-indigo-500/70 shadow-[0_4px_20px_rgba(99,102,241,0.05)]">
        <CardHeader className="p-4 sm:p-6 pb-3 sm:pb-4">
          <CardTitle className="text-sm text-muted-foreground uppercase tracking-wider">
            SMC Simulation Parameters
          </CardTitle>
          <CardDescription className="text-xs">
            Select Metal or Forex instrument &amp; live execution rules to test on historical M5 + M15 candles
          </CardDescription>
        </CardHeader>
        <CardContent className="p-4 sm:p-6 pt-0 space-y-5">
          {/* Instrument Selector */}
          <div className="space-y-2">
            <label className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground block">
              Select Asset (Metals &amp; Forex)
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-2">
              {INSTRUMENTS.map((inst) => (
                <button
                  key={inst.symbol}
                  type="button"
                  onClick={() => handleSelectSymbol(inst.symbol)}
                  className={cn(
                    "px-2.5 py-2 rounded-sm border text-left transition-all min-w-0",
                    selectedSymbol === inst.symbol
                      ? "bg-primary/15 border-primary text-primary shadow-sm"
                      : "bg-muted/25 border-border text-muted-foreground hover:border-primary/40 hover:text-foreground"
                  )}
                >
                  <div className="flex items-center justify-between gap-1">
                    <span className="font-mono font-bold text-xs truncate">{inst.symbol}</span>
                    <span className={cn(
                      "text-[9px] uppercase font-mono px-1 rounded shrink-0",
                      inst.category === "metals" ? "bg-amber-500/15 text-amber-400" : inst.category === "indices" ? "bg-indigo-500/15 text-indigo-400" : "bg-sky-500/15 text-sky-400"
                    )}>
                      {inst.category}
                    </span>
                  </div>
                  <div className="text-[10px] opacity-75 truncate mt-0.5">{inst.label}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Numeric Parameters & Horizon */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 sm:gap-4 items-end">
            <div className="col-span-2 sm:col-span-1">
              <label className="text-[10px] text-muted-foreground uppercase font-mono block mb-1">
                Lookback Period
              </label>
              <div className="grid grid-cols-3 gap-1.5">
                {[5, 14, 30].map((d) => (
                  <button
                    key={d}
                    type="button"
                    onClick={() => setLookbackDays(d)}
                    className={cn(
                      "h-9 rounded border font-mono text-xs font-bold transition-colors",
                      lookbackDays === d
                        ? "bg-indigo-600 border-indigo-500 text-white"
                        : "bg-background border-border text-muted-foreground hover:text-foreground"
                    )}
                  >
                    {d}D
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="text-[10px] text-muted-foreground uppercase font-mono block mb-1">
                Lot Size
              </label>
              <Input
                type="number"
                step="0.01"
                min="0.01"
                value={lotSize}
                onChange={(e) => setLotSize(e.target.value)}
                className="font-mono text-xs h-9"
              />
            </div>

            <div>
              <label className="text-[10px] text-muted-foreground uppercase font-mono block mb-1">
                Max SL Cap ({activeInstrument.symbol.includes("XAU") ? "$ Move" : "Price Dist"})
              </label>
              <Input
                type="number"
                step={activeInstrument.digits <= 3 ? "0.05" : "0.0005"}
                value={maxSlDist}
                onChange={(e) => setMaxSlDist(e.target.value)}
                className="font-mono text-xs h-9"
              />
            </div>

            <div>
              <label className="text-[10px] text-muted-foreground uppercase font-mono block mb-1">
                Min Target R:R
              </label>
              <Input
                type="number"
                step="0.05"
                min="1.0"
                value={minRrr}
                onChange={(e) => setMinRrr(e.target.value)}
                className="font-mono text-xs h-9"
              />
            </div>

            <div>
              <label className="text-[10px] text-muted-foreground uppercase font-mono block mb-1">
                Starting Capital ($)
              </label>
              <Input
                type="number"
                step="500"
                min="100"
                value={initialBalance}
                onChange={(e) => setInitialBalance(e.target.value)}
                className="font-mono text-xs h-9"
              />
            </div>
          </div>

          {/* Live Safeguard Toggles */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-1">
            <div className="flex items-center justify-between gap-3 p-3 rounded border border-border bg-muted/20">
              <div className="min-w-0 flex-1 space-y-0.5">
                <div className="text-xs font-semibold flex items-center gap-1.5 text-zinc-100">
                  <Clock className="h-3.5 w-3.5 text-sky-400 shrink-0" />
                  <span>PKT Session Guard (12–4 &amp; 6–10 PM)</span>
                </div>
                <p className="text-[11px] text-muted-foreground leading-snug">
                  New SMC entries only in London + NY PKT windows (active SL/BE run 24/7)
                </p>
              </div>
              <Switch
                className="shrink-0"
                checked={sessionFilterEnabled}
                onCheckedChange={setSessionFilterEnabled}
              />
            </div>

            <div className="flex items-center justify-between gap-3 p-3 rounded border border-border bg-muted/20">
              <div className="min-w-0 flex-1 space-y-0.5">
                <div className="text-xs font-semibold flex items-center gap-1.5 text-zinc-100">
                  <ShieldCheck className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                  <span>Smart $52 Max Risk Auto-Lot</span>
                </div>
                <p className="text-[11px] text-muted-foreground leading-snug">
                  Uses 0.07 lot (SL &le; $7.42), auto-scales 0.06/0.05 on $7.43–$10 SL (loss &le; $52)
                </p>
              </div>
              <Switch
                className="shrink-0"
                checked={smartRiskCapEnabled}
                onCheckedChange={setSmartRiskCapEnabled}
              />
            </div>

            <div className="flex items-center justify-between gap-3 p-3 rounded border border-border bg-muted/20">
              <div className="min-w-0 flex-1 space-y-0.5">
                <div className="text-xs font-semibold flex items-center gap-1.5 text-zinc-100">
                  <ShieldCheck className="h-3.5 w-3.5 text-indigo-400 shrink-0" />
                  <span>Pure Breakeven (+$50 Trigger)</span>
                </div>
                <p className="text-[11px] text-muted-foreground leading-snug">
                  Locks Entry+$0.25 (Gold) / 2.15pt (Indices) only after +$50.00 USD (No Stagnation, No Trailing)
                </p>
              </div>
              <Switch
                className="shrink-0"
                checked={breakevenEnabled}
                onCheckedChange={setBreakevenEnabled}
              />
            </div>
          </div>

          <Button
            onClick={handleRunBacktest}
            disabled={loading || isReadOnly}
            className="w-full sm:w-auto gap-2 bg-indigo-600 hover:bg-indigo-700 font-mono text-xs font-bold tracking-wider min-h-10 px-6"
          >
            <Play className="h-3.5 w-3.5 fill-current" />
            {loading ? `SIMULATING ${selectedSymbol}...` : `RUN PURE SMC BACKTEST (${selectedSymbol})`}
          </Button>
        </CardContent>
      </Card>

      {results && (
        <>
          {/* Metadata Strip */}
          <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
            <Badge variant="outline" className="border-indigo-500/40 bg-indigo-500/10 text-indigo-300">
              {results.symbol} · {results.lookbackDays}D Window
            </Badge>
            <Badge variant="outline" className="border-zinc-700 text-zinc-300">
              M5 Bars: {results.barsScannedM5.toLocaleString()} · M15 Bars: {results.barsScannedM15.toLocaleString()}
            </Badge>
            <Badge variant="outline" className="border-zinc-700 text-zinc-300">
              Max Lot: {results.lotSize} · {results.smartRiskCapEnabled !== false ? "Cap <=$52" : "Fixed Lot"} · Min R:R: {results.minRrr}R
            </Badge>
            <Badge variant="outline" className={results.sessionFilterEnabled ? "border-sky-500/40 text-sky-300" : "border-amber-500/40 text-amber-300"}>
              {results.sessionFilterEnabled ? "Session Filter: 12-4 & 6-10 PM PKT" : "Session Filter: 24/7 Unfiltered"}
            </Badge>
          </div>

          {/* Stats Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3 sm:gap-4">
            <Card className="bg-card border-border border-t-2 border-t-blue-500/70">
              <CardHeader className="p-3 sm:p-4 pb-1 sm:pb-2">
                <CardTitle className="text-[11px] text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                  <Activity className="h-3.5 w-3.5 shrink-0" /> Total Trades
                </CardTitle>
              </CardHeader>
              <CardContent className="p-3 sm:p-4 pt-0">
                <div className="text-xl sm:text-2xl font-mono font-bold text-blue-400">{results.totalTrades}</div>
                <div className="text-[10px] text-muted-foreground mt-1 font-mono">
                  W: {results.wins} · L: {results.losses} · BE: {results.breakevens}
                </div>
              </CardContent>
            </Card>

            <Card className="bg-card border-border border-t-2 border-t-green-500/70">
              <CardHeader className="p-3 sm:p-4 pb-1 sm:pb-2">
                <CardTitle className="text-[11px] text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                  <Award className="h-3.5 w-3.5 shrink-0" /> Win Rate
                </CardTitle>
              </CardHeader>
              <CardContent className="p-3 sm:p-4 pt-0">
                <div className="text-xl sm:text-2xl font-mono font-bold text-green-400">{results.winRate}%</div>
                <div className="text-[10px] text-muted-foreground mt-1 font-mono">
                  Avg Realized: {results.avgRrr}R
                </div>
              </CardContent>
            </Card>

            <Card className="bg-card border-border border-t-2 border-t-emerald-500/70">
              <CardHeader className="p-3 sm:p-4 pb-1 sm:pb-2">
                <CardTitle className="text-[11px] text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                  <DollarSign className="h-3.5 w-3.5 shrink-0" /> Net Profit
                </CardTitle>
              </CardHeader>
              <CardContent className="p-3 sm:p-4 pt-0">
                <div className={cn("text-xl sm:text-2xl font-mono font-bold", results.netProfit >= 0 ? "text-emerald-400" : "text-rose-400")}>
                  {results.netProfit >= 0 ? "+" : ""}${results.netProfit.toFixed(2)}
                </div>
                <div className="text-[10px] text-muted-foreground mt-1 font-mono">
                  Return: {((results.netProfit / Math.max(1, results.initialBalance)) * 100).toFixed(2)}%
                </div>
              </CardContent>
            </Card>

            <Card className="bg-card border-border border-t-2 border-t-purple-500/70">
              <CardHeader className="p-3 sm:p-4 pb-1 sm:pb-2">
                <CardTitle className="text-[11px] text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                  <TrendingUp className="h-3.5 w-3.5 shrink-0" /> Final Equity
                </CardTitle>
              </CardHeader>
              <CardContent className="p-3 sm:p-4 pt-0">
                <div className="text-xl sm:text-2xl font-mono font-bold text-purple-400">
                  ${results.finalBalance.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                </div>
                <div className="text-[10px] text-muted-foreground mt-1 font-mono">
                  Start: ${results.initialBalance.toLocaleString()}
                </div>
              </CardContent>
            </Card>

            <Card className="bg-card border-border border-t-2 border-t-cyan-500/70">
              <CardHeader className="p-3 sm:p-4 pb-1 sm:pb-2">
                <CardTitle className="text-[11px] text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                  <Target className="h-3.5 w-3.5 shrink-0" /> Profit Factor
                </CardTitle>
              </CardHeader>
              <CardContent className="p-3 sm:p-4 pt-0">
                <div className="text-xl sm:text-2xl font-mono font-bold text-cyan-400">{results.profitFactor}</div>
                <div className="text-[10px] text-muted-foreground mt-1 font-mono">
                  Gross Gain / Loss
                </div>
              </CardContent>
            </Card>

            <Card className="bg-card border-border border-t-2 border-t-rose-500/70">
              <CardHeader className="p-3 sm:p-4 pb-1 sm:pb-2">
                <CardTitle className="text-[11px] text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                  <ShieldCheck className="h-3.5 w-3.5 shrink-0" /> Max Drawdown
                </CardTitle>
              </CardHeader>
              <CardContent className="p-3 sm:p-4 pt-0">
                <div className="text-xl sm:text-2xl font-mono font-bold text-rose-400">-{results.maxDrawdownPct}%</div>
                <div className="text-[10px] text-muted-foreground mt-1 font-mono">
                  Limit Check (3.3% Max)
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Equity Chart & Simulated Trades */}
          <div className="grid grid-cols-1 xl:grid-cols-12 gap-4 sm:gap-6">
            {/* Equity Curve Chart */}
            <Card className="xl:col-span-4 bg-card border-border">
              <CardHeader className="p-4 sm:p-6 pb-2">
                <CardTitle className="text-xs text-muted-foreground uppercase tracking-wider">Equity Curve (PKT)</CardTitle>
              </CardHeader>
              <CardContent className="p-3 sm:p-6 pt-0 h-[260px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={results.equityCurve} margin={{ top: 10, right: 10, left: -12, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2a2f3a" />
                    <XAxis
                      dataKey="time"
                      stroke="#71717a"
                      fontSize={10}
                      tickFormatter={(v) => formatPktDateTime(v).split(",")[0] ?? v}
                    />
                    <YAxis stroke="#71717a" fontSize={10} domain={["auto", "auto"]} />
                    <Tooltip
                      contentStyle={{ backgroundColor: "#18181b", borderColor: "#27272a", fontSize: "11px" }}
                      labelFormatter={(v) => formatPktDateTime(String(v))}
                    />
                    <Line type="monotone" dataKey="balance" stroke="#3b82f6" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            {/* Simulated SMC Trades List */}
            <Card className="xl:col-span-8 bg-card border-border">
              <CardHeader className="p-4 sm:p-6 pb-2">
                <CardTitle className="text-xs text-muted-foreground uppercase tracking-wider">
                  Simulated Pure SMC Trades (Latest {results.trades.length})
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0 max-h-[320px] overflow-y-auto">
                {results.trades.length === 0 ? (
                  <div className="p-8 text-center text-xs font-mono text-muted-foreground">
                    No strict 9-condition SMC setups fired in this lookback window. Try 30D lookback or toggling Session Filter.
                  </div>
                ) : (
                  <Table>
                    <TableHeader className="bg-muted/50 sticky top-0">
                      <TableRow className="border-border">
                        <TableHead className="font-mono text-[10px] py-2 whitespace-nowrap">ENTRY TIME (PKT)</TableHead>
                        <TableHead className="font-mono text-[10px] py-2">SIDE</TableHead>
                        <TableHead className="font-mono text-[10px] py-2">LOTS</TableHead>
                        <TableHead className="font-mono text-[10px] py-2">SESSION</TableHead>
                        <TableHead className="font-mono text-[10px] py-2 text-right whitespace-nowrap">ENTRY → EXIT</TableHead>
                        <TableHead className="font-mono text-[10px] py-2 text-right whitespace-nowrap">SL / TP</TableHead>
                        <TableHead className="font-mono text-[10px] py-2 text-right">R:R</TableHead>
                        <TableHead className="font-mono text-[10px] py-2 text-right">P&amp;L</TableHead>
                        <TableHead className="font-mono text-[10px] py-2 text-center">OUTCOME</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {results.trades.map((t, idx) => (
                        <TableRow key={idx} className="border-border hover:bg-muted/30">
                          <TableCell className="font-mono text-[10px] py-2 text-muted-foreground whitespace-nowrap">
                            {formatPktDateTime(t.entryTime)}
                          </TableCell>
                          <TableCell className="py-2">
                            <Badge variant="outline" className={cn(
                              "rounded-sm text-[9px] font-mono px-1.5 py-0 font-bold",
                              t.type === "BUY" ? "bg-green-500/10 text-green-400 border-green-500/30" : "bg-red-500/10 text-red-400 border-red-500/30"
                            )}>
                              {t.type}
                            </Badge>
                          </TableCell>
                          <TableCell className="font-mono text-[10px] py-2 text-sky-300 font-bold whitespace-nowrap">
                            {(t.lotUsed ?? results.lotSize).toFixed(2)}
                          </TableCell>
                          <TableCell className="font-mono text-[10px] py-2 text-zinc-400 whitespace-nowrap">
                            {t.sessionLabel}
                          </TableCell>
                          <TableCell className="font-mono text-[10px] py-2 text-right whitespace-nowrap">
                            {formatPrice(t.entryPrice, t.symbol)} → {formatPrice(t.exitPrice, t.symbol)}
                          </TableCell>
                          <TableCell className="font-mono text-[10px] py-2 text-right whitespace-nowrap text-muted-foreground">
                            <span className="text-rose-400">{formatPrice(t.slPrice, t.symbol)}</span>
                            {" / "}
                            <span className="text-emerald-400">{formatPrice(t.tpPrice, t.symbol)}</span>
                          </TableCell>
                          <TableCell className="font-mono text-[10px] py-2 text-right whitespace-nowrap">
                            {t.achievedRrr >= 0 ? "+" : ""}{t.achievedRrr}R
                          </TableCell>
                          <TableCell className={cn(
                            "font-mono text-[10px] py-2 text-right font-bold whitespace-nowrap",
                            t.profitUsd >= 0 ? "text-emerald-400" : "text-rose-400"
                          )}>
                            {t.profitUsd >= 0 ? "+" : ""}${t.profitUsd.toFixed(2)}
                          </TableCell>
                          <TableCell className="py-2 text-center whitespace-nowrap">
                            <Badge variant="outline" className={cn("rounded-sm text-[9px] font-mono px-1.5 py-0", getOutcomeBadge(t.reason))}>
                              {t.reason}
                            </Badge>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
