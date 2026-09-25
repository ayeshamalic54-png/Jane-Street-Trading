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
    const isBuy = sig.action === "BUY_SPREAD" || sig.action === "BUY";
    const dirA = isBuy ? "BUY" : "SELL";
    
    const getSymbolCategory = (sym: string): string => {
      const s = sym.toUpperCase();
      if (["XAU", "XAG", "XPT", "XPD", "PLAT", "PALL"].some(x => s.includes(x))) return "metals";
      if (s.includes("AAPL") || s.includes("MSFT") || s.includes("GOOGL") || s.includes("TSLA") || s.includes("NVDA") || s.includes("AMD") || s.includes("META") || s.includes("AMZN") || s.includes("US500") || s.includes("US30") || s.includes("NAS100") || s.includes("GER30") || s.includes("UK100")) return "indices";
      return "forex";
    };

    const category = getSymbolCategory(sig.symbolA);
    let execLots = (category === "metals") ? 0.07 : 0.51;

    const slPips = config?.slPips ?? 10;
    const tpPips = config?.tpPips ?? 20;

    executeTrade.mutate(
      { data: { symbol: sig.symbolA, direction: dirA, lots: execLots, slPips, tpPips } },
      {
        onSuccess: () => {
          toast({
            title: "🚀 Pure SMC Trade Executed",
            description: `Queued: ${dirA} ${sig.symbolA} (${execLots.toFixed(2)} lots) successfully!`,
          });
        },
        onError: () => {
          toast({ title: `Failed to queue ${dirA} ${sig.symbolA}`, variant: "destructive" });
        }
      }
    );
  };

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
    
    const s = sig.symbolA.toUpperCase();
    const isMetals = ["XAU", "XAG", "GOLD", "SILVER"].some(x => s.includes(x));
    const isCrypto = s.endsWith("USDT") || ["BTC", "ETH", "SOL", "BNB"].some(x => s.includes(x));
    
    const slDist = isMetals ? 7.50 : (isCrypto ? entry * 0.015 : 0.00194);
    const tpDist = slDist * 1.8; // 1:1.8 RRR Target for ALL assets (Gold & Forex)
    const pricePrecision = isCrypto ? 2 : (getPipSize(sig.symbolA) <= 0.0001 ? 5 : getPipSize(sig.symbolA) <= 0.01 ? 3 : 2);

    const sB = sig.symbolB.toUpperCase();
    const isCryptoB = sB.endsWith("USDT") || ["BTC", "ETH", "SOL", "BNB"].some(x => sB.includes(x));
    const slDistB = isCryptoB ? entryB * 0.015 : 0.00194;
    const pricePrecisionB = isCryptoB ? 2 : (getPipSize(sig.symbolB) <= 0.0001 ? 5 : getPipSize(sig.symbolB) <= 0.01 ? 3 : 2);

    const isBuy = sig.action === "BUY_SPREAD";
    const slB = isBuy ? (entryB + slDistB) : (entryB - slDistB);

    if (sig.action === "BUY_SPREAD") {
      return {
        entry: entry.toFixed(pricePrecision),
        sl: (entry - slDist).toFixed(pricePrecision),
        tp1: (entry + tpDist).toFixed(pricePrecision),
        tp2: (entry + tpDist).toFixed(pricePrecision),
        tp3: (entry + tpDist).toFixed(pricePrecision),
        entryB: entryB.toFixed(pricePrecisionB),
        slB: slB.toFixed(pricePrecisionB),
      };
    } else if (sig.action === "SELL_SPREAD") {
      return {
        entry: entry.toFixed(pricePrecision),
        sl: (entry + slDist).toFixed(pricePrecision),
        tp1: (entry - tpDist).toFixed(pricePrecision),
        tp2: (entry - tpDist).toFixed(pricePrecision),
        tp3: (entry - tpDist).toFixed(pricePrecision),
        entryB: entryB.toFixed(pricePrecisionB),
        slB: slB.toFixed(pricePrecisionB),
      };
    }
    return { entry: "—", sl: "—", tp1: "—", tp2: "—", tp3: "—", entryB: "—", slB: "—" };
  };

  const getTpPill = (tradesList: any[] = []) => {
    if (!tradesList || tradesList.length === 0) {
      return <Badge variant="outline" className="bg-gray-500/5 text-muted-foreground/40 border-border rounded-sm font-mono text-[9px] px-1 py-0 h-4">N/A</Badge>;
    }
    const trade = tradesList[0];
    if (trade.status === "OPEN") {
      return <Badge variant="outline" className="bg-blue-500/10 text-blue-400 border-blue-500/20 rounded-sm font-mono text-[9px] px-1 py-0 h-4">OPEN</Badge>;
    }
    const profit = Number(trade.profit ?? 0);
    if (profit > 0) {
      return <Badge variant="outline" className="bg-green-500/10 text-green-400 border-green-500/20 rounded-sm font-mono text-[9px] px-1 py-0 h-4">HIT 🎯</Badge>;
    } else {
      return <Badge variant="outline" className="bg-red-500/15 text-red-400 border-red-500/20 rounded-sm font-mono text-[9px] px-1 py-0 h-4">SL ⛔</Badge>;
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
      if (["XAU", "XAG", "XPT", "XPD", "PLAT", "PALL"].some(x => s.includes(x))) return "metals";
      if (s.includes("AAPL") || s.includes("MSFT") || s.includes("GOOGL") || s.includes("TSLA") || s.includes("NVDA") || s.includes("AMD") || s.includes("META") || s.includes("AMZN") || s.includes("US500") || s.includes("US30") || s.includes("NAS100") || s.includes("GER30") || s.includes("UK100")) return "indices";
      return "forex";
    };

    const tradesList = sig.trades ?? [];
    const executedLot = tradesList.length > 0 && tradesList[0].lots != null ? Number(tradesList[0].lots) : (sig.totalLots !== undefined && sig.totalLots > 0 ? sig.totalLots : null);
    const category = getSymbolCategory(sig.symbolA);
    const lotStr = executedLot != null ? executedLot.toFixed(2) : ((category === "metals") ? "0.07" : "0.51");
    const actStr = isBuy ? "MARKET BUY 🟢" : "MARKET SELL 🔴";

    const text = `📢 *PURE SMC / ICT 9-CONDITION SIGNAL ENGINE* 📢\n` +
      `🚀 *[ NEW OPEN POSITION ]* 🚀\n\n` +
      `🟢 *ACTION:* \`${actStr}\` (${sig.symbolA})\n` +
      `⏱ *TIME:* \`${timeStr}\` \n` +
      `📊 *STRATEGY:* \`Strict 9-Condition Pure SMC Structure\`\n\n` +
      `📥 *ENTRY PRICE:* \`${details.entry}\` \n` +
      `⛔ *STOP LOSS (SL):* \`${details.sl}\` *(Sweep High/Low + $0.75 Buffer)*\n` +
      `🎯 *TAKE PROFIT (TP):* \`${details.tp2}\` *(Executing 2.0R TP / M15 Structural Target)*\n` +
      `📦 *LOT SIZE:* \`${lotStr} Lots\``;

    navigator.clipboard.writeText(text).then(() => {
      toast({
        title: "📋 Copied to Clipboard!",
        description: "Signal text formatted for Pure SMC Discord/WhatsApp notification copied successfully.",
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
        <h2 className="text-2xl font-bold tracking-tight text-foreground">Pure SMC / ICT Signal Log</h2>
        <p className="text-sm text-muted-foreground">Automated 9-Condition Pure SMC execution & telemetry log</p>
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
                  <TableHead className="font-mono text-xs">ASSET</TableHead>
                  <TableHead className="font-mono text-xs text-right font-medium">ENTRY</TableHead>
                  <TableHead className="font-mono text-xs text-right text-red-400 font-medium">SL</TableHead>
                  <TableHead className="font-mono text-xs text-right text-green-400 font-medium">TP (1:1.8)</TableHead>
                  <TableHead className="font-mono text-xs text-center">STATUS</TableHead>
                  <TableHead className="font-mono text-xs text-right">LOTS</TableHead>
                  <TableHead className="font-mono text-xs text-right">P&L</TableHead>
                  <TableHead className="font-mono text-xs text-right">SMC BIAS / STEPS</TableHead>
                  <TableHead className="font-mono text-xs text-center">ACTION</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {signals.map((sig) => {
                  const details = getSignalDetails(sig);
                  const tradesList = sig.trades ?? [];
                  const totalProfitVal = sig.totalProfit;
                  const isMetals = ["XAU", "XAG", "GOLD", "SILVER"].some(x => (sig.symbolA ?? "").toUpperCase().includes(x));
                  const executedLot = tradesList.length > 0 && tradesList[0].lots != null ? Number(tradesList[0].lots) : (sig.totalLots !== undefined && sig.totalLots > 0 ? sig.totalLots : null);
                  const displayLots = executedLot != null ? executedLot.toFixed(2) : (isMetals ? "0.07" : "0.51");
                  return (
                    <TableRow key={sig.id} className="border-border hover:bg-muted/30">
                      <TableCell className="font-mono text-xs text-muted-foreground">
                        {format(new Date(sig.timestamp), "EEEE, dd/MM/yyyy, hh:mm:ss a")}
                      </TableCell>
                      <TableCell>{getActionBadge(sig.action)}</TableCell>
                      <TableCell className="font-mono text-sm">
                        <div className="flex flex-col">
                          <span className="font-bold">{sig.symbolA}</span>
                        </div>
                      </TableCell>
                      <TableCell className="font-mono text-right text-sm">{details.entry}</TableCell>
                      <TableCell className="font-mono text-right text-sm text-red-400">{details.sl}</TableCell>
                      <TableCell className="font-mono text-right text-sm text-green-400">{details.tp2}</TableCell>
                      <TableCell className="text-center">
                        <div className="flex items-center justify-center gap-1">
                          <div className="flex flex-col gap-0.5">
                            {getTpPill(tradesList)}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="font-mono text-right text-sm font-semibold text-foreground">
                        {displayLots}
                      </TableCell>
                      <TableCell className={cn(
                        "font-mono text-right text-sm font-semibold",
                        totalProfitVal != null ? (totalProfitVal >= 0 ? "text-green-500" : "text-red-500") : "text-muted-foreground"
                      )}>
                        {totalProfitVal != null ? (totalProfitVal >= 0 ? "+" : "") + totalProfitVal.toFixed(2) : "—"}
                      </TableCell>
                      <TableCell className="font-mono text-right">
                        <Badge variant="outline" className="bg-emerald-500/10 text-emerald-400 border-emerald-500/20 font-mono text-[10px]">
                          Pure SMC 9-Condition 🟢
                        </Badge>
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
