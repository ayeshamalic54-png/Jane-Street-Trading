import os
import datetime
import numpy as np
import pandas as pd
import MetaTrader5 as mt5

# Create scratch output CSV path
artifacts_dir = r"C:\Users\wasee\.gemini\antigravity\brain\ff929b26-3e48-498d-af80-632118e67f78\scratch"
os.makedirs(artifacts_dir, exist_ok=True)
csv_output_path = os.path.join(artifacts_dir, "backtest_trade_by_trade_results.csv")

print("=========================================================================")
print("🚀 STARTING HISTORICAL TICK/M1 REPLAY BACKTEST ENGINE (JANE STREET)")
print("=========================================================================")

if not mt5.initialize():
    print(f"❌ MT5 Initialization failed: {mt5.last_error()}")
    exit(1)

# Pairs to backtest
test_pairs = [
    ("EURUSD", "USDCHF"),
    ("GBPUSD", "USDJPY"),
    ("AUDUSD", "NZDUSD")
]

# Backtest range: Last 14 days of M1 data
utc_to = datetime.datetime.now(datetime.timezone.utc)
utc_from = utc_to - datetime.timedelta(days=14)

print(f"📅 Backtest Period: {utc_from.strftime('%Y-%m-%d')} to {utc_to.strftime('%Y-%m-%d')}")
print(f"📊 Testing Pair Baskets: {test_pairs}")

# Data fetching helper
def fetch_pair_data(sym_a, sym_b):
    rates_a = mt5.copy_rates_range(sym_a, mt5.TIMEFRAME_M1, utc_from, utc_to)
    rates_b = mt5.copy_rates_range(sym_b, mt5.TIMEFRAME_M1, utc_from, utc_to)
    
    if rates_a is None or rates_b is None or len(rates_a) == 0 or len(rates_b) == 0:
        print(f"⚠️ Warning: Could not fetch rates for {sym_a}/{sym_b}")
        return None
        
    df_a = pd.DataFrame(rates_a)
    df_b = pd.DataFrame(rates_b)
    
    df_a['time_dt'] = pd.to_datetime(df_a['time'], unit='s')
    df_b['time_dt'] = pd.to_datetime(df_b['time'], unit='s')
    
    merged = pd.merge(df_a[['time_dt', 'close', 'high', 'low']], 
                      df_b[['time_dt', 'close', 'high', 'low']], 
                      on='time_dt', suffixes=('_a', '_b'))
    merged.sort_values('time_dt', inplace=True)
    merged.reset_index(drop=True, inplace=True)
    return merged

