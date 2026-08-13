import { useState } from "react";
import { useGetTrades, getGetTradesQueryKey } from "@workspace/api-client-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { format } from "date-fns";

export default function Trades() {
  const [status, setStatus] = useState<"ALL" | "OPEN" | "CLOSED">("ALL");

  const { data: trades, isLoading } = useGetTrades({
    limit: 100,
    status: status !== "ALL" ? status : undefined,
  }, {
    query: {
      queryKey: getGetTradesQueryKey({ limit: 100, status: status !== "ALL" ? status : undefined })
    }
  });

  const getOrderTypeBadge = (type: string) => {
    return (
      <Badge variant="outline" className={cn(
        "rounded-sm text-[10px] font-mono",
        type === "BUY" ? "bg-green-500/10 text-green-500 border-green-500/30" : "bg-red-500/10 text-red-500 border-red-500/30"
      )}>
        {type}
      </Badge>
    );
  };

  const getStatusBadge = (s: string) => {
    return (
      <Badge variant="outline" className={cn(
        "rounded-sm text-[10px] font-mono",
        s === "OPEN" ? "bg-blue-500/10 text-blue-500 border-blue-500/30" : "bg-gray-500/10 text-gray-400 border-gray-500/30"
      )}>
        {s}
      </Badge>
    );
  };

  return (
    <div className="flex flex-col h-full overflow-auto bg-background p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-foreground">Trade History</h2>
          <p className="text-sm text-muted-foreground">Historical order execution and P&L logs</p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={status} onValueChange={(val: any) => setStatus(val)}>
            <SelectTrigger className="w-[150px] font-mono text-xs">
              <SelectValue placeholder="Filter Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL" className="font-mono text-xs">ALL STATUS</SelectItem>
              <SelectItem value="OPEN" className="font-mono text-xs">OPEN ONLY</SelectItem>
              <SelectItem value="CLOSED" className="font-mono text-xs">CLOSED ONLY</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <Card className="bg-card border-border">
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-6 space-y-4">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          ) : !trades || trades.length === 0 ? (
            <div className="text-sm text-muted-foreground py-12 text-center">No trades found</div>
          ) : (
            <Table>
              <TableHeader className="bg-muted/50">
                <TableRow className="border-border hover:bg-transparent">
                  <TableHead className="font-mono text-xs">TICKET</TableHead>
                  <TableHead className="font-mono text-xs">TIME</TableHead>
                  <TableHead className="font-mono text-xs">SYMBOL</TableHead>
                  <TableHead className="font-mono text-xs">TYPE</TableHead>
                  <TableHead className="font-mono text-xs text-right">LOTS</TableHead>
                  <TableHead className="font-mono text-xs text-right">ENTRY</TableHead>
                  <TableHead className="font-mono text-xs text-right">EXIT</TableHead>
                  <TableHead className="font-mono text-xs text-right">P&L</TableHead>
                  <TableHead className="font-mono text-xs text-center">STATUS</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {trades.map((trade) => (
                  <TableRow key={trade.ticket} className="border-border hover:bg-muted/30">
                    <TableCell className="font-mono text-xs text-muted-foreground">#{trade.ticket}</TableCell>
                    <TableCell className="font-mono text-xs">
                      <div className="flex flex-col">
                        <span>{format(new Date(trade.entryTime), "EEEE, dd/MM/yyyy, hh:mm:ss a")}</span>
                        {trade.closeTime && (
                          <span className="text-muted-foreground/70">{format(new Date(trade.closeTime), "EEEE, dd/MM/yyyy, hh:mm:ss a")}</span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="font-mono font-medium">{trade.symbol}</TableCell>
                    <TableCell>{getOrderTypeBadge(trade.orderType)}</TableCell>
                    <TableCell className="font-mono text-right">{trade.lots.toFixed(2)}</TableCell>
                    <TableCell className="font-mono text-right">{trade.entryPrice.toFixed(5)}</TableCell>
                    <TableCell className="font-mono text-right">{trade.closePrice?.toFixed(5) || "-"}</TableCell>
                    <TableCell className={cn(
                      "font-mono text-right font-bold",
                      (trade.profit ?? 0) >= 0 ? "text-green-500" : "text-red-500"
                    )}>
                      {trade.profit !== undefined && trade.profit !== null ? (trade.profit > 0 ? "+" : "") + trade.profit.toFixed(2) : "-"}
                    </TableCell>
                    <TableCell className="text-center">{getStatusBadge(trade.status)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
