import sys
import os
import time
import datetime

sys.path.insert(0, os.path.abspath('.'))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from news_guard import send_discord_news_alert, check_pair_news_block

print("================================================================================")
print("🧪 LIVE SIMULATION TEST: HIGH-IMPACT NEWS GUARD & DISCORD ALERT 🧪")
print("================================================================================")

# 1. Test Direct Discord Webhook Alert Delivery for High Impact USD/Gold News
print("\n[TEST 1] Triggering Simulated High-Impact USD/Gold News Alert to Discord...")
try:
    send_discord_news_alert(country="USD", event_title="FOMC Interest Rate Decision & Policy Statement", mins=10, stage="Stage 1")
    print("✅ Discord Webhook trigger executed successfully (Check Discord Channel!)")
except Exception as e:
    print(f"❌ Error sending Discord alert: {e}")

# 2. Test News Guard Block Logic for Gold (XAUUSD)
print("\n[TEST 2] Verifying Trade Block Logic for Gold (XAUUSD)...")

# Create a mock high-impact event scheduled in 5 minutes
utc_now = datetime.datetime.now(datetime.timezone.utc)
mock_event_time = (utc_now + datetime.timedelta(minutes=5)).isoformat()

mock_events = [
    {
        "title": "FOMC Rate Cut Statement",
        "country": "USD",
        "date": mock_event_time,
        "impact": "high"
    }
]

# Inject mock event data into cache for testing
import json
with open("news_cache.json", "w") as f:
    json.dump({"timestamp": time.time(), "data": mock_events}, f)

is_blocked, reason, country, event = check_pair_news_block(["XAUUSD"], pre_minutes=15.0, post_minutes=30.0)

print(f"-> Mock High Impact USD News Blocked Status: {is_blocked}")
print(f"-> Block Reason: '{reason}'")
print(f"-> Affected Currency: '{country}'")
print(f"-> Event Title: '{event}'")

assert is_blocked == True, "CRITICAL FAIL: High-Impact USD news did NOT block XAUUSD trade!"
print("\n✅ PASS: High-Impact USD News for Gold (XAUUSD) SUCCESSFULLY BLOCKED TRADE EXECUTION!")
print("================================================================================")
