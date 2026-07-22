import os
import time
import datetime
import urllib.request
import json
import logging

logger = logging.getLogger("SMC_Forex_Bot")

CACHE_FILE = "news_cache.json"
CACHE_EXPIRY_SECONDS = 300 # 5 minutes cache

def get_news_halt_status(symbols):
    """
    Checks for high impact economic news for the currencies in symbols (USD, EUR, GBP, BTC, etc.).
    Halts trading if high-impact news is within 30 minutes (before or after).
    Works 100% automatically via ForexFactory live JSON feed with 5-min caching.
    """
    currencies = set()
    for sym in symbols:
        sym_clean = sym.replace("/", "").replace("USDT", "USD").upper()
        if len(sym_clean) == 6:
            currencies.add(sym_clean[:3])
            currencies.add(sym_clean[3:])
        else:
            currencies.add(sym_clean[-3:])
            currencies.add(sym_clean[:-3])

    events = []
    cached_data = None
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                cached_data = json.load(f)
        except Exception:
            pass

    # Use cache if fresh (< 5 mins)
    if cached_data and (time.time() - cached_data.get("timestamp", 0) < CACHE_EXPIRY_SECONDS):
        events = cached_data.get("data", [])
    else:
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=10) as response:
                events = json.loads(response.read().decode('utf-8'))
                with open(CACHE_FILE, "w") as f:
                    json.dump({
                        "timestamp": time.time(),
                        "data": events
                    }, f)
        except Exception as e:
            if cached_data:
                events = cached_data.get("data", [])
            else:
                return False, "No high-impact news within 30 minutes"

    utc_now = datetime.datetime.now(datetime.timezone.utc)
    
    for event in events:
        impact = str(event.get("impact", "")).lower()
        country = str(event.get("country", "")).upper()
        event_title = event.get("title", "News")
        date_str = event.get("date", "")
        
        if impact == "high" and (country in currencies or (country == "USD" and "USD" in currencies)):
            try:
                event_time = datetime.datetime.fromisoformat(date_str).astimezone(datetime.timezone.utc)
                diff_minutes = (event_time - utc_now).total_seconds() / 60.0
                
                # If event is within next 30 minutes
                if 0 <= diff_minutes <= 30.0:
                    return True, f"High impact {country} news ({event_title}) in {int(diff_minutes)}m"
                
                # If event was in the last 30 minutes
                if -30.0 <= diff_minutes < 0:
                    return True, f"High impact {country} news ({event_title}) released {int(abs(diff_minutes))}m ago"
            except Exception:
                pass

    return False, "No high-impact news within 30 minutes"
