import sys
import os
sys.path.insert(0, os.path.abspath('.'))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from news_guard import check_pair_news_block, get_news_halt_status

print("================================================================================")
print("📰 AUTHENTIC FOREXFACTORY HIGH-IMPACT NEWS GUARD VERIFICATION 📰")
print("================================================================================")

is_blocked, reason, country, event = check_pair_news_block(["XAUUSD", "XAGUSD"], pre_minutes=15.0, post_minutes=30.0)

print(f"Gold (XAUUSD) High Impact News Block Status: {is_blocked}")
if is_blocked:
    print(f"Reason: {reason} | Country: {country} | Event: {event}")
else:
    print("Status: 🟢 No High-Impact USD/Gold News currently active within 15m pre / 30m post window.")

print("================================================================================")
