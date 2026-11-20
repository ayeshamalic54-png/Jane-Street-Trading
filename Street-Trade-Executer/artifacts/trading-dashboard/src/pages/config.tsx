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
  smcEnabled: z.boolean().optional().default(true),
  autoExecute: z.boolean().optional().default(true),
  cryptoEnabled: z.boolean().optional().default(true),
  metalsEnabled: z.boolean().optional().default(true),
  forexEnabled: z.boolean().optional().default(true),
  indicesEnabled: z.boolean().optional().default(true),
  stocksEnabled: z.boolean().optional().default(true),
  m1LtfEnabled: z.boolean().optional().default(true),
  riskLimitsEnabled: z.boolean().optional().default(true),
  knifeProtectionEnabled: z.boolean().optional().default(true),
  obiEnabled: z.boolean().optional().default(true),
  volatilityFilterEnabled: z.boolean().optional().default(true),
  defaultLots: z.coerce.number().min(0).max(500),
  maxDailyTrades: z.coerce.number().min(1).max(1000),
  haltDrawdownLimit: z.coerce.number().min(0.1).max(10.0).optional().default(0.78),
  maxDrawdownLimit: z.coerce.number().min(0.5).max(20.0).optional().default(3.30),
});
type ConfigFormValues = z.infer<typeof configSchema>;

type Category = "forex" | "metals" | "indices" | "stocks" | "custom";

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
      "XAUUSD/XAGUSD", "XAGUSD/XAUUSD", "XPTUSD/XPDUSD", "XAUUSD/XPTUSD",
      "XAUUSD/EURUSD", "XAUUSD/GBPUSD", "XAUUSD/USDJPY",
    ],
  },
  indices: {
    label: "Indices",
    pairs: [
      "US30/NAS100", "NAS100/US30",
    ],
  },
  stocks: {
    label: "Stocks",
    pairs: [
      "AAPL/MSFT", "MSFT/GOOGL", "AAPL/GOOGL", "TSLA/AAPL",
      "NVDA/AMD", "META/GOOGL", "AMZN/AAPL", "TSLA/NVDA",
    ],
  },
  custom: { label: "Custom", pairs: [] },
};

const BLUE_GUARDIAN_RULES = [
  { rule: "Max Daily Loss", value: "3.3% limit", botValue: "0.83% Bot Halt Buffer (Safe)", safe: true },

  { rule: "Max Overall Loss", value: "8% limit (Static Drawdown)", botValue: "Managed via active drawdown checks", safe: true },
  {rule: "Quick Strike Rule", value: "Hold trades >= 140s (2m 20s)", botValue: "Bot enforces 140s min hold on all exits", safe: true },
  { rule: "News Trading", value: "5m before/after split", botValue: "Allowed on Challenge; Restricted on Funded", safe: true },
  { rule: "IP Consistency", value: "No shared VPN/VPS", botValue: "Dedicated IP required; Avoid US servers", safe: true },
  { rule: "EA Rule", value: "EAs allowed", botValue: "Safe to run bot on Challenge & Funded", safe: true },
  { rule: "Grid / Martingale", value: "Restricted", botValue: "Bot runs single hedged mean-reversion", safe: true },
  { rule: "Min Trading Days", value: "No minimum days", botValue: "Trade freely without day limits", safe: true },
];

