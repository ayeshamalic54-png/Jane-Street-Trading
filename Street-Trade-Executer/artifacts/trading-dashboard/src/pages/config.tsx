import { useGetConfig, useUpdateConfig, getGetConfigQueryKey, getGetDashboardQueryKey, useGetPrices } from "@workspace/api-client-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Form, FormControl, FormDescription, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ShieldAlert } from "lucide-react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { Zap, ZapOff } from "lucide-react";

const configSchema = z.object({
  activePair: z.string().min(1, "Pair is required"),
  slPips: z.coerce.number().min(5).max(500),
  tpPips: z.coerce.number().min(5).max(1000),
  zEntryThreshold: z.coerce.number().min(0.1).max(5.0),
  smcEnabled: z.boolean(),
  autoExecute: z.boolean(),
  cryptoEnabled: z.boolean(),
  metalsEnabled: z.boolean(),
  forexEnabled: z.boolean(),
  indicesEnabled: z.boolean(),
  riskLimitsEnabled: z.boolean(),
  knifeProtectionEnabled: z.boolean(),
  obiEnabled: z.boolean(),
  volatilityFilterEnabled: z.boolean(),
  defaultLots: z.coerce.number().min(0.001).max(500),
  maxDailyTrades: z.coerce.number().min(1).max(1000),
});
type ConfigFormValues = z.infer<typeof configSchema>;

type Category = "forex" | "metals" | "stocks" | "custom";

const PAIR_CATEGORIES: Record<Category, { label: string; pairs: string[] }> = {
  forex: {
    label: "Forex",
    pairs: [
      "EURUSD/GBPUSD", "GBPUSD/EURUSD", "EURUSD/USDJPY", "GBPUSD/USDJPY",
      "AUDUSD/NZDUSD", "EURUSD/USDCHF", "GBPUSD/USDCHF", "EURGBP/EURUSD",
      "EURJPY/GBPJPY", "USDJPY/USDCHF", "EURUSD/AUDUSD", "GBPUSD/AUDUSD",
    ],
  },
  metals: {
    label: "Metals",
    pairs: [
      "XAUUSD/XAGUSD", "XAGUSD/XAUUSD", "XAUUSD/EURUSD", "XAUUSD/GBPUSD",
      "XAUUSD/USDJPY",
    ],
  },

  stocks: {
    label: "Stocks / CFD",
    pairs: [
      "AAPL/MSFT", "MSFT/GOOGL", "AAPL/GOOGL", "TSLA/AAPL",
      "NVDA/AMD", "META/GOOGL", "AMZN/AAPL", "TSLA/NVDA",
    ],
  },
  custom: { label: "Custom", pairs: [] },
};

const FUNDED_NEXT_RULES = [
  { rule: "Max Daily Loss", value: "5% limit (Stellar)", botValue: "4.2% Bot Halt Buffer (Safe)", safe: true },
  { rule: "Max Overall Loss", value: "10% limit (Challenge)", botValue: "Managed via active drawdown checks", safe: true },
  { rule: "Quick Strike Rule", value: "Hold trades >= 30s", botValue: "Bot enforces 31s min hold on all exits", safe: true },
  { rule: "News Trading (Funded)", value: "5m before/after split", botValue: "Only 40% profit counts (Losses apply)", safe: true },
  { rule: "IP Consistency", value: "No shared VPN/VPS", botValue: "Dedicated IP required; Avoid US servers", safe: true },
  { rule: "EA Rule (Competition)", value: "No bots allowed", botValue: "Banned on Competition accounts (Manual only)", safe: false },
  { rule: "EA Rule (Stellar/Funded)", value: "EAs allowed", botValue: "Safe to run bot on Challenge & Funded", safe: true },
  { rule: "Grid / Martingale", value: "Restricted", botValue: "Bot runs single hedged mean-reversion", safe: true },
  { rule: "Min Trading Days", value: "5 separate days (Comp)", botValue: "Runs continuously to meet days", safe: true },
];

