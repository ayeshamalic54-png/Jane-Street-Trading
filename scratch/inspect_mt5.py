import sys
import os
import MetaTrader5 as mt5

if not mt5.initialize():
    print("MT5 initialize failed")
    sys.exit(1)

acc = mt5.account_info()
if acc:
    print(f"Account Balance: {acc.balance}")
    print(f"Account Equity: {acc.equity}")
    print(f"Account Profit: {acc.profit}")
else:
    print("Failed to get account info")

positions = mt5.positions_get()
print(f"Active positions count: {len(positions) if positions else 0}")
if positions:
    for p in positions:
        print(f"Ticket: {p.ticket} | Symbol: {p.symbol} | Profit: {p.profit} | Type: {p.type}")

mt5.shutdown()
