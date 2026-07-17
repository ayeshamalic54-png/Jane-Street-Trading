import os
import sys
import MetaTrader5 as mt5

if not mt5.initialize():
    print(f"MT5 initialize failed: {mt5.last_error()}")
    sys.exit(1)

# Get current prices
tick_aud = mt5.symbol_info_tick("AUDUSD")
tick_nzd = mt5.symbol_info_tick("NZDUSD")

print("=== CURRENT FOREX TICKERS ===")
if tick_aud:
    print(f"AUDUSD | Bid: {tick_aud.bid} | Ask: {tick_aud.ask}")
else:
    print("AUDUSD ticker not found.")

if tick_nzd:
    print(f"NZDUSD | Bid: {tick_nzd.bid} | Ask: {tick_nzd.ask}")
else:
    print("NZDUSD ticker not found.")

# Get MT5 active positions
positions = mt5.positions_get()
print("=== MT5 ACTIVE POSITIONS ===")
if positions:
    for p in positions:
        print(f"Ticket: {p.ticket} | Symbol: {p.symbol} | Type: {p.type} | Lots: {p.volume} | PriceOpen: {p.price_open} | PriceCurrent: {p.price_current} | Profit: {p.profit} | Comment: {p.comment}")
else:
    print("No active positions on MT5.")

# Get account details
acc = mt5.account_info()
if acc:
    print(f"=== ACCOUNT INFO ===\nBalance: {acc.balance} | Equity: {acc.equity} | Profit: {acc.profit}")
else:
    print("Failed to fetch account info.")

mt5.shutdown()
