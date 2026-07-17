import os
import sys
import MetaTrader5 as mt5

# Initialize MT5
if not mt5.initialize():
    print("MT5 initialization failed")
    sys.exit(1)

# Print account info
acc = mt5.account_info()
if acc:
    print(f"Logged into Account: {acc.login} | Server: {acc.server} | Company: {acc.company}")
else:
    print("Failed to get account info")

# Get all symbols
all_syms = mt5.symbols_get()
print(f"Total symbols found: {len(all_syms) if all_syms else 0}")

# Search for symbols containing key substrings
search_keys = ["100", "SPX", "US500", "US30", "DJI", "NASDAQ", "NDX", "AAPL", "MSFT", "APPLE", "MICROSOFT"]
found = {}
if all_syms:
    for s in all_syms:
        s_name_upper = s.name.upper()
        for key in search_keys:
            if key in s_name_upper:
                found.setdefault(key, []).append(s.name)

print("\n=== MATCHED SYMBOLS ===")
for key, names in found.items():
    print(f"{key}: {names[:15]} (Total: {len(names)})")

mt5.shutdown()
