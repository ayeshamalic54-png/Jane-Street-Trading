import sys
import os
import datetime
import pandas as pd
import numpy as np

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, r"G:\google antigravity\jane_street_trading_system")

from smc_strategy_engine import evaluate_smc_strategy_signal

print("=" * 85)
print("🚀 INSTITUTIONAL 6-MONTH (180 DAYS) HISTORICAL BACKTEST — XAUUSD (GOLD)")
print("=========================================================================")

import MetaTrader5 as mt5

if not mt5.initialize():
    print(f"❌ MT5 terminal connection error: {mt5.last_error()}")
    sys.exit(1)

symbol = "XAUUSD"
info = mt5.symbol_info(symbol)
if info is None:
    syms = mt5.symbols_get()
    if syms:
        for s in syms:
            if 'XAU' in s.name.upper() or 'GOLD' in s.name.upper():
                symbol = s.name
                break

# 6 Months (180 Days) Date Range
utc_to = datetime.datetime.now(datetime.timezone.utc)
utc_from = utc_to - datetime.timedelta(days=180)

print(f"📅 Backtest Window: {utc_from.strftime('%Y-%m-%d')} to {utc_to.strftime('%Y-%m-%d')} (6 MONTHS)")
print(f"📊 Symbol: {symbol} | Strategy: Pure SMC 7-Step Strict Engine")
print(f"🛡️ Stop Loss Buffer: $1.75 (Gold) | Take Profit: Pure 1:1.8 RRR Target")
print("-" * 85)

print("Fetching historical M15 and M5 candles from MT5...")
rates_m15 = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M15, utc_from, utc_to)
rates_m5 = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M5, utc_from, utc_to)
mt5.shutdown()

if rates_m15 is None or len(rates_m15) == 0 or rates_m5 is None or len(rates_m5) == 0:
    print("❌ Failed to fetch historical MT5 data for 6-month period.")
    sys.exit(1)

df_m15 = pd.DataFrame(rates_m15)
df_m5 = pd.DataFrame(rates_m5)
df_m15['time_dt'] = pd.to_datetime(df_m15['time'], unit='s')
df_m5['time_dt'] = pd.to_datetime(df_m5['time'], unit='s')

print(f"✅ Loaded M15 Candles: {len(df_m15)} bars")
print(f"✅ Loaded M5 Candles:  {len(df_m5)} bars")
print("-" * 85)

# Replay simulation through historical M5 candles
trades = []
win_count = 0
loss_count = 0
starting_capital = 5000.0
current_capital = starting_capital
peak_capital = starting_capital
max_drawdown_pct = 0.0

monthly_stats = {}

# Step every 3 M5 bars (every 15 mins)
step_size = 3
window_m5 = 35
window_m15 = 40

# Map M5 time to M15 index range efficiently
m15_times = df_m15['time'].values

