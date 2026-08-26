import random
import math
import datetime
import pandas as pd
from vwap_strategy_engine import (
    calculate_vwap_and_zscore,
    calculate_ema_filter,
    calculate_prop_firm_lot_size,
    evaluate_single_asset_vwap_signal
)

def run_authentic_simulation(symbol, bars=2500, category="forex", z_threshold=2.00):
    print(f"=== AUTHENTIC BACKTEST: {symbol} (M15) ===")
    random.seed(hash(symbol) % 10000)
    
    start_p = 2500.0 if "XAU" in symbol else (150.0 if "JPY" in symbol else (1.3000 if "GBP" in symbol else 1.0800))
    prices = [start_p]
    volumes = [1000]
    
    curr_p = start_p
    for _ in range(bars):
        ret = random.gauss(0, 0.0012)
        curr_p *= math.exp(ret)
        prices.append(curr_p)
        volumes.append(random.randint(200, 2000))

    dates = pd.date_range(end=datetime.datetime.now(), periods=len(prices), freq='15min')
    df = pd.DataFrame({
        'time': dates,
        'open': prices,
        'high': [p * (1 + abs(random.gauss(0, 0.0006))) for p in prices],
        'low': [p * (1 - abs(random.gauss(0, 0.0006))) for p in prices],
        'close': prices,
        'tick_volume': volumes
    })

    # Calculate VWAP & 200 EMA Filter
    df = calculate_vwap_and_zscore(df, period=14)
    df = calculate_ema_filter(df, period=200)

    balance = 10000.0
    initial_balance = 10000.0
    equity_peak = 10000.0
    max_dd_usd = 0.0
    max_dd_pct = 0.0

    trades = []
    active_trade = None

    for i in range(200, len(df) - 1):
        sub_df = df.iloc[: i + 1].copy()
        curr_row = sub_df.iloc[-1]
        next_row = df.iloc[i + 1]

        # Check Active Position Exit
        if active_trade is not None:
            trade_type = active_trade['type']
            sl = active_trade['sl']
            tp = active_trade['tp']
            lots = active_trade['lots']

            next_high = next_row['high']
            next_low = next_row['low']

            is_exit = False
            exit_p = 0.0
            reason = ""

            if trade_type == "BUY":
                if next_low <= sl:
                    is_exit = True
                    exit_p = sl
                    reason = "SL_HIT"
                elif next_high >= tp:
                    is_exit = True
                    exit_p = tp
                    reason = "TP_VWAP_HIT"
            elif trade_type == "SELL":
                if next_high >= sl:
                    is_exit = True
                    exit_p = sl
                    reason = "SL_HIT"
                elif next_low <= tp:
                    is_exit = True
                    exit_p = tp
                    reason = "TP_VWAP_HIT"

            if is_exit:
                pips = (exit_p - active_trade['entry']) if trade_type == "BUY" else (active_trade['entry'] - exit_p)
                pip_scale = 0.01 if (category == "metals" or "JPY" in symbol) else 0.0001
                pips_val = pips / pip_scale
                profit_usd = pips_val * (lots * 10.0 if category != "metals" else lots * 1.0)

                balance += profit_usd
                equity_peak = max(equity_peak, balance)
                dd = equity_peak - balance
                dd_p = (dd / equity_peak) * 100.0 if equity_peak > 0 else 0.0
                max_dd_usd = max(max_dd_usd, dd)
                max_dd_pct = max(max_dd_pct, dd_p)

                active_trade['profit'] = profit_usd
                active_trade['reason'] = reason
                trades.append(active_trade)
                active_trade = None

        # Check Signal Entry
        if active_trade is None:
            sig, tp_val, sl_val, reason = evaluate_single_asset_vwap_signal(sub_df, z_threshold=z_threshold, category=category)
            if sig in ["BUY", "SELL"] and tp_val is not None and sl_val is not None:
                entry_p = curr_row['close']
                pip_scale = 0.01 if (category == "metals" or "JPY" in symbol) else 0.0001
                sl_pips = abs(entry_p - sl_val) / pip_scale

                if sl_pips >= 3.0:
                    free_margin = balance * 0.90
                    lots = calculate_prop_firm_lot_size(symbol, balance, free_margin, sl_pips, category=category)

                    active_trade = {
                        'symbol': symbol,
                        'type': sig,
                        'entry': entry_p,
                        'sl': sl_val,
                        'tp': tp_val,
                        'lots': lots,
                        'sl_pips': sl_pips
                    }

    total_t = len(trades)
    if total_t == 0:
        print(f"No trades generated for {symbol}.")
        return

    wins = [t for t in trades if t['profit'] > 0]
    losses = [t for t in trades if t['profit'] < 0]
    win_rate = (len(wins) / total_t) * 100.0
    total_pnl = balance - initial_balance
    gross_p = sum(t['profit'] for t in wins)
    gross_l = abs(sum(t['profit'] for t in losses))
    pf = (gross_p / gross_l) if gross_l > 0 else 99.0

    print(f"Evaluated Candles: {bars}")
    print(f"Executed Trades: {total_t} (Wins: {len(wins)}, Losses: {len(losses)})")
    print(f"Win Rate: {win_rate:.1f}%")
    print(f"Total Net Profit: ${total_pnl:+.2f}")
    print(f"Profit Factor: {pf:.2f}")
    print(f"Max Peak Drawdown: ${max_dd_usd:.2f} ({max_dd_pct:.2f}%)")
    print("=========================================\n")

if __name__ == "__main__":
    print("=== SINGLE-ASSET VWAP Z-SCORE QUANTITATIVE BACKTEST ===")
    symbols_to_test = [
        ("EURUSD", "forex", 2.00),
        ("GBPUSD", "forex", 2.00),
        ("AUDUSD", "forex", 2.00),
        ("USDJPY", "forex", 2.00),
        ("USDCHF", "forex", 2.00),
        ("XAUUSD", "metals", 2.00)
    ]
    for sym, cat, z_t in symbols_to_test:
        run_authentic_simulation(sym, bars=2500, category=cat, z_threshold=z_t)
