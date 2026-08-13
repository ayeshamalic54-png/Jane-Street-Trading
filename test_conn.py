import MetaTrader5 as mt5
import os
import sys

# Load env credentials
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
login_val = None
password_val = None
server_val = None

if os.path.exists(env_path):
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("=", 1)
            if len(parts) == 2:
                key = parts[0].strip()
                val = parts[1].strip()
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                if key == "MT5_LOGIN": login_val = int(val) if val else None
                if key == "MT5_PASSWORD": password_val = val if val else None
                if key == "MT5_SERVER": server_val = val if val else None

terminal_path = "C:\\Program Files\\MetaTrader 5\\terminal64.exe"

print("=========================================")
print("     MT5 DIAGNOSTIC CONNECTION TEST      ")
print("=========================================\n")

# TEST 1: Connection without path (Auto-detect from registry)
print("TEST 1: Connecting WITHOUT path (Auto-detect)...")
mt5.shutdown()
if login_val and password_val and server_val:
    success = mt5.initialize(login=login_val, password=password_val, server=server_val, timeout=30000)
else:
    success = mt5.initialize(timeout=30000)

if success:
    print("SUCCESS: Test 1 connected via auto-detection.")
    acc = mt5.account_info()
    print(f"Account: {acc.login} | Server: {acc.server}\n")
    mt5.shutdown()
else:
    print(f"FAIL: Test 1 failed. Error: {mt5.last_error()}\n")

# TEST 2: Connection with explicit path
print("TEST 2: Connecting WITH path...")
mt5.shutdown()
if login_val and password_val and server_val:
    success = mt5.initialize(path=terminal_path, login=login_val, password=password_val, server=server_val, timeout=30000)
else:
    success = mt5.initialize(path=terminal_path, timeout=30000)

if success:
    print("SUCCESS: Test 2 connected with explicit path.")
    acc = mt5.account_info()
    print(f"Account: {acc.login} | Server: {acc.server}\n")
    mt5.shutdown()
else:
    print(f"FAIL: Test 2 failed. Error: {mt5.last_error()}\n")