def run_simulation(logic_mode="CURRENT_OPTION_1"):
    """
    logic_mode: 
      - "CURRENT_OPTION_1": Partial exit @ Z<=0.50 + Breakeven SL + Stepped Trailing SL
      - "ORIGINAL_BASELINE": Full Sweep Exit @ Z<=0.0 (All 4 legs close together)
    """
    all_trades = []
    active_trades = [] # Capped at max 2 concurrent pairs
    
    total_net_pnl = 0.0
    equity_curve = [9800.0]
    current_equity = 9800.0
    peak_equity = 9800.0
    max_drawdown = 0.0
    
    counts = {
        "total_sets": 0,
        "wins": 0,
        "losses": 0,
        "partial_exit_050_triggered": 0,
        "ou_half_life_triggered": 0,
        "sl_triggered": 0,
        "trailing_stop_triggered": 0,
        "adverse_exit_triggered": 0,
        "positive_turned_negative": 0
    }
    
    for sym_a, sym_b in test_pairs:
        df = fetch_pair_data(sym_a, sym_b)
        if df is None or len(df) < 100:
            continue
            
        prices_a = df['close_a'].values
        prices_b = df['close_b'].values
        times = df['time_dt'].values
        
        # Calculate Rolling Beta, Spread, Mean, Std, Z-Score
        window = 60
        beta = 0.85
        spreads = prices_a - beta * prices_b
        
        rolling_mean = pd.Series(spreads).rolling(window=window).mean().values
        rolling_std = pd.Series(spreads).rolling(window=window).std().values
        
        z_scores = np.zeros(len(spreads))
        for i in range(window, len(spreads)):
            if rolling_std[i] > 1e-6:
                z_scores[i] = (spreads[i] - rolling_mean[i]) / rolling_std[i]
                
        # Velocity
        z_velocity = np.zeros(len(z_scores))
        for i in range(1, len(z_scores)):
            z_velocity[i] = z_scores[i] - z_scores[i-1]
            
        pip_unit_a = 0.0001
        pip_unit_b = 0.0001
        
        # State tracking per active trade set
        in_trade = False
        trade_data = None
        
        for i in range(window + 5, len(df)):
            curr_time = pd.to_datetime(times[i])
            z_val = z_scores[i]
            z_vel = z_velocity[i]
            pa = prices_a[i]
            pb = prices_b[i]
            
            # --- 1. CHECK ENTRY ---
            if not in_trade:
                if len(active_trades) < 2: # Max 2 concurrent trade limit
                    # Check Z-Score Entry Threshold (|Z| >= 2.0) + Momentum confirmation
                    is_sell_entry = (z_val >= 2.0) and (z_vel < 0.0) # Spread turning down
                    is_buy_entry = (z_val <= -2.0) and (z_vel > 0.0)  # Spread turning up
                    
                    if is_sell_entry or is_buy_entry:
                        in_trade = True
                        entry_z = z_val
                        entry_pa = pa
                        entry_pb = pb
                        entry_time = curr_time
                        trade_type = "SELL" if is_sell_entry else "BUY"
                        
                        # 3 Main Parts (0.40 lots each = 1.20 lots total) + 1 Hedge (0.34 lots)
                        trade_data = {
                            "pair": f"{sym_a}/{sym_b}",
                            "trade_type": trade_type,
                            "entry_time": entry_time,
                            "entry_z": entry_z,
                            "entry_pa": pa,
                            "entry_pb": pb,
                            "tp1_active": True,
                            "tp2_active": True,
                            "tp3_active": True,
                            "hedge_active": True,
                            "tp1_pnl": 0.0,
                            "tp2_pnl": 0.0,
                            "tp3_pnl": 0.0,
                            "hedge_pnl": 0.0,
                            "tp2_sl": pa + 0.0012 if trade_type == "SELL" else pa - 0.0012, # SL 12 pips
                            "tp3_sl": pa + 0.0012 if trade_type == "SELL" else pa - 0.0012,
                            "peak_floating_pnl": 0.0,
                            "z_at_peak": z_val,
                            "did_hit_050": False,
                            "tp1_banked": False,
                            "breakeven_set": False,
                            "holding_seconds": 0,
                            "exit_reason": "",
                            "final_pnl": 0.0
                        }
                        active_trades.append(trade_data)
                        counts["total_sets"] += 1
                        
            # --- 2. MANAGE OPEN TRADE ---
            else:
                trade = trade_data
                holding_sec = (curr_time - trade["entry_time"]).total_seconds()
                trade["holding_seconds"] = holding_sec
                
                # Calculate PnL for active parts
                if trade["trade_type"] == "SELL":
                    pips_main = (trade["entry_pa"] - pa) / pip_unit_a
                    pips_hedge = (trade["entry_pb"] - pb) / pip_unit_b
                else:
                    pips_main = (pa - trade["entry_pa"]) / pip_unit_a
                    pips_hedge = (pb - trade["entry_pb"]) / pip_unit_b
                    
                cur_tp1_pnl = (pips_main * 4.0) if trade["tp1_active"] else trade["tp1_pnl"]
                cur_tp2_pnl = (pips_main * 4.0) if trade["tp2_active"] else trade["tp2_pnl"]
                cur_tp3_pnl = (pips_main * 4.0) if trade["tp3_active"] else trade["tp3_pnl"]
                cur_hedge_pnl = (pips_hedge * 3.4) if trade["hedge_active"] else trade["hedge_pnl"]
                
                total_floating_pnl = cur_tp1_pnl + cur_tp2_pnl + cur_tp3_pnl + cur_hedge_pnl
                
                if total_floating_pnl > trade["peak_floating_pnl"]:
                    trade["peak_floating_pnl"] = total_floating_pnl
                    trade["z_at_peak"] = z_val
                    
                # Track if Z <= 0.50 hit
                if trade["trade_type"] == "SELL" and z_val <= 0.50:
                    trade["did_hit_050"] = True
                elif trade["trade_type"] == "BUY" and z_val >= -0.50:
                    trade["did_hit_050"] = True
                    
                # ── LOGIC MODE 1: CURRENT OPTION 1 (Z<=0.50 Partial Exit + Breakeven + Trailing SL) ──
                if logic_mode == "CURRENT_OPTION_1":
                    # Step A: Check 0.50 Partial Exit
                    if trade["did_hit_050"] and not trade["tp1_banked"] and holding_sec >= 140.0:
                        trade["tp1_active"] = False
                        trade["tp1_pnl"] = cur_tp1_pnl
                        trade["tp1_banked"] = True
                        trade["breakeven_set"] = True
                        # Shift TP2 & TP3 SL to Breakeven
                        trade["tp2_sl"] = trade["entry_pa"]
                        trade["tp3_sl"] = trade["entry_pa"]
                        counts["partial_exit_050_triggered"] += 1
                        
                    # Step B: Check Stepped Milestone Trailing SL for TP2 & TP3
                    if trade["tp1_banked"]:
                        if pips_main >= 12.0:
                            # Milestone 2: +12 pips -> Locks +8 pips SL
                            lock_price = trade["entry_pa"] - 0.0008 if trade["trade_type"] == "SELL" else trade["entry_pa"] + 0.0008
                            trade["tp2_sl"] = lock_price
                            trade["tp3_sl"] = lock_price
                            counts["trailing_stop_triggered"] += 1
                        elif pips_main >= 8.0:
                            # Milestone 1: +8 pips -> Locks +4 pips SL
                            lock_price = trade["entry_pa"] - 0.0004 if trade["trade_type"] == "SELL" else trade["entry_pa"] + 0.0004
                            trade["tp2_sl"] = lock_price
                            trade["tp3_sl"] = lock_price
                            counts["trailing_stop_triggered"] += 1

                    # Step C: Exit Triggers (Z=0.0 Full Mean Exit, SL, OU Half-life)
                    is_mean_00 = (trade["trade_type"] == "SELL" and z_val <= 0.0) or (trade["trade_type"] == "BUY" and z_val >= 0.0)
                    is_sl_hit = (trade["trade_type"] == "SELL" and pa >= trade["tp2_sl"]) or (trade["trade_type"] == "BUY" and pa <= trade["tp2_sl"])
                    is_ou_expired = holding_sec >= (45.0 * 300.0 * 2.5) # 337.5 M5 bars
                    
                    if (is_mean_00 or is_sl_hit or is_ou_expired) and holding_sec >= 140.0:
                        in_trade = False
                        if is_mean_00:
                            trade["exit_reason"] = "Z_MEAN_REVERSION (0.0)"
                        elif is_sl_hit:
                            trade["exit_reason"] = "TRAILING_OR_BREAKEVEN_SL"
                        elif is_ou_expired:
                            trade["exit_reason"] = "OU_HALF_LIFE_EXPIRATION"
                            counts["ou_half_life_triggered"] += 1
                            
                        trade["tp2_pnl"] = cur_tp2_pnl
                        trade["tp3_pnl"] = cur_tp3_pnl
                        trade["hedge_pnl"] = cur_hedge_pnl
                        
                        trade["final_pnl"] = (trade["tp1_pnl"] if trade["tp1_banked"] else cur_tp1_pnl) + cur_tp2_pnl + cur_tp3_pnl + cur_hedge_pnl
                        
                        if trade["peak_floating_pnl"] > 10.0 and trade["final_pnl"] < 0:
                            counts["positive_turned_negative"] += 1
                            
                        if trade["final_pnl"] >= 0:
                            counts["wins"] += 1
                        else:
                            counts["losses"] += 1
                            
                        all_trades.append(trade)
                        if trade in active_trades:
                            active_trades.remove(trade)
                            
                # ── LOGIC MODE 2: ORIGINAL BASELINE (Z<=0.0 Full Sweep Exit at Mean) ──
                else:
                    is_mean_00 = (trade["trade_type"] == "SELL" and z_val <= 0.0) or (trade["trade_type"] == "BUY" and z_val >= 0.0)
                    is_z_sl = (trade["trade_type"] == "SELL" and z_val >= 3.8) or (trade["trade_type"] == "BUY" and z_val <= -3.8)
                    is_ou_expired = holding_sec >= (45.0 * 300.0 * 2.5)
                    
                    if (is_mean_00 or is_z_sl or is_ou_expired) and holding_sec >= 140.0:
                        in_trade = False
                        if is_mean_00:
                            trade["exit_reason"] = "Z_TP_REVERSION (0.0)"
                        elif is_z_sl:
                            trade["exit_reason"] = "Z_STOP_LOSS (3.8)"
                            counts["sl_triggered"] += 1
                        elif is_ou_expired:
                            trade["exit_reason"] = "OU_HALF_LIFE_EXPIRATION"
                            counts["ou_half_life_triggered"] += 1
                            
                        trade["final_pnl"] = cur_tp1_pnl + cur_tp2_pnl + cur_tp3_pnl + cur_hedge_pnl
                        
                        if trade["peak_floating_pnl"] > 10.0 and trade["final_pnl"] < 0:
                            counts["positive_turned_negative"] += 1
                            
                        if trade["final_pnl"] >= 0:
                            counts["wins"] += 1
                        else:
                            counts["losses"] += 1
                            
                        all_trades.append(trade)
                        if trade in active_trades:
                            active_trades.remove(trade)

    return all_trades, counts

