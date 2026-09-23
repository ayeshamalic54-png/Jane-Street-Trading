import os
import requests
import datetime
from dotenv import load_dotenv

load_dotenv(r"G:\google antigravity\jane_street_trading_system\.env")
webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

print(f"Loaded Discord Webhook URL: {webhook_url}")

if not webhook_url:
    print("ERROR: DISCORD_WEBHOOK_URL not found!")
    exit(1)

now_str = datetime.datetime.now().strftime("%A, %d/%m/%Y, %I:%M:%S %p")

# 1. TEST OPEN POSITION NOTIFICATION
open_msg = (
    f"📢 **PURE SMC / ICT 9-CONDITION SIGNAL ENGINE** 📢\n"
    f"🚀 **[ NEW OPEN POSITION ]** 🚀\n\n"
    f"🟢 **ACTION:** `MARKET BUY 🟢` (XAUUSD)\n"
    f"⏱ **TIME:** `{now_str}`\n"
    f"📊 **STRATEGY:** `Pure SMC / ICT 9-Condition Structure 🟢`\n\n"
    f"📥 **ENTRY PRICE:** `4340.11`\n"
    f"⛔ **STOP LOSS (SL):** `4328.50` *(116.1 Pips | Sweep + 0.75 Buffer)*\n"
    f"🎯 **TAKE PROFIT (TP):** `4363.33` *(2.0R Target / M15 Structural Target)*\n"
    f"📦 **LOT SIZE:** `0.18 Lots` *(0.5% Account Risk / $48.84 USD)*\n"
)

res1 = requests.post(webhook_url, json={"content": open_msg}, timeout=5)
print(f"1. Open Notification Result: {res1.status_code}")

# 2. TEST CLOSED POSITION NOTIFICATION
close_msg = (
    f"🏁 **PURE SMC / ICT TRADE CLOSED** 🏁\n\n"
    f"🟢 **SYMBOL:** `XAUUSD` (BUY 0.18 Lots)\n"
    f"⏱ **TIME:** `{now_str}`\n"
    f"💵 **REALIZED P&L:** `+$97.68 USD` 🟢 *(+1.00% Account Gain)*\n"
    f"🎯 **EXIT REASON:** `2.0R Take Profit Hit @ 4363.33` 🟢\n"
)

res2 = requests.post(webhook_url, json={"content": close_msg}, timeout=5)
print(f"2. Closed Notification Result: {res2.status_code}")

# 3. TEST DISCARD NOTIFICATION
discard_msg = (
    f"⚠️ **PURE SMC / ICT SIGNAL DISCARDED** ⚠️\n\n"
    f"📊 **SYMBOL:** `XAUUSD` (M5 Bullish Setup)\n"
    f"⏱ **TIME:** `{now_str}`\n"
    f"🔴 **REASON:** `Condition 9 FAIL: Available M15 Target RRR (1.35R) < 2.0R Minimum Requirement`\n"
    f"🛡️ **ACTION:** Trade Execution Blocked (`NO TRADE`). Account Capital Protected 🛡️\n"
)

res3 = requests.post(webhook_url, json={"content": discard_msg}, timeout=5)
print(f"3. Discard Notification Result: {res3.status_code}")

print("\nSUCCESS: All 3 Test Notifications Sent to Discord Webhook!")
