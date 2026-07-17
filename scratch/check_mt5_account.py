import MetaTrader5 as mt5

if not mt5.initialize():
    print("Failed to initialize MT5")
    exit()

acc = mt5.account_info()
if acc:
    print(f"Login: {acc.login}")
    print(f"Server: {acc.server}")
    print(f"Company: {acc.company}")
    print(f"Balance: {acc.balance}")
else:
    print("No account info found.")

mt5.shutdown()
