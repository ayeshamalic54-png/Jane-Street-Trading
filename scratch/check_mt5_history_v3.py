import MetaTrader5 as mt5
import datetime
import os

def check_mt5():
    # Manual .env parser
    login = None
    password = None
    server = None
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    parts = line.strip().split("=", 1)
                    if parts[0].strip() == "MT5_LOGIN":
                        login = parts[1].strip()
                    elif parts[0].strip() == "MT5_PASSWORD":
                        password = parts[1].strip()
                    elif parts[0].strip() == "MT5_SERVER":
                        server = parts[1].strip()

    terminal_path = "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
    
    if login and password and server:
        print(f"Connecting using credentials from .env -> Account: {login}, Server: {server}...")
        login_int = int(login)
        if not mt5.initialize(path=terminal_path, login=login_int, password=password, server=server, timeout=60000):
            print(f"Failed to initialize and login to MT5: {mt5.last_error()}")
            return
    else:
        print("No credentials found in .env, connecting to default active account...")
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
        return

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
            print(f"  Deal: {d.ticket} | Time: {datetime.datetime.fromtimestamp(d.time)} | Symbol: {d.symbol} | Type: {d.type} (0=Buy, 1=Sell) | Entry/Exit: {d.entry} (0=In, 1=Out) | Lots: {d.volume} | Price: {d.price} | Profit: {d.profit} | Comment: {d.comment}")

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
