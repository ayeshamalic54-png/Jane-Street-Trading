import os
import time
import datetime
import urllib.request
import json
import logging

logger = logging.getLogger("SMC_Forex_Bot")

CACHE_FILE = "news_cache.json"
CACHE_EXPIRY_SECONDS = 300 # 5 minutes cache

import requests
import threading

_DISCORD_NEWS_NOTIFIED = {}

def send_discord_news_alert(country, event_title, mins, stage="Stage 1"):
    """Sends a rich Discord Webhook alert for High-Impact News events with 15m throttling."""
    global _DISCORD_NEWS_NOTIFIED
    now = time.time()
    event_key = f"{country}_{event_title}_{stage}"

    # Throttle to send maximum ONCE per 15 minutes per event
    if event_key in _DISCORD_NEWS_NOTIFIED and (now - _DISCORD_NEWS_NOTIFIED[event_key]) < 900:
        return

    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        return

    _DISCORD_NEWS_NOTIFIED[event_key] = now

    def _async_send():
        try:
            time_desc = f"in {mins} minutes" if stage == "Stage 1" else f"{abs(mins)} minutes ago"
            payload = {
                "username": "Jane Street News Guard",
                "avatar_url": "https://cdn-icons-png.flaticon.com/512/2965/2965300.png",
                "embeds": [{
                    "title": "📰 HIGH-IMPACT NEWS GUARD ALERT",
                    "description": "**High-Impact Economic News Protection Active!**\nNew trade entries for affected currency pairs are being blocked to protect capital.",
                    "color": 15158332, # Crimson Red
                    "fields": [
                        {"name": "🌐 Currency", "value": f"**{country}**", "inline": True},
                        {"name": "🗞️ Event", "value": f"**{event_title}**", "inline": True},
                        {"name": "⏱️ Time", "value": f"**{time_desc}**", "inline": True},
                        {"name": "🛡️ Protection Layer", "value": "**Stage 1: Pre-News Entry Block**" if stage == "Stage 1" else "**Stage 2: Post-News Volatility Protection**", "inline": False}
                    ],
                    "footer": {"text": "Jane Street Quantitative System • Risk Guard Layer"},
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                }]
            }
            requests.post(webhook_url, json=payload, timeout=5)
        except Exception as ex:
            logger.error(f"Error sending Discord News alert: {ex}")

    threading.Thread(target=_async_send, daemon=True).start()

def get_news_halt_status(symbols, buffer_minutes=15.0):
    """
    Checks for high impact economic news for the currencies in symbols (USD, EUR, GBP, etc.).
    Halts trading if high-impact news is within buffer_minutes (default 15 minutes before or after).
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

    if cached_data and (time.time() - cached_data.get("timestamp", 0) < CACHE_EXPIRY_SECONDS):
        events = cached_data.get("data", [])
    else:
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=10) as response:
                events = json.loads(response.read().decode('utf-8'))
                with open(CACHE_FILE, "w") as f:
                    json.dump({"timestamp": time.time(), "data": events}, f)
        except Exception:
            if cached_data:
                events = cached_data.get("data", [])
            else:
                return False, f"No high-impact news within {int(buffer_minutes)} minutes"

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
                
                # If event is within next buffer_minutes (e.g. 15 mins)
                if 0 <= diff_minutes <= buffer_minutes:
                    return True, f"High impact {country} news ({event_title}) in {int(diff_minutes)}m"
                
                # If event was in the last buffer_minutes (e.g. 15 mins)
                if -buffer_minutes <= diff_minutes < 0:
                    return True, f"High impact {country} news ({event_title}) released {int(abs(diff_minutes))}m ago"
            except Exception:
                pass

    return False, f"No high-impact news within {int(buffer_minutes)} minutes"


def should_auto_close_before_news(symbols, lead_minutes=15.0):
    """
    Returns (True, reason) if high impact news is scheduled within `lead_minutes` (default 15 mins) before release.
    Used to block new position entries before high-impact news spikes.
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

    if cached_data and (time.time() - cached_data.get("timestamp", 0) < CACHE_EXPIRY_SECONDS):
        events = cached_data.get("data", [])
    else:
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=10) as response:
                events = json.loads(response.read().decode('utf-8'))
                with open(CACHE_FILE, "w") as f:
                    json.dump({"timestamp": time.time(), "data": events}, f)
        except Exception:
            if cached_data:
                events = cached_data.get("data", [])
            else:
                return False, ""

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
                
                if 0.0 <= diff_minutes <= lead_minutes:
                    return True, f"High impact {country} news ({event_title}) in {int(diff_minutes)}m"
            except Exception:
                pass

    return False, ""