export default function Config() {
  const { toast } = useToast();
  const [currentPass, setCurrentPass] = useState("");
  const [newPass, setNewPass] = useState("");
  const [confirmPass, setConfirmPass] = useState("");
  const isReadOnly = localStorage.getItem("wasee_role")?.toLowerCase() === "user";
  const [userNewPass, setUserNewPass] = useState("");
  const [userConfirmPass, setUserConfirmPass] = useState("");

  const handleChangeUserPassword = async () => {
    if (userNewPass !== userConfirmPass) {
      toast({
        title: "Passwords Mismatch",
        description: "User new password and confirmation password do not match.",
        variant: "destructive"
      });
      return;
    }

    try {
      const res = await fetch("/api/config/user-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ newUserPassword: userNewPass }),
      });

      if (res.ok) {
        toast({
          title: "User Password Updated",
          description: "User password updated successfully in the database.",
        });
        setUserNewPass("");
        setUserConfirmPass("");
      } else {
        toast({
          title: "Update Failed",
          description: "Could not update user password.",
          variant: "destructive"
        });
      }
    } catch (e) {
      toast({
        title: "Error occurred",
        description: "An error occurred while updating the password.",
        variant: "destructive"
      });
    }
  };

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
      stocksEnabled: true,
      m1LtfEnabled: true,
      riskLimitsEnabled: true,
      knifeProtectionEnabled: true,
      obiEnabled: true,
      volatilityFilterEnabled: true,
      defaultLots: 0.01,
      maxDailyTrades: 3,
      haltDrawdownLimit: 0.80,
      maxDrawdownLimit: 3.30,
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
          stocksEnabled: (config as any).stocksEnabled ?? true,
          m1LtfEnabled: Boolean((config as any).m1LtfEnabled ?? (config as any).m1_ltf_enabled ?? true),
          riskLimitsEnabled: config.riskLimitsEnabled,
          knifeProtectionEnabled: (config as any).knifeProtectionEnabled ?? true,
          obiEnabled: (config as any).obiEnabled ?? true,
          volatilityFilterEnabled: (config as any).volatilityFilterEnabled ?? true,
          defaultLots: (config as any).defaultLots ?? 0.01,
          maxDailyTrades: config.maxDailyTrades,
          haltDrawdownLimit: (config as any).haltDrawdownLimit ?? (config as any).halt_drawdown_limit ?? 0.80,
          maxDrawdownLimit: (config as any).maxDrawdownLimit ?? (config as any).max_drawdown_limit ?? 3.30,
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

  const [m1Saving, setM1Saving] = useState(false);

  const handleM1ToggleImmediate = async (checked: boolean) => {
    if (isReadOnly || m1Saving) return;
    const prevVal = form.getValues("m1LtfEnabled");
    form.setValue("m1LtfEnabled", checked, { shouldDirty: true, shouldTouch: true });
    setM1Saving(true);
    try {
      const res = await fetch("/api/toggle-m1-ltf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: checked }),
      });
      if (!res.ok) throw new Error("Failed to toggle M1 LTF");
      const json = await res.json();
      const confirmed = Boolean(json?.m1LtfEnabled ?? checked);
      queryClient.setQueryData(getGetConfigQueryKey(), (old: any) =>
        old ? { ...old, m1LtfEnabled: confirmed } : old
      );
      queryClient.invalidateQueries({ queryKey: getGetConfigQueryKey() });
      queryClient.invalidateQueries({ queryKey: getGetDashboardQueryKey() });
      toast({
        title: confirmed ? "M1 LTF Execution ON" : "M1 LTF Execution OFF",
        description: confirmed
          ? "US30 & NAS100 now execute 6-Condition M1 LTF entries (Gold/Forex remain M5)."
          : "All instruments now execute strictly 7-Condition M5 SMC entries.",
      });
    } catch {
      form.setValue("m1LtfEnabled", prevVal);
      toast({
        title: "Failed to update M1 LTF toggle",
        description: "Please verify API server connection and retry.",
        variant: "destructive",
      });
    } finally {
      setM1Saving(false);
    }
  };

  const onSubmit = (data: ConfigFormValues) => {
    updateConfig.mutate({ data }, {
      onSuccess: (savedData: any) => {
        queryClient.setQueryData(getGetConfigQueryKey(), (old: any) => ({ ...old, ...savedData, m1LtfEnabled: data.m1LtfEnabled }));
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
      <div className="flex flex-col h-full overflow-auto bg-background p-3 sm:p-6 space-y-4 w-full max-w-[1440px] mx-auto">
        <Skeleton className="h-8 w-56 sm:w-64" />
        <Skeleton className="h-[500px] w-full" />
      </div>
    );
  }

  const currentCatPairs = PAIR_CATEGORIES[activeCategory].pairs;

  return (
    <div className="flex flex-col h-full overflow-auto bg-background p-3 sm:p-6 space-y-4 sm:space-y-6 w-full max-w-[1440px] mx-auto">
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
      <div className="space-y-1">
        <h2 className="text-xl sm:text-2xl font-bold tracking-tight">Bot Configuration</h2>
        <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed">
          Active trading pair · execution parameters · safety filters · Blue Guardian rules
        </p>
      </div>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4 sm:space-y-6">
          <fieldset disabled={isReadOnly} className="space-y-4 sm:space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 sm:gap-6 items-start">

              {/* PAIR SELECTOR */}
              <Card className="bg-card border-border lg:col-span-5">
                <CardHeader className="p-4 sm:p-6">
                  <CardTitle className="text-sm uppercase tracking-wider text-muted-foreground">Active Trading Pair</CardTitle>
                  <CardDescription className="text-xs sm:text-sm break-words leading-relaxed">
                    Current: <span className="font-mono text-primary font-bold">{activePairVal || config.activePair}</span>
                    <span className="ml-1.5 text-xs text-muted-foreground">· Forex / Metals / Indices / Stocks / Custom</span>
                  </CardDescription>
                </CardHeader>
                <CardContent className="p-4 sm:p-6 pt-0 space-y-4">
                  {/* Category tabs */}
                  <div className="flex gap-1.5 sm:gap-2 flex-wrap">
                    {(Object.keys(PAIR_CATEGORIES) as Category[]).map((cat) => (
                      <button
                        key={cat}
                        type="button"
                        onClick={() => setActiveCategory(cat)}
                        className={cn(
                          "px-2.5 sm:px-3 py-1.5 text-[11px] sm:text-xs font-mono font-semibold uppercase tracking-wider rounded-sm border transition-colors",
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
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-2 gap-2">
                      {currentCatPairs.map((pair) => (
                        <button
                          key={pair}
                          type="button"
                          onClick={() => selectPair(pair)}
                          title={pair}
                          className={cn(
                            "px-2.5 sm:px-3 py-2.5 text-[11px] sm:text-xs font-mono rounded-sm border text-left transition-all truncate",
                            activePairVal === pair
                              ? "bg-primary/15 border-primary text-primary font-semibold"
                              : "bg-muted/30 border-border text-muted-foreground hover:border-primary/50 hover:text-foreground"
                          )}
                        >
                          {pair}
                        </button>
                      ))}
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        Enter any two MT5 symbols. Must be different. Use exact broker symbol names (e.g. XAUUSD, US30, NAS100, EURUSD).
                      </p>
                      <div className="flex flex-col sm:flex-row gap-2 sm:items-end">
                        <div className="flex-1 min-w-0">
                          <label className="text-xs text-muted-foreground uppercase tracking-wider mb-1 block">Leg A Symbol</label>
                          <Input
                            placeholder="e.g. EURUSD"
                            value={customA}
                            onChange={(e) => setCustomA(e.target.value.toUpperCase())}
                            className="font-mono border-border bg-background"
                          />
                        </div>
                        <div className="flex-1 min-w-0">
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
                          className="font-mono text-xs w-full sm:w-auto min-h-9 shrink-0"
                          disabled={!customA.trim() || !customB.trim() || customA.trim() === customB.trim()}
                        >
                          Apply
                        </Button>
                      </div>
                      {activePairVal && activePairVal.includes("/") && (
                        <div className="text-xs text-primary font-mono bg-primary/10 px-3 py-2 rounded-sm border border-primary/20 break-words">
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
              <div className="space-y-4 lg:col-span-7">
                <Card className="bg-card border-border">
                  <CardHeader className="p-4 sm:p-6 pb-3 sm:pb-4">
                    <CardTitle className="text-sm uppercase tracking-wider text-muted-foreground">Execution Parameters</CardTitle>
                    <CardDescription className="text-xs">
                      Position sizing, risk caps, quantitative filters &amp; allowed asset classes
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="p-4 sm:p-6 pt-0 space-y-5">

                    {/* Auto Execute Toggle */}
                    <FormField
                      control={form.control}
                      name="autoExecute"
                      render={({ field }) => (
                        <FormItem>
                          <div className={cn(
                            "flex items-center justify-between gap-3 p-3 rounded-sm border",
                            field.value
                              ? "bg-green-500/5 border-green-500/30"
                              : "bg-amber-500/5 border-amber-500/30"
                          )}>
                            <div className="min-w-0 flex-1 space-y-0.5">
                              <FormLabel className="text-xs uppercase tracking-wider flex items-center gap-2">
                                {field.value
                                  ? <Zap className="h-3.5 w-3.5 text-green-400 shrink-0" />
                                  : <ZapOff className="h-3.5 w-3.5 text-amber-400 shrink-0" />
                                }
                                Auto Execution
                              </FormLabel>
                              <FormDescription className="text-xs leading-relaxed">
                                {field.value
                                  ? "Bot auto-trades on KF + OBI + SMC signals"
                                  : "Signals only — no automatic order placement"
                                }
                              </FormDescription>
                            </div>
                            <FormControl>
                              <Switch className="shrink-0" checked={field.value} onCheckedChange={field.onChange} />
                            </FormControl>
                          </div>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <FormField
                        control={form.control}
                        name="slPips"
                        render={({ field }) => (
                          <FormItem className="min-w-0">
                            <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Stop Loss (Pips)</FormLabel>
                            <FormControl>
                              <Input type="number" {...field} className="font-mono border-border bg-background" />
                            </FormControl>
                            <FormDescription className="text-xs leading-relaxed">
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
                          <FormItem className="min-w-0">
                            <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Take Profit (Pips)</FormLabel>
                            <FormControl>
                              <Input type="number" {...field} className="font-mono border-border bg-background" />
                            </FormControl>
                            <FormDescription className="text-xs leading-relaxed">
                              Take Profit in pips (e.g. 70 pips for 1:2 R:R main target).
                            </FormDescription>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      <FormField
                        control={form.control}
                        name="zEntryThreshold"
                        render={({ field }) => (
                          <FormItem className="min-w-0">
                            <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Z-Score Entry Threshold</FormLabel>
                            <FormControl>
                              <Input type="number" step="0.1" {...field} className="font-mono border-border bg-background" />
                            </FormControl>
                            <FormDescription className="text-xs leading-relaxed">
                              Standard deviations threshold (e.g. 2.0). Lower triggers more frequently.
                            </FormDescription>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      <FormField
                        control={form.control}
                        name="defaultLots"
                        render={({ field }) => (
                          <FormItem className="min-w-0">
                            <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Default Lot Size (Auto-Trade)</FormLabel>
                            <FormControl>
                              <Input type="number" step="0.001" min="0" {...field} className="font-mono border-border bg-background" />
                            </FormControl>
                            <FormDescription className="text-xs leading-relaxed">
                              Fixed lot size for automatic spread trades (e.g. 0.01 minimum).
                            </FormDescription>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </div>

                    <FormField
                      control={form.control}
                      name="maxDailyTrades"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Max Daily Trades Limit</FormLabel>
                          <FormControl>
                            <Input type="number" min="1" {...field} className="font-mono border-border bg-background sm:max-w-[260px]" />
                          </FormControl>
                          <FormDescription className="text-xs leading-relaxed">
                            Maximum number of trades the bot can execute per day.
                          </FormDescription>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <div className="border-t border-border pt-4 space-y-4">
                      <FormField
                        control={form.control}
                        name="smcEnabled"
                        render={({ field }) => (
                          <FormItem>
                            <div className="flex items-center justify-between gap-4">
                              <div className="min-w-0 flex-1 space-y-0.5">
                                <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">SMC / FVG Confluence</FormLabel>
                                <FormDescription className="text-xs leading-relaxed">
                                  Require FVG/OB zone before entry. Disable if trades aren't firing.
                                </FormDescription>
                              </div>
                              <FormControl>
                                <Switch className="shrink-0" checked={field.value} onCheckedChange={field.onChange} />
                              </FormControl>
                            </div>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      {/* M1 LTF Execution Refinement Toggle */}
                      <FormField
                        control={form.control}
                        name="m1LtfEnabled"
                        render={({ field }) => (
                          <FormItem className="rounded-lg border border-cyan-500/30 bg-cyan-950/15 p-3">
                            <div className="flex items-center justify-between gap-4">
                              <div className="min-w-0 flex-1 space-y-1">
                                <FormLabel className="text-xs uppercase tracking-wider text-cyan-300 font-bold flex items-center gap-2">
                                  <span>M1 LTF Execution Refinement (US30 / NAS100)</span>
                                  <Badge
                                    variant="outline"
                                    className={cn(
                                      "text-[10px] px-1.5 py-0 font-mono",
                                      field.value
                                        ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
                                        : "bg-zinc-800 text-zinc-400 border-zinc-700"
                                    )}
                                  >
                                    {field.value ? "ON (6-Cond M1)" : "OFF (7-Cond M5)"}
                                  </Badge>
                                </FormLabel>
                                <FormDescription className="text-xs leading-relaxed">
                                  {field.value
                                    ? "ON (Recommended): US30 & NAS100 execute 6-Condition M15 Bias -> M5 Sweep -> M1 LTF entries (min 38pt SL). Gold & Forex stay on M5."
                                    : "OFF (Strict M5 Only): ALL instruments (including US30 & NAS100) execute strictly 7-Condition M5 SMC entries (no M1 live entries)."}
                                </FormDescription>
                              </div>
                              <FormControl>
                                <Switch
                                  className="shrink-0"
                                  disabled={m1Saving}
                                  checked={Boolean(field.value)}
                                  onCheckedChange={handleM1ToggleImmediate}
                                />
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
                            <div className="flex items-center justify-between gap-4">
                              <div className="min-w-0 flex-1 space-y-0.5">
                                <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Enforce Daily Drawdown Limit</FormLabel>
                                <FormDescription className="text-xs leading-relaxed">
                                  Halt trading if daily drawdown reaches configured threshold. (Auto-bypassed on Demo accounts).
                                </FormDescription>
                              </div>
                              <FormControl>
                                <Switch className="shrink-0" checked={field.value} onCheckedChange={field.onChange} />
                              </FormControl>
                            </div>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </div>

                    {/* DYNAMIC DRAWDOWN LIMIT INPUT CONTROLS IN PERCENT & USD */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 p-3 sm:p-4 rounded-lg bg-muted/20 border border-border/60">
                      <FormField
                        control={form.control}
                        name="haltDrawdownLimit"
                        render={({ field }) => {
                          const haltVal = Number(field.value || 0.78);
                          const haltUsd = (9795.54 * (haltVal / 100.0)).toFixed(2);
                          return (
                            <FormItem className="min-w-0">
                              <FormLabel className="text-xs uppercase tracking-wider text-amber-500 font-bold">⚠️ Halt Drawdown Limit (%)</FormLabel>
                              <div className="flex items-center gap-2">
                                <FormControl>
                                  <Input type="number" step="0.01" min="0.10" max="10.0" {...field} className="font-bold text-sm bg-background/80" />
                                </FormControl>
                                <span className="text-sm font-bold text-amber-500 shrink-0">%</span>
                              </div>
                              <FormDescription className="text-xs text-emerald-400 font-semibold mt-1 leading-relaxed">
                                💰 Equivalent Loss: <strong>${haltUsd} USD</strong> (based on $9,795.54 Equity)
                              </FormDescription>
                              <FormMessage />
                            </FormItem>
                          );
                        }}
                      />

                      <FormField
                        control={form.control}
                        name="maxDrawdownLimit"
                        render={({ field }) => {
                          const maxVal = Number(field.value || 3.30);
                          const maxUsd = (9795.54 * (maxVal / 100.0)).toFixed(2);
                          return (
                            <FormItem className="min-w-0">
                              <FormLabel className="text-xs uppercase tracking-wider text-red-500 font-bold">🚨 Max Drawdown Limit (%)</FormLabel>
                              <div className="flex items-center gap-2">
                                <FormControl>
                                  <Input type="number" step="0.01" min="0.50" max="20.0" {...field} className="font-bold text-sm bg-background/80" />
                                </FormControl>
                                <span className="text-sm font-bold text-red-500 shrink-0">%</span>
                              </div>
                              <FormDescription className="text-xs text-red-400 font-semibold mt-1 leading-relaxed">
                                💰 Equivalent Loss Cap: <strong>${maxUsd} USD</strong> (based on $9,795.54 Equity)
                              </FormDescription>
                              <FormMessage />
                            </FormItem>
                          );
                        }}
                      />
                    </div>

                    <div className="border-t border-border pt-4 space-y-4">
                      <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Quantitative Safety Filters</h4>

                      {/* Z-Velocity / Knife Protection Toggle */}
                      <FormField
                        control={form.control}
                        name="knifeProtectionEnabled"
                        render={({ field }) => (
                          <FormItem>
                            <div className="flex items-center justify-between gap-4">
                              <div className="min-w-0 flex-1 space-y-0.5">
                                <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Z-Velocity / Knife Protection Filter</FormLabel>
                                <FormDescription className="text-xs leading-relaxed">
                                  Defer entry if spread is moving too fast (falling/rising knife protection).
                                </FormDescription>
                              </div>
                              <FormControl>
                                <Switch className="shrink-0" checked={field.value} onCheckedChange={field.onChange} />
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
                          <div className="flex items-center justify-between gap-4">
                            <div className="min-w-0 flex-1 space-y-0.5">
                              <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Order Book Imbalance (OBI) Filter</FormLabel>
                              <FormDescription className="text-xs leading-relaxed">
                                Require order book bid/ask volume imbalance confluence before entry.
                              </FormDescription>
                            </div>
                            <FormControl>
                              <Switch className="shrink-0" checked={field.value} onCheckedChange={field.onChange} />
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
                          <div className="flex items-center justify-between gap-4">
                            <div className="min-w-0 flex-1 space-y-0.5">
                              <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Dynamic Volatility Filter</FormLabel>
                              <FormDescription className="text-xs leading-relaxed">
                                Scale entry Z-threshold dynamically during high market volatility.
                              </FormDescription>
                            </div>
                            <FormControl>
                              <Switch className="shrink-0" checked={field.value} onCheckedChange={field.onChange} />
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
                          <div className="flex items-center justify-between gap-4">
                            <div className="min-w-0 flex-1 space-y-0.5">
                              <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Forex Pairs</FormLabel>
                              <FormDescription className="text-xs leading-relaxed">
                                Enable trading standard Forex pairs.
                              </FormDescription>
                            </div>
                            <FormControl>
                              <Switch className="shrink-0" checked={field.value} onCheckedChange={field.onChange} />
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
                          <div className="flex items-center justify-between gap-4">
                            <div className="min-w-0 flex-1 space-y-0.5">
                              <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Metals (Gold/Silver)</FormLabel>
                              <FormDescription className="text-xs leading-relaxed">
                                Enable trading Spot Gold and Silver.
                              </FormDescription>
                            </div>
                            <FormControl>
                              <Switch className="shrink-0" checked={field.value} onCheckedChange={field.onChange} />
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
                          <div className="flex items-center justify-between gap-4">
                            <div className="min-w-0 flex-1 space-y-0.5">
                              <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Indices (US30 / NAS100)</FormLabel>
                              <FormDescription className="text-xs leading-relaxed">
                                Enable trading top US index CFDs (US30 & NAS100).
                              </FormDescription>
                            </div>
                            <FormControl>
                              <Switch className="shrink-0" checked={field.value} onCheckedChange={field.onChange} />
                            </FormControl>
                          </div>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    {/* Stock CFDs Trading Toggle */}
                    <FormField
                      control={form.control}
                      name="stocksEnabled"
                      render={({ field }) => (
                        <FormItem>
                          <div className="flex items-center justify-between gap-4">
                            <div className="min-w-0 flex-1 space-y-0.5">
                              <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Stock CFDs / Equities (AAPL / NVDA / MSFT)</FormLabel>
                              <FormDescription className="text-xs leading-relaxed">
                                Enable trading individual stock equities (e.g. AAPL, NVDA, MSFT).
                              </FormDescription>
                            </div>
                            <FormControl>
                              <Switch className="shrink-0" checked={field.value} onCheckedChange={field.onChange} />
                            </FormControl>
                          </div>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>

                  <div className="pt-3 border-t border-border grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs text-muted-foreground">
                    <div className="p-2 rounded bg-muted/20 border border-border/50">
                      <div className="text-[10px] uppercase">Z-Score Entry</div>
                      <div className="font-mono text-foreground font-semibold mt-0.5">±{Number(form.watch("zEntryThreshold") ?? 2.0).toFixed(2)}σ</div>
                    </div>
                    <div className="p-2 rounded bg-muted/20 border border-border/50">
                      <div className="text-[10px] uppercase">Max Daily Trades</div>
                      <div className="font-mono text-foreground font-semibold mt-0.5">{form.watch("maxDailyTrades") ?? 3}</div>
                    </div>
                    <div className="p-2 rounded bg-muted/20 border border-border/50">
                      <div className="text-[10px] uppercase">Risk Per Trade</div>
                      <div className="font-mono text-foreground font-semibold mt-0.5">1% equity</div>
                    </div>
                    <div className="p-2 rounded bg-muted/20 border border-border/50">
                      <div className="text-[10px] uppercase">Execution</div>
                      <div className="font-mono text-foreground font-semibold mt-0.5">3-Part TP</div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Button
                type="submit"
                disabled={updateConfig.isPending}
                className="w-full min-h-10 py-2.5 font-mono text-xs font-bold tracking-wider bg-primary text-primary-foreground hover:bg-primary/90"
              >
                {updateConfig.isPending ? "SAVING..." : "SAVE CONFIGURATION"}
              </Button>
            </div>
          </div>

          {/* BLUE GUARDIAN RULES */}
          <Card className="bg-card border-border">
            <CardHeader className="p-4 sm:p-6 pb-3">
              <div className="flex flex-wrap items-center gap-2">
                <CardTitle className="text-sm uppercase tracking-wider text-muted-foreground">Blue Guardian Rules Compliance</CardTitle>
                <Badge className="bg-green-500/15 text-green-500 border-green-500/30 text-xs rounded-sm shrink-0">SAFE</Badge>
              </div>
              <CardDescription className="text-xs leading-relaxed">
                Bot configured to stay within Blue Guardian limits. 0.83% daily halt = intentional buffer below the 3.3% hard limit.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-4 sm:p-6 pt-0">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
                {BLUE_GUARDIAN_RULES.map((r) => (
                  <div key={r.rule} className="flex flex-col gap-1.5 p-3 rounded-sm border border-border bg-muted/20 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-xs text-muted-foreground leading-snug">{r.rule}</span>
                      <Badge
                        variant="outline"
                        className={cn(
                          "text-[10px] rounded-sm px-1.5 font-bold font-mono uppercase shrink-0 whitespace-nowrap",
                          r.safe
                            ? "bg-green-500/10 text-green-400 border-green-500/20"
                            : "bg-red-500/10 text-red-400 border-red-500/20"
                        )}
                      >
                        {r.safe ? "✓ COMPLIANT" : "✗ BANNED"}
                      </Badge>
                    </div>
                    <div className="text-xs font-mono font-medium text-foreground break-words">{r.value}</div>
                    <div className="text-[11px] text-muted-foreground leading-snug break-words">{r.botValue}</div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </fieldset>

          {/* PASSWORD CHANGE SECTION */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6">
            <Card className="bg-card border-border">
              <CardHeader className="p-4 sm:p-6 pb-3">
                <CardTitle className="text-sm uppercase tracking-wider text-muted-foreground">Admin Security Settings</CardTitle>
                <CardDescription className="text-xs leading-relaxed">
                  Update the master administrator credentials for the trading system.
                </CardDescription>
              </CardHeader>
              <CardContent className="p-4 sm:p-6 pt-0">
                <div className="space-y-4">
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
                    className="w-full sm:w-auto bg-indigo-600 hover:bg-indigo-500 text-white font-mono text-xs px-4 min-h-9 font-bold"
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

            {/* USER PASSWORD CHANGE SECTION (ADMIN ONLY) */}
            {!isReadOnly && (
              <Card className="bg-card border-border">
                <CardHeader className="p-4 sm:p-6 pb-3">
                  <CardTitle className="text-sm uppercase tracking-wider text-muted-foreground">User Security Settings</CardTitle>
                  <CardDescription className="text-xs leading-relaxed">
                    Update the login password for the read-only User account.
                  </CardDescription>
                </CardHeader>
                <CardContent className="p-4 sm:p-6 pt-0">
                  <div className="space-y-4">
                    <div className="space-y-1">
                      <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono block">New User Password</label>
                      <Input
                        type="password"
                        placeholder="••••••••"
                        value={userNewPass}
                        onChange={(e) => setUserNewPass(e.target.value)}
                        className="font-mono text-xs border-border bg-zinc-950/40 text-foreground"
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono block">Confirm New User Password</label>
                      <Input
                        type="password"
                        placeholder="••••••••"
                        value={userConfirmPass}
                        onChange={(e) => setUserConfirmPass(e.target.value)}
                        className="font-mono text-xs border-border bg-zinc-950/40 text-foreground"
                      />
                    </div>
                    <Button
                      type="button"
                      onClick={handleChangeUserPassword}
                      disabled={!userNewPass || !userConfirmPass}
                      className="w-full sm:w-auto bg-emerald-600 hover:bg-emerald-500 text-white font-mono text-xs px-4 min-h-9 font-bold"
                    >
                      CHANGE USER PASSWORD
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </form>
      </Form>
    </div>
  );
}
