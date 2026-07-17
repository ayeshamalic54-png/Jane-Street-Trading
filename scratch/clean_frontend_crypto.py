import os

dashboard_dir = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "trading-dashboard", "src", "pages")

config_path = os.path.join(dashboard_dir, "config.tsx")
dashboard_path = os.path.join(dashboard_dir, "dashboard.tsx")
markets_path = os.path.join(dashboard_dir, "markets.tsx")

# 1. Clean config.tsx
if os.path.exists(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Remove crypto pairs
    target_pairs = """  crypto: {
    label: "Crypto",
    pairs: [
      "BTCUSD/ETHUSD", "ETHUSD/BTCUSD", "BTCUSD/SOLUSD", "ETHUSD/SOLUSD",
      "BTCUSD/XRPUSD", "BTCUSD/BNBUSD", "ETHUSD/ADAUSD", "SOLUSD/AVAXUSD",
      "BTCUSD/DOGEUSD", "ETHUSD/MATICUSD",
    ],
  },"""
    if target_pairs in content:
        content = content.replace(target_pairs, "")
        print("config.tsx: Removed crypto pairs configuration.")
        
    # Remove crypto FormField switch
    target_switch = """                    {/* Crypto Trading Toggle */}
                    <FormField
                      control={form.control}
                      name="cryptoEnabled"
                      render={({ field }) => (
                        <FormItem>
                          <div className="flex items-center justify-between">
                            <div>
                              <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Cryptocurrencies</FormLabel>
                              <FormDescription className="text-xs mt-0.5">
                                Enable trading Bitcoin, Ethereum, etc.
                              </FormDescription>
                            </div>
                            <FormControl>
                              <Switch checked={field.value} onCheckedChange={field.onChange} />
                            </FormControl>
                          </div>
                          <FormMessage />
                        </FormItem>
                      )}
                    />"""
    
    # Try alternate indentation just in case
    target_switch_alt = """                    <FormField
                      control={form.control}
                      name="cryptoEnabled"
                      render={({ field }) => (
                        <FormItem>
                          <div className="flex items-center justify-between">
                            <div>
                              <FormLabel className="text-xs uppercase tracking-wider text-muted-foreground">Cryptocurrencies</FormLabel>
                              <FormDescription className="text-xs mt-0.5">
                                Enable trading Bitcoin, Ethereum, etc.
                              </FormDescription>
                            </div>
                            <FormControl>
                              <Switch checked={field.value} onCheckedChange={field.onChange} />
                            </FormControl>
                          </div>
                          <FormMessage />
                        </FormItem>
                      )}
                    />"""
                    
    if target_switch in content:
        content = content.replace(target_switch, "")
        print("config.tsx: Removed crypto switch FormField.")
    elif target_switch_alt in content:
        content = content.replace(target_switch_alt, "")
        print("config.tsx: Removed crypto switch FormField (alt).")
        
    # Also clean the category selection description text
    content = content.replace("Forex / Crypto / Metals / Stocks / Custom", "Forex / Metals / Stocks / Custom")

    with open(config_path, "w", encoding="utf-8") as f:
        f.write(content)

# 2. Clean dashboard.tsx
if os.path.exists(dashboard_path):
    with open(dashboard_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Remove Crypto badge
    target_badge = '<span className={cn("px-1.5 py-0.5 rounded-sm text-[10px] font-bold border transition-all duration-300", dashboard.cryptoEnabled ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30 shadow-[0_0_10px_rgba(16,185,129,0.15)]" : "text-zinc-600 border-zinc-800 bg-zinc-900/20 opacity-50")}>Crypto</span>'
    if target_badge in content:
        content = content.replace(target_badge, "")
        print("dashboard.tsx: Removed crypto status badge.")
        
    # Clean description tooltip
    content = content.replace("Forex, Crypto, Metals, and Stocks/Indices", "Forex, Metals, and Stocks/Indices")

    with open(dashboard_path, "w", encoding="utf-8") as f:
        f.write(content)

# 3. Clean markets.tsx
if os.path.exists(markets_path):
    with open(markets_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Clean type Category
    content = content.replace('type Category = "all" | "forex" | "crypto" | "metals" | "stocks";', 'type Category = "all" | "forex" | "metals" | "stocks";')
    # Clean CATEGORY_LABELS
    content = content.replace('  crypto: "Crypto",\n', "")
    # Clean categoryOrder
    content = content.replace('"crypto", ', "")
    # Clean footer text
    content = content.replace("Crypto: Binance live · Forex: Frankfurter · Metals: Binance · Stocks: MT5 CFD", "Forex: Frankfurter · Metals: MT5 · Stocks: MT5 CFD")

    with open(markets_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("markets.tsx: Cleaned crypto references.")