def check_pair_news_block(symbols, pre_minutes=15.0, post_minutes=30.0):
    """
    Currency-Specific High-Impact News Enforcement Layer.
    Detects high-impact news and identifies affected currencies.
    Blocks NEW entries for pairs containing that currency from pre_minutes (15m before)
    until post_minutes (30m after release).
    Does NOT close, modify, or interfere with existing open positions.
    Returns: (is_blocked, reason, affected_currency, event_title)
    """
    currencies = set()
    for s in symbols:
        s_clean = s.replace("/", "").replace("USDT", "USD").upper()
        if len(s_clean) == 6:
            currencies.add(s_clean[:3])
            currencies.add(s_clean[3:])
        else:
            currencies.add(s_clean[-3:])
            currencies.add(s_clean[:-3])

    events = []
    cached_data = None
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                cached_data = json.load(f)
        except Exception:
            pass

    if cached_data and (time.time() - cached_data.get("timestamp", 0) < CACHE_EXPIRY_SECONDS):
        events = cached_data.get("data", [])
    else:
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=10) as response:
                events = json.loads(response.read().decode('utf-8'))
                with open(CACHE_FILE, "w") as f:
                    json.dump({"timestamp": time.time(), "data": events}, f)
        except Exception:
            if cached_data:
                events = cached_data.get("data", [])
            else:
                return False, "", "", ""

    utc_now = datetime.datetime.now(datetime.timezone.utc)

    for event in events:
        impact = str(event.get("impact", "")).lower()
        country = str(event.get("country", "")).upper()
        event_title = event.get("title", "News")
        date_str = event.get("date", "")

        if impact == "high" and country in currencies:
            try:
                event_time = datetime.datetime.fromisoformat(date_str).astimezone(datetime.timezone.utc)
                diff_minutes = (event_time - utc_now).total_seconds() / 60.0

                # Block from pre_minutes before (15m) to post_minutes after (30m)
                if -post_minutes <= diff_minutes <= pre_minutes:
                    reason = f"{country} HIGH IMPACT NEWS ({event_title})"
                    mins = max(1, int(round(diff_minutes)))
                    pair_str = "/".join(symbols) if isinstance(symbols, (list, tuple, set)) else str(symbols)
                    logger.info(f"NEWS BLOCK | Currency: {country} | Event: {event_title} | Pair: {pair_str} | Time: {mins}m | TRADE BLOCKED")
                    send_discord_news_alert(country, event_title, mins, stage="Stage 1")
                    return True, reason, country, event_title
            except Exception:
                pass

    return False, "", "", ""

def check_post_news_stability(symbols, kf_pair=None, post_window_minutes=120.0):
    """
    Stage 2: Post-News Regime Confirmation Protection.
    After the 30m hard news-block window expires (between 30m and 120m after release),
    verifies if the affected spread has stabilized and returned to a mean-reverting regime.
    If post-news directional momentum / Z-velocity is still excessively fast, entry is deferred.
    Returns: (is_unstable, reason, affected_currency, event_title)
    """
    currencies = set()
    for s in symbols:
        s_clean = s.replace("/", "").replace("USDT", "USD").upper()
        if len(s_clean) == 6:
            currencies.add(s_clean[:3])
            currencies.add(s_clean[3:])
        else:
            currencies.add(s_clean[-3:])
            currencies.add(s_clean[:-3])

    events = []
    cached_data = None
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                cached_data = json.load(f)
        except Exception:
            pass

    if cached_data and (time.time() - cached_data.get("timestamp", 0) < CACHE_EXPIRY_SECONDS):
        events = cached_data.get("data", [])

    if not events:
        return False, "", "", ""

    utc_now = datetime.datetime.now(datetime.timezone.utc)

    for event in events:
        impact = str(event.get("impact", "")).lower()
        country = str(event.get("country", "")).upper()
        event_title = event.get("title", "News")
        date_str = event.get("date", "")

        if impact == "high" and country in currencies:
            try:
                event_time = datetime.datetime.fromisoformat(date_str).astimezone(datetime.timezone.utc)
                diff_minutes = (event_time - utc_now).total_seconds() / 60.0

                # Post-news window: between 30 minutes and 120 minutes AFTER event release
                if -post_window_minutes <= diff_minutes < -30.0:
                    if kf_pair is not None:
                        z_vel = kf_pair.get_velocity(k=3)
                        z_curr = kf_pair.z_history[-1] if kf_pair.z_history else 0.0
                        
                        # Determine asset-tailored dynamic velocity threshold
                        sym_sample = str(list(symbols)[0]).upper() if symbols else ""
                        if any(m in sym_sample for m in ["XAU", "XAG", "GOLD", "SILVER"]):
                            z_vel_limit = 0.035
                        elif any(idx in sym_sample for idx in ["US30", "NAS100", "US500", "GER30"]):
                            z_vel_limit = 0.025
                        else:
                            z_vel_limit = 0.015

                        import numpy as np
                        if len(kf_pair.z_history) >= 20:
                            vel_changes = np.diff(kf_pair.z_history[-20:])
                            dynamic_std = float(np.std(vel_changes)) if len(vel_changes) > 0 else z_vel_limit
                            z_vel_limit = max(z_vel_limit, round(dynamic_std * 2.0, 4))
                        
                        # Check if spread momentum is still expanding fast in trend direction
                        is_expanding_fast = (z_curr > 2.0 and z_vel > z_vel_limit) or (z_curr < -2.0 and z_vel < -z_vel_limit)
                        
                        if is_expanding_fast:
                            reason = f"Post-news momentum shock active ({country} news {abs(int(diff_minutes))}m ago | Z={z_curr:.2f}, Z-Vel={z_vel:+.4f} > limit {z_vel_limit:.4f})"
                            send_discord_news_alert(country, event_title, int(diff_minutes), stage="Stage 2")
                            return True, reason, country, event_title
            except Exception:
                pass

    return False, "", "", ""

