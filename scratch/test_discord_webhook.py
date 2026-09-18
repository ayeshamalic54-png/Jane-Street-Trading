import os
import requests

webhook_url = "https://discord.com/api/webhooks/1546796694249668679/btdDhZ-LvyzKm-eUZ-6fKKtdUfKajC8BSUg1L5goqkx5F-k1cYCwB-UDVgZ2zGletRCJ"

payload = {
    "content": "🟢 **[ WASEE SOFT TRADING SYSTEM ]**\n⚡ Discord Webhook Connection Test Successful!\n🛡️ Security Status: 100% Protected (Env Variable Only)"
}

try:
    res = requests.post(webhook_url, json=payload, timeout=5)
    if res.status_code in (200, 204):
        print("SUCCESS: Discord Webhook message delivered cleanly!")
    else:
        print(f"FAILED: HTTP {res.status_code} - {res.text}")
except Exception as e:
    print(f"ERROR: {e}")
