import os
import requests
import datetime

url = "https://discord.com/api/webhooks/1546796694249668679/btdDhZ-LvyzKm-eUZ-6fKKtdUfKajC8BSUg1L5goqkx5F-k1cYCwB-UDVgZ2zGletRCJ"

now_str = datetime.datetime.now().strftime("%A, %d/%m/%Y, %I:%M:%S %p")
message = (
    f"📢 **PURE SMC / ICT 7-STEP SIGNAL ENGINE** 📢\n"
    f"🚀 **[ LIVE DISCORD NOTIFICATION TEST ]** 🚀\n\n"
    f"🔴 **ACTION:** `MARKET SELL 🔴` (XAUUSD)\n"
    f"⏱ **TIME:** `{now_str}`\n"
    f"📊 **STRATEGY:** `Pure SMC / ICT 7-Step Structure 🟢`\n\n"
    f"📥 **ENTRY PRICE:** `4271.34`\n"
    f"⛔ **STOP LOSS (SL):** `4278.56` *(Local Swing High + $0.75 Buffer | -$50.54 Risk Cap)*\n"
    f"🎯 **TAKE PROFIT (TP):** `4258.34` *(1:1.8 RRR Target | +$91.00 Profit Target)*\n"
    f"📦 **LOT SIZE:** `0.07 Lots` (MT5 Gold Standard)\n\n"
    f"🟢 **STATUS:** Live Webhook Connection Active & Operational! 🚀"
)

payload = {"content": message}

try:
    res = requests.post(url, json=payload, timeout=10)
    print(f"Status Code: {res.status_code}")
    if res.status_code in (200, 204):
        print("NOTIFICATION_SENT_SUCCESSFULLY")
    else:
        print(f"Response text: {res.text}")
except Exception as e:
    print(f"Error: {e}")
