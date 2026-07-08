import { useGetPrices, getGetPricesQueryKey } from "@workspace/api-client-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

type Category = "all" | "forex" | "crypto" | "metals" | "stocks";

const CATEGORY_LABELS: Record<Category, string> = {
  all: "All Markets",
  forex: "Forex",
  crypto: "Crypto",
  metals: "Metals / Commodities",
  stocks: "Stocks / CFD",
};

const SOURCE_COLORS: Record<string, string> = {
  Binance: "bg-yellow-500/10 text-yellow-500 border-yellow-500/20",
  Frankfurter: "bg-blue-500/10 text-blue-500 border-blue-500/20",
  "MT5-CFD": "bg-purple-500/10 text-purple-500 border-purple-500/20",
  Estimated: "bg-muted text-muted-foreground border-border",
};

function formatPrice(price: number, category: string): string {
  if (category === "crypto" && price > 1000) return price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (category === "crypto" && price < 1) return price.toFixed(6);
  if (category === "forex") return price.toFixed(5);
  if (category === "metals") return price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return price.toFixed(2);
}

export default function Markets() {
  const [category, setCategory] = useState<Category>("all");

  const { data: prices, isLoading, dataUpdatedAt } = useGetPrices(
    { category },
    { query: { queryKey: getGetPricesQueryKey({ category }), refetchInterval: 10000 } }
  );

  const grouped: Record<string, typeof prices> = {};
  if (prices) {
    for (const p of prices) {
      if (!grouped[p.category]) grouped[p.category] = [];
      grouped[p.category]!.push(p);
    }
  }

  const categoryOrder: Category[] = ["forex", "crypto", "metals", "stocks"];

  return (
    <div className="flex flex-col h-full overflow-auto bg-background p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Live Markets</h2>
          <p className="text-sm text-muted-foreground">
            Crypto: Binance live · Forex: Frankfurter · Metals: Binance · Stocks: MT5 CFD
            {dataUpdatedAt ? ` · Updated ${new Date(dataUpdatedAt).toLocaleTimeString()}` : ""}
          </p>
        </div>
      </div>

      {/* Category filter */}
      <div className="flex gap-2 flex-wrap">
        {(Object.keys(CATEGORY_LABELS) as Category[]).map((cat) => (
          <button
            key={cat}
            onClick={() => setCategory(cat)}
            className={cn(
              "px-3 py-1.5 text-xs font-mono font-semibold uppercase tracking-wider rounded-sm border transition-colors",
              category === cat
                ? "bg-primary text-primary-foreground border-primary"
                : "bg-transparent text-muted-foreground border-border hover:border-primary/50 hover:text-foreground"
            )}
          >
            {CATEGORY_LABELS[cat]}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {Array.from({ length: 12 }).map((_, i) => <Skeleton key={i} className="h-24 w-full" />)}
        </div>
      ) : !prices?.length ? (
        <div className="text-center text-muted-foreground py-12">No price data available</div>
      ) : (
        <div className="space-y-6">
          {(category === "all" ? categoryOrder : [category as Exclude<Category, "all">]).map((cat) => {
            const catPrices = grouped[cat] ?? [];
            if (!catPrices.length) return null;
            return (
              <div key={cat}>
                <div className="flex items-center gap-2 mb-3">
                  <h3 className="text-xs font-mono font-semibold uppercase tracking-widest text-muted-foreground">
                    {CATEGORY_LABELS[cat as Category]}
                  </h3>
                  <div className="flex-1 h-px bg-border" />
                </div>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
                  {catPrices.map((p) => {
                    const hasChange = p.changePct24h != null;
                    const up = hasChange && p.changePct24h! > 0;
                    const down = hasChange && p.changePct24h! < 0;
                    return (
                      <Card key={p.symbol} className="bg-card border-border hover:border-primary/30 transition-colors">
                        <CardContent className="p-3 space-y-2">
                          <div className="flex items-start justify-between gap-1">
                            <span className="font-mono font-bold text-sm leading-tight">{p.symbol}</span>
                            <Badge variant="outline" className={cn("text-[10px] rounded-sm px-1.5 shrink-0", SOURCE_COLORS[p.source] ?? SOURCE_COLORS.Estimated)}>
                              {p.source}
                            </Badge>
                          </div>
                          <div className={cn(
                            "text-lg font-mono font-bold",
                            up ? "text-green-500" : down ? "text-red-500" : "text-foreground"
                          )}>
                            {formatPrice(p.price, p.category)}
                          </div>
                          {hasChange ? (
                            <div className={cn(
                              "flex items-center gap-1 text-xs font-mono",
                              up ? "text-green-500" : down ? "text-red-500" : "text-muted-foreground"
                            )}>
                              {up ? <TrendingUp className="h-3 w-3" /> : down ? <TrendingDown className="h-3 w-3" /> : <Minus className="h-3 w-3" />}
                              {up ? "+" : ""}{p.changePct24h!.toFixed(2)}%
                            </div>
                          ) : (
                            <div className="text-[10px] text-muted-foreground font-mono">24h change N/A</div>
                          )}
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
