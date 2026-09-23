import os
import subprocess
import MetaTrader5 as mt5

possible_paths = [
    r"C:\Program Files\MetaTrader 5\terminal64.exe",
    r"C:\Program Files (x86)\MetaTrader 5\terminal64.exe",
    r"C:\Program Files\Exness MetaTrader 5\terminal64.exe",
    r"C:\Program Files\XM MetaTrader 5\terminal64.exe",
    r"C:\Program Files\FTMO MetaTrader 5\terminal64.exe",
]

found = []
for p in possible_paths:
    if os.path.exists(p):
        found.append(p)
        print("Found MT5 Terminal:", p)

if not found:
    print("Searching Program Files for terminal64.exe...")
    import glob
    matches = glob.glob(r"C:\Program Files*\**\terminal64.exe", recursive=True)
    for m in matches:
        print("Found MT5:", m)
        found.append(m)

if found:
    print(f"Attempting to initialize MT5 with path: {found[0]}")
    res = mt5.initialize(path=found[0])
    print("MT5 Init Result:", res)
    if not res:
        print("Error detail:", mt5.last_error())
    else:
        print("Connected to MT5 successfully!")
        mt5.shutdown()
else:
    print("No MT5 terminal executable found in standard locations.")