export default function Config() {
  const { toast } = useToast();
  const [currentPass, setCurrentPass] = useState("");
  const [newPass, setNewPass] = useState("");
  const [confirmPass, setConfirmPass] = useState("");
  const isReadOnly = localStorage.getItem("wasee_role") === "user";

  const handleChangePassword = async () => {
    if (newPass !== confirmPass) {
      toast({
        title: "❌ Passwords Mismatch",
        description: "New password and confirmation password do not match.",
        variant: "destructive"
      });
      return;
    }

    try {
      const res = await fetch("/api/config/password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ currentPassword: currentPass, newPassword: newPass }),
      });

      if (res.ok) {
        toast({
          title: "🔑 Password Updated",
          description: "Admin master password updated successfully in the database.",
        });
        setCurrentPass("");
        setNewPass("");
        setConfirmPass("");
      } else {
        const data = await res.json();
        toast({
          title: "❌ Update Failed",
          description: data.error || "Failed to update admin password.",
          variant: "destructive"
        });
      }
    } catch (err) {
      toast({
        title: "❌ Connection Error",
        description: "Could not connect to the password update server.",
        variant: "destructive"
      });
    }
  };
  const queryClient = useQueryClient();
  const [activeCategory, setActiveCategory] = useState<Category>("forex");
  const [customA, setCustomA] = useState("");
  const [customB, setCustomB] = useState("");

  const { data: config, isLoading } = useGetConfig({
    query: { queryKey: getGetConfigQueryKey() },
  });



  const updateConfig = useUpdateConfig();

  const form = useForm<ConfigFormValues>({
    resolver: zodResolver(configSchema),
    defaultValues: {
      activePair: "",
      slPips: 35,
      tpPips: 70,
      zEntryThreshold: 2.0,
      smcEnabled: true,
      autoExecute: true,
      cryptoEnabled: true,
      metalsEnabled: true,
      forexEnabled: true,
      indicesEnabled: true,
      riskLimitsEnabled: true,
      knifeProtectionEnabled: true,
      obiEnabled: true,
      volatilityFilterEnabled: true,
      defaultLots: 0.01,
      maxDailyTrades: 3,
    },
    values: config
      ? {
          activePair: config.activePair,
          slPips: config.slPips,
          tpPips: (config as any).tpPips ?? 70,
          zEntryThreshold: config.zEntryThreshold,
          smcEnabled: config.smcEnabled,
          autoExecute: config.autoExecute,
          cryptoEnabled: config.cryptoEnabled,
          metalsEnabled: config.metalsEnabled,
          forexEnabled: config.forexEnabled,
          indicesEnabled: config.indicesEnabled,
          riskLimitsEnabled: config.riskLimitsEnabled,
          knifeProtectionEnabled: (config as any).knifeProtectionEnabled ?? true,
          obiEnabled: (config as any).obiEnabled ?? true,
          volatilityFilterEnabled: (config as any).volatilityFilterEnabled ?? true,
          defaultLots: (config as any).defaultLots ?? 0.01,
          maxDailyTrades: config.maxDailyTrades,
        }
      : undefined,
  });

  const activePairVal = form.watch("activePair");
  const autoExecuteVal = form.watch("autoExecute");

  const selectPair = (pair: string) => {
    form.setValue("activePair", pair, { shouldDirty: true, shouldTouch: true });
  };

  const applyCustom = () => {
    const a = customA.trim().toUpperCase();
    const b = customB.trim().toUpperCase();
    if (a && b && a !== b) {
      selectPair(`${a}/${b}`);
    }
  };

  const onSubmit = (data: ConfigFormValues) => {
    updateConfig.mutate({ data }, {
      onSuccess: () => {
        toast({ title: "Configuration saved", description: `Active pair: ${data.activePair}` });
        queryClient.invalidateQueries({ queryKey: getGetConfigQueryKey() });
        queryClient.invalidateQueries({ queryKey: getGetDashboardQueryKey() });
      },
      onError: () => {
        toast({ title: "Update failed", variant: "destructive" });
      },
    });
  };

  if (isLoading || !config) {
    return (
      <div className="flex flex-col h-full overflow-auto bg-background p-6 space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-[500px] w-full" />
      </div>
    );
  }

  const currentCatPairs = PAIR_CATEGORIES[activeCategory].pairs;

  return (
    <div className="flex flex-col h-full overflow-auto bg-background p-6 space-y-6">
      {isReadOnly && (
        <Alert className="bg-red-500/5 text-red-400 border-red-500/20 py-2.5 rounded-sm">
          <div className="flex gap-2 items-center">
            <ShieldAlert className="h-4 w-4 shrink-0" />
            <AlertDescription className="text-xs font-mono font-bold">
              ⚠️ VIEWER MODE: Configuration changes and action triggers are disabled.
            </AlertDescription>
          </div>
        </Alert>
      )}
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Bot Configuration</h2>
        <p className="text-sm text-muted-foreground">
          Trading pair · execution parameters · auto/manual mode · FundedNext rules
        </p>
      </div>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
          <fieldset disabled={isReadOnly} className="space-y-6">
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">

            {/* PAIR SELECTOR */}
            <Card className="bg-card border-border xl:col-span-2">
              <CardHeader>
                <CardTitle className="text-sm uppercase tracking-wider text-muted-foreground">Active Trading Pair</CardTitle>
                <CardDescription>
                  Current: <span className="font-mono text-primary font-bold">{activePairVal || config.activePair}</span>
                  <span className="ml-2 text-xs text-muted-foreground">· Forex / Metals / Stocks / Custom</span>
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Category tabs */}
                <div className="flex gap-2 flex-wrap">
                  {(Object.keys(PAIR_CATEGORIES) as Category[]).map((cat) => (
                    <button
                      key={cat}
                      type="button"
                      onClick={() => setActiveCategory(cat)}
                      className={cn(
                        "px-3 py-1.5 text-xs font-mono font-semibold uppercase tracking-wider rounded-sm border transition-colors",
                        activeCategory === cat
                          ? "bg-primary text-primary-foreground border-primary"
                          : "bg-transparent text-muted-foreground border-border hover:border-primary/50 hover:text-foreground"
                      )}
                    >
                      {PAIR_CATEGORIES[cat].label}
                    </button>
                  ))}
                </div>

                {/* Pair grid */}
{activeCategory !== "custom" ? (
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                    {currentCatPairs.map((pair) => (
                      <button
                        key={pair}
                        type="button"
                        onClick={() => selectPair(pair)}
                        className={cn(
                          "px-3 py-2 text-xs font-mono rounded-sm border text-left transition-all",
                          activePairVal === pair
                            ? "bg-primary/15 border-primary text-primary"
                            : "bg-muted/30 border-border text-muted-foreground hover:border-primary/50 hover:text-foreground"
                        )}
                      >
                        {pair}
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="space-y-3">
                    <p className="text-xs text-muted-foreground">
                      Enter any two MT5 symbols. Must be different. Use exact broker symbol names (e.g. EURUSD, BTCUSD, XAUUSD, US500, AAPL).
                    </p>
                    <div className="flex gap-2 items-end">
                      <div className="flex-1">
                        <label className="text-xs text-muted-foreground uppercase tracking-wider mb-1 block">Leg A Symbol</label>
                        <Input
                          placeholder="e.g. EURUSD"
                          value={customA}
                          onChange={(e) => setCustomA(e.target.value.toUpperCase())}
                          className="font-mono border-border bg-background"
                        />
                      </div>
                      <div className="flex-1">
                        <label className="text-xs text-muted-foreground uppercase tracking-wider mb-1 block">Leg B Symbol</label>
                        <Input
                          placeholder="e.g. GBPUSD"
                          value={customB}
                          onChange={(e) => setCustomB(e.target.value.toUpperCase())}
                          className="font-mono border-border bg-background"
                        />
                      </div>
                      <Button
                        type="button"
                        onClick={applyCustom}
                        variant="outline"
                        className="font-mono text-xs"
                        disabled={!customA.trim() || !customB.trim() || customA.trim() === customB.trim()}
                      >
                        Apply
                      </Button>
                    </div>
                    {activePairVal && activePairVal.includes("/") && (
                      <div className="text-xs text-primary font-mono bg-primary/10 px-3 py-2 rounded-sm border border-primary/20">
                        ✓ Selected: {activePairVal}
                      </div>
                    )}
                  </div>
                )}

                <FormField
                  control={form.control}
                  name="activePair"
                  render={() => (
                    <FormItem>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </CardContent>
            </Card>

            {/* EXECUTION PARAMS */}
            <div className="space-y-4">
              <Card className="bg-card border-border">
                <CardHeader>
                  <CardTitle className="text-sm uppercase tracking-wider text-muted-foreground">Execution Parameters</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">

                  {/* Auto Execute Toggle */}
                  <FormField
                    control={form.control}
                    name="autoExecute"
                    render={({ field }) => (
                      <FormItem>
                        <div className={cn(
                          "flex items-center justify-between p-3 rounded-sm border",
                          field.value
                            ? "bg-green-500/5 border-green-500/30"
                            : "bg-amber-500/5 border-amber-500/30"
                        )}>
                          <div>
                            <FormLabel className="text-xs uppercase tracking-wider flex items-center gap-2">
                              {field.value
                                ? <Zap className="h-3.5 w-3.5 text-green-400" />
                                : <ZapOff className="h-3.5 w-3.5 text-amber-400" />
                              }
                              Auto Execution
                            </FormLabel>
                            <FormDescription className="text-xs mt-0.5">
                              {field.value
                                ? "Bot auto-trades on KF + OBI + SMC signals"
                                : "Signals only — no automatic order placement"
                              }
                            </FormDescription>
                          </div>
                          <FormControl>
                            <Switch checked={field.value} onCheckedChange={field.onChange} />
                          </FormControl>
                        </div>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <FormField
                      control={form.control}
                      name="slPips"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Stop Loss (Pips)</FormLabel>
                          <FormControl>
                            <Input type="number" {...field} className="font-mono border-border bg-background" />
                          </FormControl>
                          <FormDescription className="text-xs">
                            Stop Loss in pips (e.g. 35 pips for safe breathing room).
                          </FormDescription>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="tpPips"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Take Profit (Pips)</FormLabel>
                          <FormControl>
                            <Input type="number" {...field} className="font-mono border-border bg-background" />
                          </FormControl>
                          <FormDescription className="text-xs">
                            Take Profit in pips (e.g. 70 pips for 1:2 R:R main target).
                          </FormDescription>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>

                  <FormField
                    control={form.control}
                    name="zEntryThreshold"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Z-Score Entry Threshold</FormLabel>
                        <FormControl>
                          <Input type="number" step="0.1" {...field} className="font-mono border-border bg-background" />
                        </FormControl>
                        <FormDescription className="text-xs">
                          Threshold in standard deviations (e.g. 2.0). Lower values (like 0.5) trigger trades more frequently.
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="defaultLots"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Default Lot Size (Auto-Trade)</FormLabel>
                        <FormControl>
                          <Input type="number" step="0.01" min="0.001" {...field} className="font-mono border-border bg-background" />
                        </FormControl>
                        <FormDescription className="text-xs">
                          Fixed lot size used for all automatic spread trades. (e.g. 0.01 to risk minimum).
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="maxDailyTrades"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Max Daily Trades Limit</FormLabel>
                        <FormControl>
                          <Input type="number" min="1" {...field} className="font-mono border-border bg-background" />
                        </FormControl>
                        <FormDescription className="text-xs">
                          Maximum number of trades the bot can execute per day. (e.g., set to 100 for no daily limit warnings).
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />



                  <FormField
                    control={form.control}
                    name="smcEnabled"
                    render={({ field }) => (
                      <FormItem>
                        <div className="flex items-center justify-between">
                          <div>
                            <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">SMC / FVG Confluence</FormLabel>
                            <FormDescription className="text-xs mt-0.5">
                              Require FVG/OB zone before entry. Disable if trades aren't firing.
                            </FormDescription>
                          </div>
                          <FormControl>
                            <Switch checked={field.value} onCheckedChange={field.onChange} />
                          </FormControl>
                        </div>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="riskLimitsEnabled"
                    render={({ field }) => (
                      <FormItem>
                        <div className="flex items-center justify-between">
                          <div>
                            <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Enforce Daily Drawdown Limit</FormLabel>
                            <FormDescription className="text-xs mt-0.5">
                              Halt trading if daily drawdown reaches 4.2%. (Auto-bypassed on Demo accounts).
                            </FormDescription>
                          </div>
                          <FormControl>
                            <Switch checked={field.value} onCheckedChange={field.onChange} />
                          </FormControl>
                        </div>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <div className="border-t border-border pt-4 space-y-4">
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Quantitative Safety Filters</h4>

                    {/* Z-Velocity / Knife Protection Toggle */}
                    <FormField
                      control={form.control}
                      name="knifeProtectionEnabled"
                      render={({ field }) => (
                        <FormItem>
                          <div className="flex items-center justify-between">
                            <div>
                              <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Z-Velocity / Knife Protection Filter</FormLabel>
                              <FormDescription className="text-xs mt-0.5">
                                Defer entry if spread is moving too fast (falling/rising knife protection).
                              </FormDescription>
                            </div>
                            <FormControl>
                              <Switch checked={field.value} onCheckedChange={field.onChange} />
                            </FormControl>
                          </div>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    {/* OBI Filter Toggle */}
                    <FormField
                      control={form.control}
                      name="obiEnabled"
                      render={({ field }) => (
                        <FormItem>
                          <div className="flex items-center justify-between">
                            <div>
                              <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Order Book Imbalance (OBI) Filter</FormLabel>
                              <FormDescription className="text-xs mt-0.5">
                                Require order book bid/ask volume imbalance confluence before entry.
                              </FormDescription>
                            </div>
                            <FormControl>
                              <Switch checked={field.value} onCheckedChange={field.onChange} />
                            </FormControl>
                          </div>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    {/* Volatility Protection Toggle */}
                    <FormField
                      control={form.control}
                      name="volatilityFilterEnabled"
                      render={({ field }) => (
                        <FormItem>
                          <div className="flex items-center justify-between">
                            <div>
                              <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Dynamic Volatility Filter</FormLabel>
                              <FormDescription className="text-xs mt-0.5">
                                Scale entry Z-threshold dynamically during high market volatility.
                              </FormDescription>
                            </div>
                            <FormControl>
                              <Switch checked={field.value} onCheckedChange={field.onChange} />
                            </FormControl>
                          </div>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>

                  <div className="border-t border-border pt-4 space-y-4">
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Allowed Asset Classes</h4>
                    
                    {/* Forex Trading Toggle */}
                    <FormField
                      control={form.control}
                      name="forexEnabled"
                      render={({ field }) => (
                        <FormItem>
                          <div className="flex items-center justify-between">
                            <div>
                              <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Forex Pairs</FormLabel>
                              <FormDescription className="text-xs mt-0.5">
                                Enable trading standard Forex pairs.
                              </FormDescription>
                            </div>
                            <FormControl>
                              <Switch checked={field.value} onCheckedChange={field.onChange} />
                            </FormControl>
                          </div>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    {/* Metals Trading Toggle */}
                    <FormField
                      control={form.control}
                      name="metalsEnabled"
                      render={({ field }) => (
                        <FormItem>
                          <div className="flex items-center justify-between">
                            <div>
                              <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Metals (Gold/Silver)</FormLabel>
                              <FormDescription className="text-xs mt-0.5">
                                Enable trading Spot Gold and Silver.
                              </FormDescription>
                            </div>
                            <FormControl>
                              <Switch checked={field.value} onCheckedChange={field.onChange} />
                            </FormControl>
                          </div>
                          <FormMessage />
                        </FormItem>
                      )}
                    />



                    {/* Indices Trading Toggle */}
                    <FormField
                      control={form.control}
                      name="indicesEnabled"
                      render={({ field }) => (
                        <FormItem>
                          <div className="flex items-center justify-between">
                            <div>
                              <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Indices / Stock CFDs</FormLabel>
                              <FormDescription className="text-xs mt-0.5">
                                Enable trading stock index CFDs (e.g. US500, NAS100).
                              </FormDescription>
                            </div>
                            <FormControl>
                              <Switch checked={field.value} onCheckedChange={field.onChange} />
                            </FormControl>
                          </div>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>

                  <div className="pt-2 border-t border-border space-y-2 text-xs text-muted-foreground">
                    <div className="flex justify-between"><span>Z-Score Entry</span><span className="font-mono text-foreground">±{Number(form.watch("zEntryThreshold") ?? 2.0).toFixed(2)}σ</span></div>
                    <div className="flex justify-between"><span>Max Daily Trades</span><span className="font-mono text-foreground">{form.watch("maxDailyTrades") ?? 3}</span></div>
                    <div className="flex justify-between"><span>Risk Per Trade</span><span className="font-mono text-foreground">1% equity</span></div>
                    <div className="flex justify-between"><span>Execution Model</span><span className="font-mono text-foreground">3-Part TP ladder</span></div>
                  </div>
                </CardContent>
              </Card>

              <Button
                type="submit"
                disabled={updateConfig.isPending}
                className="w-full font-mono text-xs bg-primary text-primary-foreground hover:bg-primary/90"
              >
                {updateConfig.isPending ? "SAVING..." : "SAVE CONFIGURATION"}
              </Button>
            </div>
          </div>

          {/* FUNDEDNEXT RULES */}
          <Card className="bg-card border-border">
            <CardHeader>
              <div className="flex items-center gap-2">
                <CardTitle className="text-sm uppercase tracking-wider text-muted-foreground">FundedNext Rules Compliance</CardTitle>
                <Badge className="bg-green-500/15 text-green-500 border-green-500/30 text-xs rounded-sm">SAFE</Badge>
              </div>
              <CardDescription className="text-xs">
                Bot configured to stay within FundedNext limits. 4.2% daily halt = intentional buffer below the 5% hard limit.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                {FUNDED_NEXT_RULES.map((r) => (
                  <div key={r.rule} className="flex flex-col gap-1 p-3 rounded-sm border border-border bg-muted/20">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-muted-foreground">{r.rule}</span>
                      <Badge 
                        variant="outline" 
                        className={cn(
                          "text-[10px] rounded-sm px-1.5 font-bold font-mono uppercase", 
                          r.safe 
                            ? "bg-green-500/10 text-green-400 border-green-500/20" 
                            : "bg-red-500/10 text-red-400 border-red-500/20"
                        )}
                      >
                        {r.safe ? "✓ COMPLIANT" : "✗ BANNED"}
                      </Badge>
                    </div>
                    <div className="text-xs font-mono font-medium text-foreground">{r.value}</div>
                    <div className="text-[10px] text-muted-foreground">{r.botValue}</div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </fieldset>

          {/* PASSWORD CHANGE SECTION */}
          <Card className="bg-card border-border mt-6">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm uppercase tracking-wider text-muted-foreground">Admin Security Settings</CardTitle>
              <CardDescription className="text-xs">
                Update the master administrator credentials for the trading system.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="max-w-md space-y-4">
                <div className="space-y-1">
                  <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono block">Current Password</label>
                  <Input 
                    type="password" 
                    placeholder="••••••••" 
                    value={currentPass}
                    onChange={(e) => setCurrentPass(e.target.value)}
                    disabled={isReadOnly}
                    className="font-mono text-xs border-border bg-zinc-950/40 text-foreground"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono block">New Password</label>
                  <Input 
                    type="password" 
                    placeholder="••••••••" 
                    value={newPass}
                    onChange={(e) => setNewPass(e.target.value)}
                    disabled={isReadOnly}
                    className="font-mono text-xs border-border bg-zinc-950/40 text-foreground"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono block">Confirm New Password</label>
                  <Input 
                    type="password" 
                    placeholder="••••••••" 
                    value={confirmPass}
                    onChange={(e) => setConfirmPass(e.target.value)}
                    disabled={isReadOnly}
                    className="font-mono text-xs border-border bg-zinc-950/40 text-foreground"
                  />
                </div>
                <Button 
                  type="button" 
                  onClick={handleChangePassword}
                  disabled={isReadOnly || !currentPass || !newPass || !confirmPass}
                  className="bg-indigo-600 hover:bg-indigo-500 text-white font-mono text-xs px-4 h-9 font-bold"
                >
                  CHANGE ADMIN PASSWORD
                </Button>
                {isReadOnly && (
                  <div className="text-[10px] text-rose-500 font-mono animate-pulse">
                    🚫 Change password disabled for viewers.
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </form>
      </Form>
    </div>
  );
}