# Run both simulations
trades_curr, counts_curr = run_simulation("CURRENT_OPTION_1")
trades_base, counts_base = run_simulation("ORIGINAL_BASELINE")

# Export trade-by-trade CSV
df_results = pd.DataFrame(trades_curr)
if len(df_results) > 0:
    df_results.to_csv(csv_output_path, index=False)
    print(f"✅ Trade-by-Trade Backtest Results saved to: {csv_output_path}")

print("\n=========================================================================")
print("📊 COMPREHENSIVE BACKTEST REPORT & COMPARISON TABLE")
print("=========================================================================")

def calc_stats(trades_list, counts_dict):
    total = len(trades_list)
    if total == 0:
        return {}
    wins = [t['final_pnl'] for t in trades_list if t['final_pnl'] >= 0]
    losses = [t['final_pnl'] for t in trades_list if t['final_pnl'] < 0]
    
    net_pnl = sum([t['final_pnl'] for t in trades_list])
    win_rate = (len(wins) / total) * 100.0 if total > 0 else 0.0
    avg_win = np.mean(wins) if len(wins) > 0 else 0.0
    avg_loss = np.mean(losses) if len(losses) > 0 else 0.0
    
    total_win_val = sum(wins)
    total_loss_val = abs(sum(losses))
    profit_factor = (total_win_val / total_loss_val) if total_loss_val > 0 else 99.0
    
    return {
        "total_sets": total,
        "win_rate": win_rate,
        "net_pnl": net_pnl,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "pos_turned_neg": counts_dict["positive_turned_negative"],
        "partial_050_cnt": counts_dict["partial_exit_050_triggered"],
        "ou_expired_cnt": counts_dict["ou_half_life_triggered"]
    }

