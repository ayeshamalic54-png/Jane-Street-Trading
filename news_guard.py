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

_US_INDEX_KEYS = ("US30", "DJ30", "WS30", "DOW", "NAS100", "USTEC", "US100", "NDX", "US500", "SPX")
_EU_INDEX_KEYS = ("GER30", "GER40", "DE30", "DE40", "DAX")
_UK_INDEX_KEYS = ("UK100", "FTSE")
_US_STOCK_KEYS = ("AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMD", "META", "AMZN")


def _is_us_index_or_stock(sym: str) -> bool:
    s = str(sym or "").upper().split(".")[0]
    return any(k in s for k in _US_INDEX_KEYS) or any(k in s for k in _US_STOCK_KEYS)


def _extract_currencies(symbols) -> set:
    currencies = set()
    for s in symbols or []:
        s_clean = str(s).replace("/", "").replace("USDT", "USD").split(".")[0].upper()
        if "XAU" in s_clean or "GOLD" in s_clean:
            currencies.update(("USD", "XAU"))
        elif "XAG" in s_clean or "SILVER" in s_clean:
            currencies.update(("USD", "XAG"))
        elif any(k in s_clean for k in _US_INDEX_KEYS) or any(k in s_clean for k in _US_STOCK_KEYS):
            currencies.add("USD")
        elif any(k in s_clean for k in _EU_INDEX_KEYS):
            currencies.add("EUR")
        elif any(k in s_clean for k in _UK_INDEX_KEYS):
            currencies.add("GBP")
        elif len(s_clean) == 6:
            currencies.add(s_clean[:3])
            currencies.add(s_clean[3:])
        elif len(s_clean) > 3:
            currencies.add(s_clean[-3:])
            currencies.add(s_clean[:-3])
    return currencies


def _load_calendar_events():
    events = []
    cached_data = None
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                cached_data = json.load(f)
        except Exception:
            pass

    if cached_data and (time.time() - cached_data.get("timestamp", 0) < CACHE_EXPIRY_SECONDS):
        return cached_data.get("data", [])

    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=10) as response:
            events = json.loads(response.read().decode("utf-8"))
            with open(CACHE_FILE, "w") as f:
                json.dump({"timestamp": time.time(), "data": events}, f)
            return events
    except Exception:
        if cached_data:
            return cached_data.get("data", [])
        return []


def _is_fixed_major_us_market_holiday(est_date: datetime.date):
    """Fallback guard for major full-day NYSE/NASDAQ closures even if calendar feed is offline."""
    if (est_date.month, est_date.day) in ((1, 1), (7, 4), (12, 25)):
        return True, "US Major Market Holiday"
    # Thanksgiving Day: 4th Thursday of November
    if est_date.month == 11 and est_date.weekday() == 3 and 22 <= est_date.day <= 28:
        return True, "US Thanksgiving Bank Holiday"
    return False, ""


def _check_us_holiday_block(symbols, events, utc_now=None):
    """Blocks thin-liquidity US Bank Holiday sessions on US Equity Indices & Stocks (US30, NAS100, US500)."""
    if not any(_is_us_index_or_stock(s) for s in (symbols or [])):
        return False, ""
    now_utc = utc_now or datetime.datetime.now(datetime.timezone.utc)
    est_now = now_utc - datetime.timedelta(hours=5)
    est_today = est_now.date()

    for event in events or []:
        impact = str(event.get("impact", "")).lower()
        country = str(event.get("country", "")).upper()
        title = str(event.get("title", "Bank Holiday") or "Bank Holiday")
        date_str = str(event.get("date", "") or "")
        if country == "USD" and (impact == "holiday" or "bank holiday" in title.lower()):
            try:
                ev_est_date = datetime.datetime.fromisoformat(date_str).astimezone(
                    datetime.timezone(datetime.timedelta(hours=-5))
                ).date()
                if ev_est_date == est_today:
                    return True, f"USD Bank Holiday ({title})"
            except Exception:
                pass

    fixed_hol, hol_name = _is_fixed_major_us_market_holiday(est_today)
    if fixed_hol:
        return True, hol_name
    return False, ""


def get_news_halt_status(symbols, buffer_minutes=15.0):
    """
    Checks for high-impact economic news and US Index Bank Holidays via ForexFactory feed (5-min cache).
    """
    currencies = _extract_currencies(symbols)
    events = _load_calendar_events()
    utc_now = datetime.datetime.now(datetime.timezone.utc)

    is_hol, hol_reason = _check_us_holiday_block(symbols, events, utc_now)
    if is_hol:
        return True, hol_reason

    if not events:
        return False, f"No high-impact news within {int(buffer_minutes)} minutes"

    for event in events:
        impact = str(event.get("impact", "")).lower()
        country = str(event.get("country", "")).upper()
        event_title = event.get("title", "News")
        date_str = event.get("date", "")

        if impact == "high" and (country in currencies or (country == "USD" and "USD" in currencies)):
            try:
                event_time = datetime.datetime.fromisoformat(date_str).astimezone(datetime.timezone.utc)
                diff_minutes = (event_time - utc_now).total_seconds() / 60.0

                if 0 <= diff_minutes <= buffer_minutes:
                    return True, f"High impact {country} news ({event_title}) in {int(diff_minutes)}m"
                if -buffer_minutes <= diff_minutes < 0:
                    return True, f"High impact {country} news ({event_title}) released {int(abs(diff_minutes))}m ago"
            except Exception:
                pass

    return False, f"No high-impact news within {int(buffer_minutes)} minutes"


def should_auto_close_before_news(symbols, lead_minutes=15.0):
    """
    Returns (True, reason) if high impact news is scheduled within `lead_minutes` before release.
    """
    currencies = _extract_currencies(symbols)
    events = _load_calendar_events()
    if not events:
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
    Currency-Specific High-Impact News & US Index Bank Holiday Enforcement Layer.
    Blocks NEW entries during pre/post high-impact news or USD Bank Holidays (on US30/NAS100).
    Returns: (is_blocked, reason, affected_currency, event_title)
    """
    currencies = _extract_currencies(symbols)
    events = _load_calendar_events()
    utc_now = datetime.datetime.now(datetime.timezone.utc)

    is_hol, hol_reason = _check_us_holiday_block(symbols, events, utc_now)
    if is_hol:
        pair_str = "/".join(symbols) if isinstance(symbols, (list, tuple, set)) else str(symbols)
        logger.info(f"HOLIDAY BLOCK | Currency: USD | Event: {hol_reason} | Pair: {pair_str} | TRADE BLOCKED")
        return True, f"USD BANK HOLIDAY ({hol_reason})", "USD", hol_reason

    if not events:
        return False, "", "", ""

    for event in events:
        impact = str(event.get("impact", "")).lower()
        country = str(event.get("country", "")).upper()
        event_title = event.get("title", "News")
        date_str = event.get("date", "")

        if impact == "high" and (country in currencies or country == "ALL" or (country == "USD" and ("XAU" in currencies or "USD" in currencies))):
            try:
                event_time = datetime.datetime.fromisoformat(date_str).astimezone(datetime.timezone.utc)
                diff_minutes = (event_time - utc_now).total_seconds() / 60.0

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
    """
    currencies = _extract_currencies(symbols)
    events = _load_calendar_events()
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

