import MetaTrader5 as mt5

if not mt5.initialize():
    print("Failed to initialize MT5")
    exit()

tickets = [9555782966, 9555787869, 9555792101, 9555796139]
for t in tickets:
    deals = mt5.history_deals_get(position=t)
    print(f"Position ID: {t} | Deals count: {len(deals) if deals else 0}")
    if deals:
        for d in deals:
            print(f"  Deal: {d.ticket} | Sym: {d.symbol} | Profit: {d.profit} | Type: {d.type} | Entry: {d.entry}")

mt5.shutdown()
