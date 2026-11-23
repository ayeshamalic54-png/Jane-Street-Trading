import { useGetSignals, getGetSignalsQueryKey, useGetConfig, useExecuteTrade } from "@workspace/api-client-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, formatPktDateTime } from "@/lib/utils";
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

  const getSymbolCategory = (sym: string): string => {
    const s = (sym ?? "").toUpperCase();
    if (["XAU", "XAG", "XPT", "XPD", "PLAT", "PALL", "GOLD", "SILVER"].some(x => s.includes(x))) return "metals";
    if (["US500", "US30", "NAS100", "USTEC", "GER30", "UK100", "SPX", "DJI", "NDX"].some(x => s.includes(x))) return "indices";
    if (["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMD", "META", "AMZN"].some(x => s.includes(x))) return "stocks";
    if (s.endsWith("USDT") || ["BTC", "ETH", "SOL", "BNB"].some(x => s.includes(x))) return "crypto";
    return "forex";
  };

  const resolveSignalLots = (sig: any, tradesList: any[] = []): number => {
    if (tradesList.length > 0 && tradesList[0].lots != null) return Number(tradesList[0].lots);
    if (sig.signalLots != null && Number(sig.signalLots) > 0) return Number(sig.signalLots);
    if (sig.totalLots != null && Number(sig.totalLots) > 0) return Number(sig.totalLots);
    const cat = getSymbolCategory(sig.symbolA);
    if (cat === "metals") return 0.07;
    if (cat === "indices") return 0.60;
    if (cat === "stocks") return 0.10;
    if (cat === "crypto") return 0.01;
    return 0.51;
  };

  const handleExecuteSignal = (sig: any) => {
    const isBuy = sig.action === "BUY_SPREAD" || sig.action === "BUY";
    const dirA = isBuy ? "BUY" : "SELL";
    const execLots = resolveSignalLots(sig, sig.trades ?? []);

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
    
    const s = (sig.symbolA ?? "").toUpperCase();
    const catA = getSymbolCategory(s);
    const isMetals = catA === "metals";
    const isIndices = catA === "indices";
    const isCrypto = catA === "crypto";
    const isJpy = s.includes("JPY");
    
    const slDist = isMetals ? 7.50 : isIndices ? 45.0 : isCrypto ? entry * 0.015 : isJpy ? 0.20 : 0.00194;
    const tpDist = slDist * 2.0; // Dynamic Opposing Liquidity Target
    const pricePrecision = (isCrypto || isIndices || isMetals) ? 2 : (getPipSize(sig.symbolA) <= 0.0001 ? 5 : getPipSize(sig.symbolA) <= 0.01 ? 3 : 2);

    const sB = (sig.symbolB ?? "").toUpperCase();
    const isCryptoB = getSymbolCategory(sB) === "crypto";
    const slDistB = isCryptoB ? entryB * 0.015 : 0.00194;
    const pricePrecisionB = isCryptoB ? 2 : (getPipSize(sig.symbolB) <= 0.0001 ? 5 : getPipSize(sig.symbolB) <= 0.01 ? 3 : 2);

    const isBuy = sig.action === "BUY_SPREAD" || sig.action === "BUY";
    const slB = isBuy ? (entryB + slDistB) : (entryB - slDistB);

    // Prioritize actual live MT5 / database recorded Entry, SL & TP
    const executedTrade = (sig.trades && sig.trades.length > 0) ? (sig.trades.find((t: any) => t.sl != null) || sig.trades[0]) : null;
    const realSl = (executedTrade?.sl != null ? Number(executedTrade.sl) : null) ?? (sig.sl != null ? Number(sig.sl) : null);
    const realTp = (executedTrade?.tp != null ? Number(executedTrade.tp) : null) ?? (sig.tp != null ? Number(sig.tp) : null);
    const realEntry = executedTrade?.entryPrice != null ? Number(executedTrade.entryPrice) : (executedTrade?.entry != null ? Number(executedTrade.entry) : ((sig as any).entryPrice != null ? Number((sig as any).entryPrice) : entry));

    if (realSl != null && realTp != null && realSl > 0 && realTp > 0) {
      return {
        entry: realEntry.toFixed(pricePrecision),
        sl: realSl.toFixed(pricePrecision),
        tp1: realTp.toFixed(pricePrecision),
        tp2: realTp.toFixed(pricePrecision),
        tp3: realTp.toFixed(pricePrecision),
        entryB: entryB.toFixed(pricePrecisionB),
        slB: slB.toFixed(pricePrecisionB),
      };
    }

    if (isBuy) {
      return {
        entry: realEntry.toFixed(pricePrecision),
        sl: (realEntry - slDist).toFixed(pricePrecision),
        tp1: (realEntry + tpDist).toFixed(pricePrecision),
        tp2: (realEntry + tpDist).toFixed(pricePrecision),
        tp3: (realEntry + tpDist).toFixed(pricePrecision),
        entryB: entryB.toFixed(pricePrecisionB),
        slB: slB.toFixed(pricePrecisionB),
      };
    } else if (sig.action === "SELL_SPREAD" || sig.action === "SELL") {
      return {
        entry: realEntry.toFixed(pricePrecision),
        sl: (realEntry + slDist).toFixed(pricePrecision),
        tp1: (realEntry - tpDist).toFixed(pricePrecision),
        tp2: (realEntry - tpDist).toFixed(pricePrecision),
        tp3: (realEntry - tpDist).toFixed(pricePrecision),
        entryB: entryB.toFixed(pricePrecisionB),
        slB: slB.toFixed(pricePrecisionB),
      };
    }
    return { entry: "—", sl: "—", tp1: "—", tp2: "—", tp3: "—", entryB: "—", slB: "—" };
  };

  const getTpPill = (tradesList: any[] = [], sig?: any) => {
    if (!tradesList || tradesList.length === 0) {
      const sSt = String(sig?.signalStatus ?? "").toUpperCase();
      if (sSt === "TP_HIT") {
        return <Badge variant="outline" className="bg-green-500/15 text-green-400 border-green-500/30 rounded-sm font-mono text-[9px] px-1 py-0 h-4">HIT 🎯</Badge>;
      }
      if (sSt === "SL_HIT") {
        return <Badge variant="outline" className="bg-red-500/15 text-red-400 border-red-500/30 rounded-sm font-mono text-[9px] px-1 py-0 h-4">SL ⛔</Badge>;
      }
      if (sSt === "OPEN") {
        return <Badge variant="outline" className="bg-blue-500/10 text-blue-400 border-blue-500/25 rounded-sm font-mono text-[9px] px-1 py-0 h-4">SIGNAL OPEN</Badge>;
      }
      return <Badge variant="outline" className="bg-amber-500/10 text-amber-400 border-amber-500/20 rounded-sm font-mono text-[9px] px-1 py-0 h-4">SIGNAL ONLY</Badge>;
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
    const isBuy = sig.action === "BUY_SPREAD" || sig.action === "BUY";
    const details = getSignalDetails(sig);
    const timeStr = formatPktDateTime(sig.timestamp);
    const tradesList = sig.trades ?? [];
    const lotStr = resolveSignalLots(sig, tradesList).toFixed(2);
    const category = getSymbolCategory(sig.symbolA);
    const isMetals = category === "metals";
    const isIndices = category === "indices";
    const isM1Mode = String(sig.executionMode ?? "").toUpperCase() === "M1_LTF";
    const condTitle = isM1Mode ? "6-CONDITION M1 LTF ENGINE" : "7-CONDITION M5 SMC ENGINE";
    const stratLabel = isM1Mode ? "6-Condition M1 LTF Pure SMC Structure" : "7-Condition M5 Pure SMC Structure";
    const bufNote = isMetals ? "Sweep High/Low + $0.75 Buffer" : isIndices ? "Sweep High/Low + Structural Index Buffer" : "Sweep High/Low + Structural Pip Buffer";
    const actStr = isBuy ? "MARKET BUY 🟢" : "MARKET SELL 🔴";
    const sigSt = String(sig.signalStatus ?? "").toUpperCase();
    const isClosedSim = sigSt === "TP_HIT" || sigSt === "SL_HIT";
    const isClosedReal = tradesList.length > 0 && tradesList[0].status === "CLOSED";
    const statusHeader = (isClosedReal || isClosedSim)
      ? `🏁 *[ POSITION CLOSED ]* 🏁`
      : tradesList.length > 0
      ? `🚀 *[ NEW OPEN POSITION ]* 🚀`
      : `📢 *[ NEW PURE SMC TRADING SIGNAL ]* 📢`;
    const pnlVal = isClosedReal ? Number(tradesList[0].profit ?? 0) : (isClosedSim && sig.simulatedProfit != null ? Number(sig.simulatedProfit) : null);
    const closeExtra = pnlVal != null
      ? `\n🏁 *RESULT:* \`${pnlVal >= 0 ? "+" : ""}$${pnlVal.toFixed(2)} USD\`${sig.closePrice != null ? ` (Exit: \`${Number(sig.closePrice).toFixed(isMetals || isIndices ? 2 : 5)}\`)` : ""}`
      : "";

    const text = `📢 *PURE SMC / ICT ${condTitle}* 📢\n` +
      `${statusHeader}\n\n` +
      `${isBuy ? "🟢" : "🔴"} *ACTION:* \`${actStr}\` (${sig.symbolA})\n` +
      `⏱ *TIME:* \`${timeStr}\`\n` +
      `📊 *STRATEGY:* \`${stratLabel}\`\n\n` +
      `📥 *ENTRY PRICE:* \`${details.entry}\`\n` +
      `⛔ *STOP LOSS (SL):* \`${details.sl}\` *(${bufNote})*\n` +
      `🎯 *TAKE PROFIT (TP):* \`${details.tp2}\` *(Opposing Liquidity Target)*\n` +
      `📦 *LOT SIZE:* \`${lotStr} Lots\`` +
      closeExtra;

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
    <div className="flex flex-col h-full overflow-auto bg-background p-3 sm:p-6 space-y-4 sm:space-y-6">
      <div>
        <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground">Pure SMC / ICT Signal Log</h2>
        <p className="text-xs sm:text-sm text-muted-foreground">6-Condition M1 LTF (Indices) &amp; 7-Condition M5 SMC Signal &amp; Execution Log</p>
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
                  <TableHead className="font-mono text-xs text-right text-green-400 font-medium">TP (Target)</TableHead>
                  <TableHead className="font-mono text-xs text-center">STATUS</TableHead>
                  <TableHead className="font-mono text-xs text-right">LOTS</TableHead>
                  <TableHead className="font-mono text-xs text-right">P&L</TableHead>
                  <TableHead className="font-mono text-xs text-right">SMC BIAS / STEPS</TableHead>
                  <TableHead className="font-mono text-xs text-center">ACTION</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(() => {
                  const claimedTickets = new Set<number>();
                  const normalizedSignals = signals.map((rawSig: any) => {
                    const rawTrades = [...(rawSig.trades ?? [])].sort((a: any, b: any) => Number(b.ticket || 0) - Number(a.ticket || 0));
                    const matchedTrade = rawTrades.find((t: any) => !claimedTickets.has(Number(t.ticket)));
                    if (matchedTrade) {
                      claimedTickets.add(Number(matchedTrade.ticket));
                      const singleTrades = [matchedTrade];
                      const singleProfit = matchedTrade.profit != null ? Number(matchedTrade.profit) : rawSig.totalProfit;
                      return {
                        ...rawSig,
                        priceA: matchedTrade.entryPrice != null ? Number(matchedTrade.entryPrice) : rawSig.priceA,
                        sl: matchedTrade.sl != null ? Number(matchedTrade.sl) : rawSig.sl,
                        tp: matchedTrade.tp != null ? Number(matchedTrade.tp) : rawSig.tp,
                        trades: singleTrades,
                        totalProfit: singleProfit,
                      };
                    }
                    if (rawTrades.length > 0) {
                      return { ...rawSig, trades: [], totalProfit: null };
                    }
                    return rawSig;
                  });
                  return normalizedSignals.map((sig: any) => {
                  const details = getSignalDetails(sig);
                  const tradesList = sig.trades ?? [];
                  const totalProfitVal = tradesList.length > 0 ? sig.totalProfit : (sig.simulatedProfit != null ? Number(sig.simulatedProfit) : null);
                  const displayLots = resolveSignalLots(sig, tradesList).toFixed(2);
                  const isM1Row = String(sig.executionMode ?? "").toUpperCase() === "M1_LTF";
                  return (
                    <TableRow key={sig.id} className="border-border hover:bg-muted/30">
                      <TableCell className="font-mono text-xs text-muted-foreground">
                        {formatPktDateTime(sig.timestamp)}
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
                            {getTpPill(tradesList, sig)}
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
                        <Badge variant="outline" className={cn(
                          "font-mono text-[10px]",
                          isM1Row ? "bg-indigo-500/15 text-indigo-300 border-indigo-500/30" : "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                        )}>
                          {isM1Row ? "M1 LTF 6-Cond ⚡" : "M5 SMC 7-Cond 🟢"}
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
                });
                })()}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
