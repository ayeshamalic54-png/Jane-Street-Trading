import { useGetSignals, getGetSignalsQueryKey, useGetConfig, useExecuteTrade } from "@workspace/api-client-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { format } from "date-fns";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";

export default function Signals() {
  const executeTrade = useExecuteTrade();
  const { toast } = useToast();
  const isReadOnly = localStorage.getItem("wasee_role") === "user";
  const { data: signals, isLoading: isSignalsLoading } = useGetSignals({ limit: 100 }, {
    query: {
      queryKey: getGetSignalsQueryKey({ limit: 100 })
    }
  });

  const { data: config, isLoading: isConfigLoading } = useGetConfig();

  const isLoading = isSignalsLoading || isConfigLoading;

  const handleExecuteSignal = (sig: any) => {
    const isBuy = sig.action === "BUY_SPREAD";
    const dirA = isBuy ? "BUY" : "SELL";
    
    // Check if symbol A is metals/indices to assign category-specific lots if dashboard is 0.0
    const getSymbolCategory = (sym: string): string => {
      const s = sym.toUpperCase();
      if (s.includes("XAU") || s.includes("XAG")) return "metals";
      if (s.includes("AAPL") || s.includes("MSFT") || s.includes("GOOGL") || s.includes("TSLA") || s.includes("NVDA") || s.includes("AMD") || s.includes("META") || s.includes("AMZN") || s.includes("US500") || s.includes("US30") || s.includes("NAS100") || s.includes("GER30") || s.includes("UK100")) return "indices";
      return "forex";
    };

    const category = getSymbolCategory(sig.symbolA);
    let defaultLots = config?.defaultLots ?? 0.0;
    if (defaultLots <= 0.0) {
      if (category === "metals") defaultLots = 0.15;
      else if (category === "indices") defaultLots = 0.60;
      else defaultLots = 1.20; // forex
    }

    const partLotsA = defaultLots / 3.0;
    const betaVal = Number(sig.beta ?? 1.0);
    const betaPositive = (betaVal >= 0);
    
    let dirB = "BUY";
    if (isBuy) {
      // BUY_SPREAD: BUY A, SELL B if beta > 0. If beta < 0, BUY B!
      dirB = betaPositive ? "SELL" : "BUY";
    } else {
      // SELL_SPREAD: SELL A, BUY B if beta > 0. If beta < 0, SELL B!
      dirB = betaPositive ? "BUY" : "SELL";
    }

    // Hedge lots are multiplied by 3.0 in main.py, so we pass the part scale here
    const partLotsB = Math.max(0.01, Math.abs(partLotsA * betaVal));

    const slPips = config?.slPips ?? 10;
    const tpPips = config?.tpPips ?? 20;

    executeTrade.mutate(
      { data: { symbol: sig.symbolA, direction: dirA, lots: partLotsA, slPips, tpPips } },
      {
        onSuccess: () => {
          executeTrade.mutate(
            { data: { symbol: sig.symbolB, direction: dirB, lots: partLotsB, slPips, tpPips, comment: "JS_HEDGE_MANUAL_LEGB" } },
            {
              onSuccess: () => {
                toast({
                  title: "🚀 One-Click Spread Executed",
                  description: `Queued: ${dirA} ${sig.symbolA} (${defaultLots.toFixed(2)} lots) & ${dirB} ${sig.symbolB} (${(partLotsB * 3.0).toFixed(2)} lots) successfully!`,
                });
              },
              onError: () => {
                toast({ title: `Failed to queue second leg ${sig.symbolB}`, variant: "destructive" });
              }
            }
          );
        },
        onError: () => {
          toast({ title: `Failed to queue first leg ${sig.symbolA}`, variant: "destructive" });
        }
      }
    );
  };

  const getPipSize = (sym: string): number => {
    const s = sym.toUpperCase();
    if (s.includes("JPY")) return 0.01;
    if (s.includes("XAU")) return 1.0;
    if (s.includes("XAG")) return 0.1;
    if (s.includes("BTC")) return 1.0;
    if (s.includes("ETH")) return 0.1;
    if (s.includes("SOL") || s.includes("BNB") || s.includes("AVAX")) return 0.01;
    if (s.includes("XRP") || s.includes("ADA") || s.includes("DOGE") || s.includes("MATIC")) return 0.0001;
    if (["US500", "US30", "NAS100", "GER30", "UK100", "SPX", "DJI", "NDX"].some(x => s.includes(x))) return 1.0;
    if (["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMD", "META", "AMZN"].some(x => s.includes(x))) return 0.1;
    return 0.0001;
  };

  const getActionBadge = (action: string) => {
    switch(action) {
      case "BUY_SPREAD":
        return <Badge variant="outline" className="bg-green-500/10 text-green-500 border-green-500/30 rounded-sm font-mono text-[10px]">BUY_SPREAD</Badge>;
      case "SELL_SPREAD":
        return <Badge variant="outline" className="bg-red-500/10 text-red-500 border-red-500/30 rounded-sm font-mono text-[10px]">SELL_SPREAD</Badge>;
      default:
        return <Badge variant="outline" className="bg-gray-500/10 text-gray-400 border-gray-500/30 rounded-sm font-mono text-[10px]">NONE</Badge>;
    }
  };

  const getSignalDetails = (sig: any) => {
    const entry = Number(sig.priceA);
    const entryB = Number(sig.priceB);
    const slPips = config?.slPips ?? 10;
    const tpPips = config?.tpPips ?? 20;
    
    const s = sig.symbolA.toUpperCase();
    const isCrypto = s.endsWith("USDT") || ["BTC", "ETH", "SOL", "BNB", "AVAX", "XRP", "ADA", "DOGE", "MATIC"].some(x => s.includes(x));
    
    const slDist = isCrypto ? slPips * (entry * 0.001) : slPips * getPipSize(sig.symbolA);
    const tpDist = isCrypto ? tpPips * (entry * 0.001) : tpPips * getPipSize(sig.symbolA);
    const pricePrecision = isCrypto ? 2 : (getPipSize(sig.symbolA) <= 0.0001 ? 5 : getPipSize(sig.symbolA) <= 0.01 ? 3 : 2);

    const sB = sig.symbolB.toUpperCase();
    const isCryptoB = sB.endsWith("USDT") || ["BTC", "ETH", "SOL", "BNB", "AVAX", "XRP", "ADA", "DOGE", "MATIC"].some(x => sB.includes(x));
    const slDistB = isCryptoB ? slPips * (entryB * 0.001) : slPips * getPipSize(sig.symbolB);
    const pricePrecisionB = isCryptoB ? 2 : (getPipSize(sig.symbolB) <= 0.0001 ? 5 : getPipSize(sig.symbolB) <= 0.01 ? 3 : 2);

    const isBuy = sig.action === "BUY_SPREAD";
    const slB = isBuy ? (entryB + slDistB) : (entryB - slDistB);

    if (sig.action === "BUY_SPREAD") {
      return {
        entry: entry.toFixed(pricePrecision),
        sl: (entry - slDist).toFixed(pricePrecision),
        tp1: (entry + slDist).toFixed(pricePrecision),
        tp2: (entry + tpDist).toFixed(pricePrecision),
        tp3: (entry + slDist * 3.5).toFixed(pricePrecision),
        entryB: entryB.toFixed(pricePrecisionB),
        slB: slB.toFixed(pricePrecisionB),
      };
    } else if (sig.action === "SELL_SPREAD") {
      return {
        entry: entry.toFixed(pricePrecision),
        sl: (entry + slDist).toFixed(pricePrecision),
        tp1: (entry - slDist).toFixed(pricePrecision),
        tp2: (entry - tpDist).toFixed(pricePrecision),
        tp3: (entry - slDist * 3.5).toFixed(pricePrecision),
        entryB: entryB.toFixed(pricePrecisionB),
        slB: slB.toFixed(pricePrecisionB),
      };
    }
    return { entry: "—", sl: "—", tp1: "—", tp2: "—", tp3: "—", entryB: "—", slB: "—" };
  };

  const getTpPill = (partName: string, tradesList: any[] = []) => {
    const trade = tradesList.find((t: any) => t.comment && t.comment.includes(partName));
    if (!trade) {
      return <Badge variant="outline" className="bg-gray-500/5 text-muted-foreground/40 border-border rounded-sm font-mono text-[9px] px-1 py-0 h-4">N/A</Badge>;
    }
    if (trade.status === "OPEN") {
      return <Badge variant="outline" className="bg-blue-500/10 text-blue-400 border-blue-500/20 rounded-sm font-mono text-[9px] px-1 py-0 h-4">OPEN</Badge>;
    }
    const profit = Number(trade.profit ?? 0);
    if (profit > 0) {
      return <Badge variant="outline" className="bg-green-500/10 text-green-400 border-green-500/20 rounded-sm font-mono text-[9px] px-1 py-0 h-4">HIT</Badge>;
    } else {
      return <Badge variant="outline" className="bg-red-500/15 text-red-400 border-red-500/20 rounded-sm font-mono text-[9px] px-1 py-0 h-4">SL</Badge>;
    }
  };

  const getHedgePill = (tradesList: any[] = []) => {
    const trade = tradesList.find((t: any) => t.comment && t.comment.includes("HEDGE"));
    if (!trade) return null;
    if (trade.status === "OPEN") {
      return <Badge variant="outline" className="bg-blue-500/10 text-blue-400 border-blue-500/20 rounded-sm font-mono text-[9px] px-1 py-0 h-4">H_OPEN</Badge>;
    }
    const profit = Number(trade.profit ?? 0);
    return (
      <Badge variant="outline" className={cn(
        "rounded-sm font-mono text-[9px] px-1 py-0 h-4",
        profit >= 0 ? "bg-green-500/10 text-green-400 border-green-500/20" : "bg-red-500/15 text-red-400 border-red-500/20"
      )}>
        H_CLSD
      </Badge>
    );
  };

  const handleCopySignal = (sig: any) => {
    const isBuy = sig.action === "BUY_SPREAD";
    const details = getSignalDetails(sig);
    const timeStr = format(new Date(sig.timestamp), "EEEE, dd/MM/yyyy, hh:mm:ss a");
    
    const actionEmoji = isBuy ? "🟢" : "🔴";
    
    // Check if symbol A is metals/indices to assign category-specific lots if dashboard is 0.0
    const getSymbolCategory = (sym: string): string => {
      const s = sym.toUpperCase();
      if (s.includes("XAU") || s.includes("XAG")) return "metals";
      if (s.includes("AAPL") || s.includes("MSFT") || s.includes("GOOGL") || s.includes("TSLA") || s.includes("NVDA") || s.includes("AMD") || s.includes("META") || s.includes("AMZN") || s.includes("US500") || s.includes("US30") || s.includes("NAS100") || s.includes("GER30") || s.includes("UK100")) return "indices";
      return "forex";
    };

    const category = getSymbolCategory(sig.symbolA);
    let defaultLots = config?.defaultLots ?? 0.0;
    if (defaultLots <= 0.0) {
      if (category === "metals") defaultLots = 0.15;
      else if (category === "indices") defaultLots = 0.60;
      else defaultLots = 1.20; // forex
    }

    const partLotsA = (defaultLots / 3.0).toFixed(2);
    const totalLotsA = defaultLots.toFixed(2);
    
    const betaVal = Number(sig.beta ?? 1.0);
    const betaPositive = (betaVal >= 0);
    
    let legBDirection = "BUY";
    if (isBuy) {
      // BUY_SPREAD: BUY A, SELL B if beta > 0. If beta < 0 (negative correlation), BUY B to hedge!
      legBDirection = betaPositive ? "SELL" : "BUY";
    } else {
      // SELL_SPREAD: SELL A, BUY B if beta > 0. If beta < 0 (negative correlation), SELL B to hedge!
      legBDirection = betaPositive ? "BUY" : "SELL";
    }

    const lotsB = Math.max(0.01, Math.abs(defaultLots * betaVal)).toFixed(2);

    const text = `📢 *AWAIS JANE STREET QUANTUM ENGINE SIGNAL* 📢\n\n` +
      `${actionEmoji} *ACTION:* ${sig.action} (${sig.symbolA} / ${sig.symbolB})\n` +
      `⏱ *Time:* ${timeStr}\n` +
      `📊 *Z-Score:* ${sig.zScore.toFixed(3)}\n\n` +
      `🛡 *LEG A (${sig.symbolA}) - 3 Parts:*\n` +
      `  📥 *Entry:* ${details.entry}\n` +
      `  ⛔ *Stop Loss (SL):* ${details.sl}\n` +
      `  🎯 *TP1:* ${details.tp1}\n` +
      `  🎯 *TP2:* ${details.tp2}\n` +
      `  🎯 *TP3:* ${details.tp3}\n` +
      `  📦 *Lots:* 3 parts of ${partLotsA} (Total ${totalLotsA})\n\n` +
      `⚖ *LEG B (${sig.symbolB}) - Hedge:*\n` +
      `  📥 *Entry:* ${details.entryB}\n` +
      `  ⛔ *Stop Loss (SL):* ${details.slB}\n` +
      `  🎯 *TP:* Dynamic (Spread Reversion)\n` +
      `  📦 *Lots:* ${lotsB}\n` +
      `  📥 *Position:* ${legBDirection}`;

    navigator.clipboard.writeText(text).then(() => {
      toast({
        title: "📋 Copied to Clipboard!",
        description: "Signal text formatted for WhatsApp has been copied successfully.",
      });
    }).catch(() => {
      toast({
        title: "❌ Failed to Copy",
        description: "Could not copy signal to clipboard.",
        variant: "destructive"
      });
    });
  };

  return (
    <div className="flex flex-col h-full overflow-auto bg-background p-6 space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-foreground">Signal Log</h2>
        <p className="text-sm text-muted-foreground">Statistical arbitrage model generation log</p>
      </div>

      <Card className="bg-card border-border">
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-6 space-y-4">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          ) : !signals || signals.length === 0 ? (
            <div className="text-sm text-muted-foreground py-12 text-center">No signals recorded</div>
          ) : (
            <Table>
              <TableHeader className="bg-muted/50">
                <TableRow className="border-border hover:bg-transparent">
                  <TableHead className="font-mono text-xs">TIME</TableHead>
                  <TableHead className="font-mono text-xs">ACTION</TableHead>
                  <TableHead className="font-mono text-xs">PAIR A / B</TableHead>
                  <TableHead className="font-mono text-xs text-right font-medium">ENTRY</TableHead>
                  <TableHead className="font-mono text-xs text-right text-red-400 font-medium">SL</TableHead>
                  <TableHead className="font-mono text-xs text-right text-green-400 font-medium">TP1</TableHead>
                  <TableHead className="font-mono text-xs text-right text-green-400 font-medium">TP2</TableHead>
                  <TableHead className="font-mono text-xs text-right text-green-400 font-medium">TP3</TableHead>
                  <TableHead className="font-mono text-xs text-center">TARGETS</TableHead>
                  <TableHead className="font-mono text-xs text-right">LOTS</TableHead>
                  <TableHead className="font-mono text-xs text-right">P&L</TableHead>
                  <TableHead className="font-mono text-xs text-right">Z-SCORE</TableHead>
                  <TableHead className="font-mono text-xs text-center">ACTION</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {signals.map((sig) => {
                  const details = getSignalDetails(sig);
                  const tradesList = sig.trades ?? [];
                  const totalProfitVal = sig.totalProfit;
                  const handleCopySignal = (sig: any) => {
    const isBuy = sig.action === "BUY_SPREAD";
    const details = getSignalDetails(sig);
    const timeStr = format(new Date(sig.timestamp), "EEEE, dd/MM/yyyy, hh:mm:ss a");
    
    const actionEmoji = isBuy ? "🟢" : "🔴";
    const legBDirection = isBuy ? "SELL" : "BUY";

    const defaultLots = config?.defaultLots ?? 0.01;
    const partLotsA = (defaultLots / 3.0).toFixed(2);
    const totalLotsA = defaultLots.toFixed(2);
    const lotsB = (defaultLots * Number(sig.beta ?? 1.0)).toFixed(2);

    const text = `📢 *AWAIS JANE STREET QUANTUM ENGINE SIGNAL* 📢\n\n` +
      `${actionEmoji} *ACTION:* ${sig.action} (${sig.symbolA} / ${sig.symbolB})\n` +
      `⏱ *Time:* ${timeStr}\n` +
      `📊 *Z-Score:* ${sig.zScore.toFixed(3)}\n\n` +
      `🛡 *LEG A (${sig.symbolA}) - 3 Parts:*\n` +
      `  📥 *Entry:* ${details.entry}\n` +
      `  ⛔ *Stop Loss (SL):* ${details.sl}\n` +
      `  🎯 *TP1:* ${details.tp1}\n` +
      `  🎯 *TP2:* ${details.tp2}\n` +
      `  🎯 *TP3:* ${details.tp3}\n` +
      `  📦 *Lots:* 3 parts of ${partLotsA} (Total ${totalLotsA})\n\n` +
      `⚖ *LEG B (${sig.symbolB}) - Hedge:*\n` +
      `  📥 *Entry:* ${details.entryB}\n` +
      `  ⛔ *Stop Loss (SL):* ${details.slB}\n` +
      `  🎯 *TP:* Dynamic (Spread Reversion)\n` +
      `  📦 *Lots:* ${lotsB}\n` +
      `  📥 *Position:* ${legBDirection}`;

    navigator.clipboard.writeText(text).then(() => {
      toast({
        title: "📋 Copied to Clipboard!",
        description: "Signal text formatted for WhatsApp has been copied successfully.",
      });
    }).catch(() => {
      toast({
        title: "❌ Failed to Copy",
        description: "Could not copy signal to clipboard.",
        variant: "destructive"
      });
    });
  };

  return (
                    <TableRow key={sig.id} className="border-border hover:bg-muted/30">
                      <TableCell className="font-mono text-xs text-muted-foreground">
                        {format(new Date(sig.timestamp), "EEEE, dd/MM/yyyy, hh:mm:ss a")}
                      </TableCell>
                      <TableCell>{getActionBadge(sig.action)}</TableCell>
                      <TableCell className="font-mono text-sm">
                        <div className="flex flex-col">
                          <span>{sig.symbolA}</span>
                          <span className="text-[10px] text-muted-foreground">{sig.symbolB}</span>
                        </div>
                      </TableCell>
                      <TableCell className="font-mono text-right text-sm">{details.entry}</TableCell>
                      <TableCell className="font-mono text-right text-sm text-red-400">{details.sl}</TableCell>
                      <TableCell className="font-mono text-right text-sm text-green-400">{details.tp1}</TableCell>
                      <TableCell className="font-mono text-right text-sm text-green-400/80">{details.tp2}</TableCell>
                      <TableCell className="font-mono text-right text-sm text-green-400/60">{details.tp3}</TableCell>
                      <TableCell className="text-center">
                        <div className="flex items-center justify-center gap-1">
                          <div className="flex flex-col gap-0.5">
                            <span className="text-[8px] text-muted-foreground">TP1</span>
                            {getTpPill("TP1", tradesList)}
                          </div>
                          <div className="flex flex-col gap-0.5">
                            <span className="text-[8px] text-muted-foreground">TP2</span>
                            {getTpPill("TP2", tradesList)}
                          </div>
                          <div className="flex flex-col gap-0.5">
                            <span className="text-[8px] text-muted-foreground">TP3</span>
                            {getTpPill("TP3", tradesList)}
                          </div>
                          {tradesList.some((t: any) => t.comment && t.comment.includes("HEDGE")) && (
                            <div className="flex flex-col gap-0.5">
                              <span className="text-[8px] text-muted-foreground">HEDGE</span>
                              {getHedgePill(tradesList)}
                            </div>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="font-mono text-right text-sm text-muted-foreground">
                        {sig.totalLots !== undefined ? sig.totalLots.toFixed(2) : "—"}
                      </TableCell>
                      <TableCell className={cn(
                        "font-mono text-right text-sm font-semibold",
                        totalProfitVal != null ? (totalProfitVal >= 0 ? "text-green-500" : "text-red-500") : "text-muted-foreground"
                      )}>
                        {totalProfitVal != null ? (totalProfitVal >= 0 ? "+" : "") + totalProfitVal.toFixed(2) : "—"}
                      </TableCell>
                      <TableCell className={cn(
                        "font-mono text-right font-bold text-sm",
                        Math.abs(sig.zScore) >= 2 ? (sig.zScore > 0 ? "text-red-500" : "text-green-500") : "text-foreground"
                      )}>
                        {sig.zScore.toFixed(3)}
                      </TableCell>
                      <TableCell className="text-center">
                        <div className="flex items-center justify-center gap-1.5">
                          <Button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleExecuteSignal(sig);
                            }}
                            size="sm"
                            className="bg-emerald-600 hover:bg-emerald-500 text-white font-mono text-[10px] font-bold h-7 px-2"
                            disabled={executeTrade.isPending || isReadOnly}
                          >
                            ⚡ EXECUTE
                          </Button>
                          <Button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleCopySignal(sig);
                            }}
                            size="sm"
                            className="bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border border-zinc-700 font-mono text-[10px] font-bold h-7 px-2"
                          >
                            📋 COPY
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
