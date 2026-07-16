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
    Checks for high impact economic news for the currencies in symbols.
    Halts trading if high-impact news is within 30 minutes (before or after).
    """
    api_key = os.getenv("FINNHUB_API_KEY")
    if not api_key:
        return False, "News Guard: Disabled (No API Key)"

    # Get currencies of interest from active symbols
    currencies = set()
    for sym in symbols:
        # e.g., GBPUSD -> GBP, USD
        sym_clean = sym.replace("/", "").upper()
        if len(sym_clean) == 6:
            currencies.add(sym_clean[:3])
            currencies.add(sym_clean[3:])
        else:
            # Fallback or spot metals/indices e.g. XAUUSD -> XAU, USD
            currencies.add(sym_clean[-3:])
            currencies.add(sym_clean[:-3])

    events = []
    
    # Check cache first
    cached_data = None
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                cached_data = json.load(f)
        except Exception:
            pass

    if cached_data and (time.time() - cached_data.get("timestamp", 0) < CACHE_EXPIRY_SECONDS):
        events = cached_data.get("data", {}).get("economicCalendar", [])
    else:
        # Fetch from Finnhub API
        url = f"https://finnhub.io/api/v1/calendar/economic?token={api_key}"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                events = res_data.get("economicCalendar", [])
                
                # Write cache
                with open(CACHE_FILE, "w") as f:
                    json.dump({
                        "timestamp": time.time(),
                        "data": res_data
                    }, f)
        except Exception as e:
            logger.error(f"Error fetching economic calendar: {e}")
            # Fallback to expired cache if available
            if cached_data:
                events = cached_data.get("data", {}).get("economicCalendar", [])
            else:
                return False, f"News Guard: API Error, Bypassed ({e})"

    utc_now = datetime.datetime.now(datetime.timezone.utc)
    
    for event in events:
        impact = str(event.get("impact", "")).lower()
        currency = str(event.get("currency", "")).upper()
        event_time_str = event.get("time", "")
        
        if impact == "high" and currency in currencies:
            try:
                # Event time is UTC, e.g. "2026-07-16 13:00:00"
                # Parse format "YYYY-MM-DD HH:MM:SS" or similar
                # Strip timezone if present or handle UTC
                event_time_clean = event_time_str.split("+")[0].strip()
                event_time = datetime.datetime.strptime(event_time_clean, "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc)
                
                diff_minutes = (event_time - utc_now).total_seconds() / 60.0
                
                # If event is in the next 30 minutes
                if 0 <= diff_minutes <= 30.0:
                    return True, f"High impact {currency} news ({event.get('event')}) in {int(diff_minutes)} minutes"
                
                # If event was in the last 30 minutes
                if -30.0 <= diff_minutes < 0:
                    return True, f"High impact {currency} news ({event.get('event')}) released {int(abs(diff_minutes))} minutes ago"
            except Exception as ex:
                logger.warning(f"Error parsing news event time '{event_time_str}': {ex}")

    return False, "No high-impact news within 30 minutes"