s_curr = calc_stats(trades_curr, counts_curr)
s_base = calc_stats(trades_base, counts_base)

print(f"\n{'METRIC':<35} | {'CURRENT LOGIC (Z<=0.50)':<25} | {'ORIGINAL BASELINE (Z<=0.0)':<25}")
print("-" * 90)
print(f"{'Total Trade Baskets Executed':<35} | {s_curr.get('total_sets', 0):<25} | {s_base.get('total_sets', 0):<25}")
print(f"{'Win Rate (%)':<35} | {s_curr.get('win_rate', 0.0):<24.1f}% | {s_base.get('win_rate', 0.0):<24.1f}%")
print(f"{'Total Net PnL ($)':<35} | +${s_curr.get('net_pnl', 0.0):<24.2f} | +${s_base.get('net_pnl', 0.0):<24.2f}")
print(f"{'Average Win ($)':<35} | +${s_curr.get('avg_win', 0.0):<24.2f} | +${s_base.get('avg_win', 0.0):<24.2f}")
print(f"{'Average Loss ($)':<35} | -${abs(s_curr.get('avg_loss', 0.0)):<24.2f} | -${abs(s_base.get('avg_loss', 0.0)):<24.2f}")
print(f"{'Profit Factor':<35} | {s_curr.get('profit_factor', 0.0):<25.2f} | {s_base.get('profit_factor', 0.0):<25.2f}")
print(f"{'Positive Trades Turned Loss':<35} | {s_curr.get('pos_turned_neg', 0):<25} | {s_base.get('pos_turned_neg', 0):<25}")
print(f"{'Z <= 0.50 Partial Exits Triggered':<35} | {s_curr.get('partial_050_cnt', 0):<25} | N/A (Full Sweep Only)")
print(f"{'OU Half-Life Expirations':<35} | {s_curr.get('ou_expired_cnt', 0):<25} | {s_base.get('ou_expired_cnt', 0):<25}")
print("=========================================================================\n")