for i in range(window_m5, len(df_m5) - 40, step_size):
    m5_sub = df_m5.iloc[i-window_m5:i].copy().reset_index(drop=True)
    curr_m5_time = df_m5.iloc[i-1]['time']
    
    # Slice M15 up to current M5 timestamp
    m15_sub = df_m15[df_m15['time'] <= curr_m5_time].tail(window_m15).copy().reset_index(drop=True)
    
    if len(m15_sub) < 15 or len(m5_sub) < 10:
        continue
        
    sig, tp, sl, dist, msg = evaluate_smc_strategy_signal(df_m15=m15_sub, df_m5=m5_sub, category="metals")
    
    if sig in ["BUY", "SELL"]:
        entry_price = float(m5_sub.iloc[-1]['close'])
        entry_time = m5_sub.iloc[-1]['time_dt']
        month_key = entry_time.strftime('%Y-%m')
        
        # Forward simulate outcome over next 40 M5 candles (3 hours max hold)
        future_bars = df_m5.iloc[i:i+40]
        outcome = "OPEN"
        exit_price = entry_price
        pnl = 0.0
        
        for _, f_row in future_bars.iterrows():
            f_high = float(f_row['high'])
            f_low = float(f_row['low'])
            
            if sig == "BUY":
                if f_low <= sl:
                    outcome = "LOSS (SL HIT)"
                    exit_price = sl
                    pnl = -50.0  # Fixed $50 USD Risk (1.0%)
                    break
                elif f_high >= tp:
                    outcome = "WIN (TP HIT)"
                    exit_price = tp
                    pnl = +90.0  # Pure 1:1.8 RRR = +$90 USD
                    break
            elif sig == "SELL":
                if f_high >= sl:
                    outcome = "LOSS (SL HIT)"
                    exit_price = sl
                    pnl = -50.0
                    break
                elif f_low <= tp:
                    outcome = "WIN (TP HIT)"
                    exit_price = tp
                    pnl = +90.0
                    break
                    
        if outcome in ["WIN (TP HIT)", "LOSS (SL HIT)"]:
            if outcome == "WIN (TP HIT)":
                win_count += 1
            else:
                loss_count += 1
                
            current_capital += pnl
            if current_capital > peak_capital:
                peak_capital = current_capital
            dd = (peak_capital - current_capital) / peak_capital * 100.0
            if dd > max_drawdown_pct:
                max_drawdown_pct = dd
                
            if month_key not in monthly_stats:
                monthly_stats[month_key] = {'wins': 0, 'losses': 0, 'pnl': 0.0}
            monthly_stats[month_key]['pnl'] += pnl
            if outcome == "WIN (TP HIT)":
                monthly_stats[month_key]['wins'] += 1
            else:
                monthly_stats[month_key]['losses'] += 1
                
            trades.append({
                'time': entry_time,
                'type': sig,
                'entry': entry_price,
                'sl': sl,
                'tp': tp,
                'outcome': outcome,
                'pnl': pnl,
                'capital': current_capital
            })

total_trades = win_count + loss_count
win_rate = (win_count / total_trades * 100.0) if total_trades > 0 else 0.0
gross_profit = win_count * 90.0
gross_loss = loss_count * 50.0
profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 99.0
net_pnl = current_capital - starting_capital

print("=" * 85)
print("📈 6-MONTH (180 DAYS) PURE SMC BACKTEST PERFORMANCE REPORT")
print("=========================================================================")
print(f"📅 Evaluation Period:          {utc_from.strftime('%Y-%m-%d')} to {utc_to.strftime('%Y-%m-%d')} (6 Months)")
print(f"💱 Instrument Evaluated:       XAUUSD (Gold)")
print(f"🎫 Total Signals Executed:     {total_trades}")
print(f"✅ Winning Trades (TP Hit):     {win_count}")
print(f"❌ Losing Trades (SL Hit):      {loss_count}")
print(f"📊 Win Rate (Accuracy):        {win_rate:.1f}%")
print(f"💰 Starting Capital:           ${starting_capital:.2f} USD")
print(f"💵 Final Capital:              ${current_capital:.2f} USD")
print(f"💵 Net Realized Profit:         ${net_pnl:+.2f} USD ({net_pnl/starting_capital*100:+.1f}%)")
print(f"📉 Maximum Drawdown:            {max_drawdown_pct:.2f}%")
print(f"⚖️ Profit Factor:               {profit_factor:.2f}")
print("=" * 85)

print("\n📅 MONTH-BY-MONTH PERFORMANCE BREAKDOWN:")
print("-" * 65)
print(f"{'Month':<10} | {'Wins':<6} | {'Losses':<6} | {'Win Rate':<10} | {'Net PnL ($)':<12}")
print("-" * 65)
for m_key, m_val in sorted(monthly_stats.items()):
    m_tot = m_val['wins'] + m_val['losses']
    m_wr = (m_val['wins'] / m_tot * 100.0) if m_tot > 0 else 0.0
    print(f"{m_key:<10} | {m_val['wins']:<6} | {m_val['losses']:<6} | {m_wr:>8.1f}% | ${m_val['pnl']:>+10.2f}")
print("-" * 65)

if trades:
    df_trades = pd.DataFrame(trades)
    output_path = r"G:\google antigravity\jane_street_trading_system\scratch\smc_6month_backtest_trades.csv"
    df_trades.to_csv(output_path, index=False)
    print(f"\n📁 Full trade-by-trade log saved to: [smc_6month_backtest_trades.csv](file:///{output_path})")
print("=" * 85)
