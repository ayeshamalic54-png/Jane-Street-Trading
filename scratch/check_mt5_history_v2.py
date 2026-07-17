import MetaTrader5 as mt5
import datetime

def check_mt5():
    if not mt5.initialize():
        print(f"Failed to initialize MT5: {mt5.last_error()}")
        return

    acc_info = mt5.account_info()
    if acc_info:
        print("MT5 Account Info:")
        print(f"  Login: {acc_info.login}")
        print(f"  Server: {acc_info.server}")
        print(f"  Balance: {acc_info.balance}")
        print(f"  Equity: {acc_info.equity}")
        print(f"  Profit: {acc_info.profit}")
    else:
        print("Failed to get MT5 account info")

    now = datetime.datetime.now()
    from_date = now - datetime.timedelta(days=7)
    
    deals = mt5.history_deals_get(from_date, now)
    print("\nMT5 Deal History (Last 7 Days):")
    if deals is None:
        print(f"  Failed to get history deals: {mt5.last_error()}")
    elif len(deals) == 0:
        print("  No deals found in history.")
    else:
        # Sort deals by time descending
        sorted_deals = sorted(deals, key=lambda x: x.time, reverse=True)
        for d in sorted_deals[:100]:
            print(f"  Deal: {d.ticket} | Time: {datetime.datetime.fromtimestamp(d.time)} | Symbol: {d.symbol} | Type: {d.type} | Entry/Exit: {d.entry} | Lots: {d.volume} | Price: {d.price} | Profit: {d.profit} | Comment: {d.comment}")

    # Check active positions
    positions = mt5.positions_get()
    print("\nActive Positions:")
    if positions is None:
        print(f"  Failed to get positions: {mt5.last_error()}")
    elif len(positions) == 0:
        print("  No active positions.")
    else:
        for p in positions:
            print(f"  Position: {p.ticket} | Symbol: {p.symbol} | Type: {p.type} | Lots: {p.volume} | PriceOpen: {p.price_open} | PriceCurrent: {p.price_current} | Profit: {p.profit} | Swap: {p.swap} | Comment: {p.comment}")

    mt5.shutdown()

if __name__ == "__main__":
    check_mt5()
