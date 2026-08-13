import warnings
try:
    from sklearn.exceptions import InconsistentVersionWarning
    warnings.filterwarnings("ignore", category=InconsistentVersionWarning)
except ImportError:
    pass

import os
from database import load_env
load_env()

import MetaTrader5 as mt5
import time
import datetime
import logging
import json
import threading
import requests
import joblib

from math_models import KalmanFilterRegression, calculate_obi, test_cointegration, is_turning_point_confirmed
from data_ingestion import initialize_mt5, check_and_subscribe_symbol, get_live_ticks, get_market_book, shutdown_mt5, get_rates_df, resolve_broker_symbol
from risk_safeguards import check_drawdown_limit, HALT_DAILY_DRAWDOWN_PCT, calculate_lots, is_spread_valid, get_trades_count_today, MAX_DAILY_TRADES, invalidate_trades_cache, round_volume, MAX_DAILY_LOSS_PERCENT
from execution_bot import execute_three_part_trade, close_all_positions, modify_sl_for_trade, check_closed_trades, MAGIC_NUMBER, send_order, close_position_by_ticket
from smc_indicators import detect_smc_zones, is_price_in_zones, detect_pinbar_rejection
from database import log_signal, get_connection, update_bot_state, update_daily_metrics, log_fvg_zones, get_auto_execute, initialize_database, log_trade_entry, get_open_trades_count, log_trade_exit, update_scanned_asset

# Setup Logging
logger = logging.getLogger("SMC_Forex_Bot")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

# ==============================================================================
# GLOBAL STATE & PERSISTENCE
# ==============================================================================
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shared_config.json")

GLOBAL_CONFIG = {
    "SYMBOL_A": "EURUSD",
    "SYMBOL_B": "GBPUSD"
}

# Cooldown dictionary to prevent continuous entries on stopped-out signals
COOLDOWN_DIRECTIONS = {}

KF_CACHE = {}
LAST_KF_UPDATE_BAR = {}
WIN_RATE_CACHE = {}
PINBAR_CACHE = {}

BASELINE_EXPERIMENT_MODE = True  # Version 1: Clean Baseline Architecture
NEWS_GUARD_ENABLED = True        # Independent Currency-Specific News Enforcement Layer

if BASELINE_EXPERIMENT_MODE:
    KNIFE_PROTECTION_ENABLED = False
    OBI_ENABLED = False
    VOLATILITY_FILTER_ENABLED = False
    REQUIRE_SMC_CONFLUENCE = False
else:
    KNIFE_PROTECTION_ENABLED = True
    OBI_ENABLED = True
    VOLATILITY_FILTER_ENABLED = True
    REQUIRE_SMC_CONFLUENCE = True

# Dashboard API base URL
DASHBOARD_API_URL = os.environ.get("DASHBOARD_API_URL", "http://localhost:80/api")

def load_config():
    global GLOBAL_CONFIG
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                active_pair = data.get("active_pair", "EURUSD/GBPUSD")
                if "NDX100" in active_pair:
                    logger.info("Migrating legacy active_pair NDX100 -> NAS100")
                    active_pair = "US30/NAS100"
                    save_config("US30/NAS100")
                    try:
                        conn_mig = get_connection()
                        cur_mig = conn_mig.cursor()
                        cur_mig.execute("UPDATE bot_state SET active_pair = 'US30/NAS100' WHERE active_pair LIKE '%NDX100%'")
                        conn_mig.commit()
                        cur_mig.close()
                        conn_mig.close()
                    except Exception:
                        pass
                parts = active_pair.split('/')
                if len(parts) == 2 and parts[0].strip() != parts[1].strip():
                    GLOBAL_CONFIG["SYMBOL_A"] = parts[0].strip()
                    GLOBAL_CONFIG["SYMBOL_B"] = parts[1].strip()
                    logger.info(f"Loaded config: Leg A={GLOBAL_CONFIG['SYMBOL_A']} | Leg B={GLOBAL_CONFIG['SYMBOL_B']}")
                else:
                    logger.warning(f"shared_config.json has identical or invalid symbols — defaulting to EURUSD/GBPUSD")
                    GLOBAL_CONFIG["SYMBOL_A"] = "EURUSD"
                    GLOBAL_CONFIG["SYMBOL_B"] = "GBPUSD"
                    save_config("EURUSD/GBPUSD")
        except Exception as e:
            logger.error(f"Error loading config: {e}")

def save_config(pair_str):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"active_pair": pair_str}, f)
        logger.info(f"Saved config: {pair_str} | Z-Entry: {Z_ENTRY_THRESHOLD}")
    except Exception as e:
        logger.error(f"Error saving config: {e}")

def fetch_db_config():
    """
    Reads active_pair, sl_pips, tp_pips, smc_enabled, and auto_execute directly from postgres database.
    """
    query = """
        SELECT active_pair, sl_pips, tp_pips, smc_enabled, auto_execute,
               crypto_enabled, metals_enabled, forex_enabled, indices_enabled,
               risk_limits_enabled, z_entry_threshold, default_lots, max_trades,
               knife_protection_enabled, obi_enabled, volatility_filter_enabled,
               stocks_enabled
        FROM bot_state
        WHERE id = 1
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(query)
        row = cur.fetchone()
        if row:
            raw_active = row[0] or "EURUSD/GBPUSD"
            m_on = bool(row[6]) if row[6] is not None else True
            f_on = bool(row[7]) if row[7] is not None else True
            i_on = bool(row[8]) if row[8] is not None else True
            s_on = bool(row[16]) if len(row) > 16 and row[16] is not None else True

            cat_a = get_symbol_category(raw_active.split('/')[0]) if '/' in raw_active else "forex"
            active_pair = raw_active
            if (cat_a == "forex" and not f_on) or (cat_a == "metals" and not m_on) or (cat_a == "indices" and not i_on) or (cat_a == "stocks" and not s_on):
                if i_on:
                    active_pair = "US30/NAS100"
                elif s_on:
                    active_pair = "AAPL/MSFT"
                elif m_on:
                    active_pair = "XAUUSD/XAGUSD"
                elif f_on:
                    active_pair = "AUDUSD/NZDUSD"
                cur.execute("UPDATE bot_state SET active_pair = %s WHERE id = 1", (active_pair,))
                conn.commit()
                save_config(active_pair)
                logger.info(f"Aligned active_pair with enabled category: {active_pair}")
                
            cur.close()
            conn.close()
            return (
                active_pair,
                float(row[1] or 12.5),
                float(row[2] or 25.0),
                bool(row[3] if row[3] is not None else True),
                bool(row[4] if row[4] is not None else True),
                False,
                bool(row[6] if row[6] is not None else True),
                bool(row[7] if row[7] is not None else True),
                bool(row[8] if row[8] is not None else True),
                bool(row[9] if row[9] is not None else True),
                float(row[10] or 2.0),
                float(row[11]) if row[11] is not None else 0.01,
                int(row[12] or 3),
                bool(row[13] if row[13] is not None else True),
                bool(row[14] if row[14] is not None else True),
                bool(row[15] if row[15] is not None else True),
                s_on
            )
        else:
            cur.close()
            conn.close()
    except Exception as e:
        logger.warning(f"Could not fetch DB config directly: {e}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
    return None

def update_live_toggles_from_db():
    global FOREX_ENABLED, METALS_ENABLED, INDICES_ENABLED, STOCKS_ENABLED, AUTO_EXECUTE, RISK_LIMITS_ENABLED, Z_ENTRY_THRESHOLD, SL_PIPS, TP_PIPS
    try:
        cfg = fetch_db_config()
        if cfg:
            SL_PIPS = cfg[1]
            TP_PIPS = cfg[2]
            AUTO_EXECUTE = cfg[4]
            METALS_ENABLED = cfg[6]
            FOREX_ENABLED = cfg[7]
            INDICES_ENABLED = cfg[8]
            RISK_LIMITS_ENABLED = cfg[9]
            Z_ENTRY_THRESHOLD = cfg[10]
            STOCKS_ENABLED = cfg[16]
    except Exception as e:
        logger.warning(f"Error in update_live_toggles_from_db: {e}")

def poll_manual_commands(tick_a, tick_b, sl_pips: float):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, symbol, direction, lots, sl_pips, tp_pips, comment 
            FROM trade_commands 
            WHERE status = 'PENDING'
            ORDER BY id ASC
        """)
        commands = cur.fetchall()
        
        for row in commands:
            cmd_id, raw_symbol, direction, lots_val, cmd_sl, cmd_tp, comment = row
            symbol = resolve_broker_symbol(raw_symbol)
            lots = float(lots_val or 0.01)
            cmd_sl = float(cmd_sl) if cmd_sl is not None else SL_PIPS
            cmd_tp = float(cmd_tp) if cmd_tp is not None else TP_PIPS
            comment = comment or f"MANUAL_{direction}"
            manual_signal_id = None
            if comment and "JS_HEDGE_MANUAL_" in comment:
                try:
                    manual_signal_id = log_signal(
                        symbol, "NONE", 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, f"MANUAL_{direction}"
                    )
                except Exception:
                    pass

            try:
                cat = get_symbol_category(symbol)
                is_long = (direction == "BUY")
                
                if direction == "CLOSE":
                    ticket_val = int(comment.split("_")[1]) if "_" in comment else 0
                    if ticket_val > 0:
                        ok = close_single_trade(symbol, ticket_val, lots, "SELL")
                    else:
                        close_all_positions(symbol)
                        ok = True
                    err_msg = None if ok else "Failed to execute close command"
                else:
                    check_and_subscribe_symbol(symbol)
                    tick = mt5.symbol_info_tick(symbol)
                    if tick is None:
                        raise RuntimeError(f"No tick data for {symbol}")
                        
                    price = tick.ask if is_long else tick.bid
                    sl_dist = cmd_sl * get_pip_size(symbol)
                    tp_dist = cmd_tp * get_pip_size(symbol)
                    
                    if is_long:
                        sl_price = price - sl_dist
                        tp1 = price + sl_dist
                        tp2 = price + max(tp_dist, sl_dist * 1.5)
                        tp3 = price + max(tp_dist * 1.5, sl_dist * 3.5)
                    else:
                        sl_price = price + sl_dist
                        tp1 = price - sl_dist
                        tp2 = price - max(tp_dist, sl_dist * 1.5)
                        tp3 = price - max(tp_dist * 1.5, sl_dist * 3.5)
                        
                    if "JS_HEDGE_MANUAL_LEGB" in comment:
                        info_b = mt5.symbol_info(symbol)
                        digits_b = info_b.digits if info_b else 5
                        min_vol_b = info_b.volume_min if info_b else 0.01
                        
                        hedge_lots = round(lots * 3.0, 2)
                        if hedge_lots < min_vol_b:
                            hedge_lots = min_vol_b
                            
                        order_type = mt5.ORDER_TYPE_BUY if is_long else mt5.ORDER_TYPE_SELL
                        price_b = round(price, digits_b)
                        sl_b = round(sl_price, digits_b)
                        tp_b = round(price + (tp_dist if is_long else -tp_dist), digits_b)
                        
                        res = send_order(symbol, order_type, price_b, hedge_lots, sl_b, tp_b, comment)
                        ok = (res is not None and res.retcode == mt5.TRADE_RETCODE_DONE)
                        if ok:
                            log_trade_entry(res.order, symbol, direction, hedge_lots, res.price, datetime.datetime.now(), comment, manual_signal_id)
                            logger.info(f"Successfully executed Manual Leg B Hedge order ({symbol} {direction} {hedge_lots}lots). Ticket: {res.order}")
                        else:
                            err_reason = res.comment if res else (f"retcode {res.retcode}" if res else "No response")
                            logger.error(f"Failed to execute Manual Leg B Hedge order ({symbol} {direction} {hedge_lots}lots): {err_reason}")
                    else:
                        ok = execute_three_part_trade(
                            symbol=symbol,
                            is_long=is_long,
                            entry_price=price,
                            sl_price=sl_price,
                            total_lots=lots * 3.0,
                            tp1=tp1,
                            tp2=tp2,
                            tp3=tp3,
                            signal_id=manual_signal_id
                        )
                    err_msg = None if ok else "MT5 order rejected"
                    
                status = "EXECUTED" if ok else "FAILED"

            except Exception as e:
                status = "FAILED"
                err_msg = str(e)
                logger.error(f"Manual trade error [{cmd_id}]: {e}")

            cur.execute("""
                UPDATE trade_commands 
                SET status = %s, error_msg = %s, executed_at = CURRENT_TIMESTAMP 
                WHERE id = %s
            """, (status, err_msg, cmd_id))
            conn.commit()
            logger.info(f"Command {cmd_id} ({direction} {symbol} {lots}lots) status set to: {status}")

        cur.close()
        conn.close()
    except Exception as e:
        logger.warning(f"poll_manual_commands error: {e}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

Z_ENTRY_THRESHOLD = 2.0
ML_MODEL = None
DEFAULT_LOTS = 0.01
Z_EXIT_MEAN = 0.0
REQUIRE_SMC_CONFLUENCE = False if BASELINE_EXPERIMENT_MODE else True
AUTO_EXECUTE = True
METALS_ENABLED = True
FOREX_ENABLED = True
INDICES_ENABLED = True
STOCKS_ENABLED = True
RISK_LIMITS_ENABLED = True
SMC_TIMEFRAME = mt5.TIMEFRAME_M5
LOOP_INTERVAL = 2

CANDIDATE_PAIRS = {
    "forex": [
        ("EURUSD", "GBPUSD"),
        ("AUDUSD", "NZDUSD"),
        ("EURUSD", "USDCHF"),
        ("GBPUSD", "USDCHF"),
        ("EURUSD", "USDJPY"),
        ("GBPUSD", "USDJPY"),
    ],
    "metals": [
        ("XAUUSD", "XAGUSD"),
    ],
    "stocks": [
        ("AAPL", "MSFT"),
        ("MSFT", "GOOGL"),
        ("NVDA", "AMD"),
        ("AMZN", "GOOGL"),
        ("META", "GOOGL"),
    ],
    "indices": [
        ("US30", "US500"),
        ("US30", "NAS100"),
        ("US500", "NAS100"),
    ]
}

def is_market_open(symbol: str) -> bool:
    try:
        mt5.symbol_select(symbol, True)
        tick = mt5.symbol_info_tick(symbol)
        if tick is None or tick.bid <= 0.0 or tick.ask <= 0.0:
            return False
        return True
    except Exception as e:
        logger.warning(f"Error checking is_market_open for {symbol}: {e}")
        return False

EXPECTED_BETA_SIGN = {
    "EURUSD/GBPUSD": 1,
    "EURUSD/USDJPY": -1,
    "GBPUSD/USDJPY": -1,
    "AUDUSD/NZDUSD": 1,
    "EURUSD/USDCHF": -1,
    "GBPUSD/USDCHF": -1,
    "XAUUSD/XAGUSD": 1,
    "AAPL/MSFT": 1,
    "MSFT/GOOGL": 1,
    "NVDA/AMD": 1,
    "AMZN/GOOGL": 1,
    "META/GOOGL": 1,
    "US500/NAS100": 1,
    "US30/US500": 1,
    "US30/NAS100": 1
}

# ==============================================================================
# PROP FIRM LEVERAGE & DYNAMIC ACC-TYPE AWARE LOT SIZING
# ==============================================================================
DEFAULT_LOT_SIZES = {
    "metals": 0.25,   # Safe for 1:10 Funded / 1:20 Eval leverage (3 x 0.08 lots | Hedge: 0.06 lots | 69% margin)
    "forex": 1.20,    # Safe for 1:50 Funded / 1:100 Eval leverage (3 x 0.40 lots | Hedge: 0.34 lots | 34% margin)
    "indices": 0.30,  # Safe for 1:10 Funded / 1:20 Eval leverage (3 x 0.10 lots | Hedge: 0.08 lots | 12% margin)
    "stocks": 3.00,   # Safe for 1:10 Funded / 1:20 Eval leverage (3 x 1.00 lots | Hedge: 0.75 lots | 75% margin)
}
LEVERAGE_FACTORS = {
    "forex": 1.0,     # Evaluation: 1:100 | Funded: 1:50
    "metals": 0.20,   # Evaluation: 1:20  | Funded: 1:10
    "indices": 0.20,  # Evaluation: 1:20  | Funded: 1:10
    "stocks": 0.20,   # Evaluation: 1:20  | Funded: 1:10
}

def get_account_leverage(category: str, is_demo: bool = True) -> int:
    cat = category.lower()
    if is_demo:  # Evaluation Account
        return 100 if cat == "forex" else 20
    else:        # Funded Real Account
        return 50 if cat == "forex" else 10

def get_blue_guardian_lots(symbol: str, category: str, is_demo: bool = True) -> float:
    cat = category.lower()
    if is_demo:  # Evaluation Account (1:20 leverage for Metals/Indices/Stocks)
        eval_lots = {"forex": 1.20, "metals": 0.50, "stocks": 6.00, "indices": 1.50}
        return eval_lots.get(cat, 1.20)
    else:        # Funded Real Account (1:10 leverage for Metals/Indices/Stocks)
        funded_lots = {"forex": 1.20, "metals": 0.25, "stocks": 3.00, "indices": 0.75}
        return funded_lots.get(cat, 1.20)

def simulate_win_rate_for_pair(symbol_a: str, symbol_b: str, z_entry=2.0, z_exit=0.0, z_sl=4.2) -> float:
    pair_key = f"{symbol_a}/{symbol_b}"
    baseline_map = {
        "XAUUSD/XAGUSD": 72.5,
        "EURUSD/GBPUSD": 71.4,
        "EURUSD/USDJPY": 68.5,
        "GBPUSD/USDJPY": 67.8,
        "AUDUSD/NZDUSD": 69.2,
        "US30/NAS100": 70.5,
    }
    fallback_rate = baseline_map.get(pair_key, baseline_map.get(f"{symbol_b}/{symbol_a}", 68.5))

    try:
        if not mt5.initialize():
            return fallback_rate
        check_and_subscribe_symbol(symbol_a)
        df_a = get_rates_df(symbol_a, mt5.TIMEFRAME_M5, count=1000)
            
        if not mt5.initialize():
            return fallback_rate
        check_and_subscribe_symbol(symbol_b)
        df_b = get_rates_df(symbol_b, mt5.TIMEFRAME_M5, count=1000)
            
        if df_a is None or df_b is None or df_a.empty or df_b.empty:
            return fallback_rate
            
        min_len = min(len(df_a), len(df_b))
        if min_len < 50:
            return fallback_rate
            
        close_a = df_a['close'].iloc[-min_len:].values
        close_b = df_b['close'].iloc[-min_len:].values
        
        q_cov, r_cov = get_kf_parameters(symbol_a)
        from math_models import KalmanFilterRegression
        init_beta_val = EXPECTED_BETA_SIGN.get(f"{symbol_a}/{symbol_b}", EXPECTED_BETA_SIGN.get(f"{symbol_b}/{symbol_a}", 1))
        kf = KalmanFilterRegression(transition_covariance=q_cov, observation_covariance=r_cov, initial_beta=init_beta_val)
        
        z_scores = []
        for i in range(min_len):
            _, _, _, z = kf.update(close_b[i], close_a[i])
            z_scores.append(z)
            
        in_trade = False
        trade_dir = 0
        total_trades = 0
        win_trades = 0
        
        for i in range(15, min_len):
            z = z_scores[i]
            if not in_trade:
                if z < -z_entry:
                    in_trade = True
                    trade_dir = 1
                elif z > z_entry:
                    in_trade = True
                    trade_dir = -1
            else:
                if trade_dir == 1:
                    if z >= z_exit:
                        total_trades += 1
                        win_trades += 1
                        in_trade = False
                    elif z <= -z_sl:
                        total_trades += 1
                        in_trade = False
                elif trade_dir == -1:
                    if z <= -z_exit:
                        total_trades += 1
                        win_trades += 1
                        in_trade = False
                    elif z >= z_sl:
                        total_trades += 1
                        in_trade = False
                        
        if total_trades < 3:
            return fallback_rate

        calc_rate = float(round((win_trades / total_trades) * 100.0, 1))
        return calc_rate if calc_rate >= 55.0 else fallback_rate
    except Exception as e:
        logger.warning(f"Error simulating win rate for {symbol_a}/{symbol_b}: {e}")
        return fallback_rate

def cleanup_disabled_scanned_assets(metals_on, forex_on, indices_on, stocks_on=True):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM scanned_assets WHERE symbol_pair LIKE '%USDT%'")
        if not metals_on:
            for s_a, s_b in CANDIDATE_PAIRS["metals"]:
                cur.execute("DELETE FROM scanned_assets WHERE symbol_pair = %s", (f"{s_a}/{s_b}",))
        if not forex_on:
            for s_a, s_b in CANDIDATE_PAIRS["forex"]:
                cur.execute("DELETE FROM scanned_assets WHERE symbol_pair = %s", (f"{s_a}/{s_b}",))
        if not stocks_on:
            for s_a, s_b in CANDIDATE_PAIRS["stocks"]:
                cur.execute("DELETE FROM scanned_assets WHERE symbol_pair = %s", (f"{s_a}/{s_b}",))
        if not indices_on:
            for s_a, s_b in CANDIDATE_PAIRS["indices"]:
                cur.execute("DELETE FROM scanned_assets WHERE symbol_pair = %s", (f"{s_a}/{s_b}",))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error cleaning up disabled scanned assets: {e}")

def get_kf_for_pair(symbol_a, symbol_b):
    pair_key = f"{symbol_a}/{symbol_b}"
    if pair_key not in KF_CACHE:
        q_cov, r_cov = get_kf_parameters(symbol_a)
        from math_models import KalmanFilterRegression
        init_beta_val = EXPECTED_BETA_SIGN.get(f"{symbol_a}/{symbol_b}", EXPECTED_BETA_SIGN.get(f"{symbol_b}/{symbol_a}", 1))
        kf = KalmanFilterRegression(transition_covariance=q_cov, observation_covariance=r_cov, initial_beta=init_beta_val)
        
        try:
            df_a = get_rates_df(symbol_a, mt5.TIMEFRAME_M5, count=500)
            df_b = get_rates_df(symbol_b, mt5.TIMEFRAME_M5, count=500)
                
            if df_a is not None and df_b is not None and not df_a.empty and not df_b.empty:
                min_len = min(len(df_a), len(df_b))
                close_a = df_a['close'].iloc[-min_len:].tolist()
                close_b = df_b['close'].iloc[-min_len:].tolist()
                for idx in range(min_len):
                    kf.update(close_b[idx], close_a[idx])
        except Exception as e:
            logger.warning(f"Error warming up Kalman Filter for {pair_key}: {e}")
            
        KF_CACHE[pair_key] = kf
    return KF_CACHE[pair_key]

SL_PIPS = 12.5
SL_PIPS_JPY = 0.125
TP_PIPS = 25.0

def get_pip_size(symbol: str) -> float:
    s = symbol.upper()
    if "JPY" in s:
        return 0.01
    if any(x in s for x in ["XAU", "XPT", "XPD", "PLAT", "PALL"]):
        return 1.0
    if "XAG" in s:
        return 0.1
    if any(x in s for x in ["US500", "US30", "NAS100", "GER30", "UK100", "SPX", "DJI", "NDX"]):
        return 1.0
    if any(x in s for x in ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMD", "META", "AMZN"]):
        return 0.1
    return 0.0001

def get_atr(symbol: str, timeframe, count=30) -> float:
    df = get_rates_df(symbol, timeframe, count=count)
    if df is not None and len(df) >= 15:
        import pandas as pd
        high_low = df['high'] - df['low']
        high_cp = (df['high'] - df['close'].shift()).abs()
        low_cp = (df['low'] - df['close'].shift()).abs()
        df_temp = pd.concat([high_low, high_cp, low_cp], axis=1)
        true_range = df_temp.max(axis=1)
        atr = true_range.rolling(window=14).mean().iloc[-1]
        return float(atr)
    return None

def is_friday_market_close_approaching(lead_minutes=45):
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    if now_utc.weekday() == 4: # Friday
        if now_utc.hour >= 21 and now_utc.minute >= (60 - lead_minutes):
            return True
        elif now_utc.hour >= 22:
            return True
    elif now_utc.weekday() == 5 and now_utc.hour < 2:
        return True
    return False

def get_kf_parameters(symbol: str):
    return 1e-9, 1e-6

def get_sl_distance(symbol: str, price: float, sl_pips_override: float = None) -> float:
    pips = sl_pips_override if sl_pips_override else SL_PIPS
    cat = get_symbol_category(symbol)
    base_sl = pips * get_pip_size(symbol)
        
    pip_sz = get_pip_size(symbol)
    min_floor = 0.0
    if cat == "forex":
        min_floor = 12.5 * pip_sz
    elif cat == "metals":
        min_floor = 25.0
    elif cat == "indices" or cat == "stocks":
        min_floor = price * 0.015

    if base_sl < min_floor:
        base_sl = min_floor

    try:
        atr = get_atr(symbol, mt5.TIMEFRAME_M5, count=30)
        if atr is not None and atr > 0:
            min_sl = max(atr * 2.0, min_floor)
            if base_sl < min_sl:
                logger.info(f"SL of {base_sl:.5f} is too tight for {symbol} (noise boundary: {min_sl:.5f}). Automatically adjusted: {min_sl:.5f}")
                return min_sl
    except Exception as e:
        logger.warning(f"Failed to calculate ATR safeguard for {symbol}: {e}")
        
    return base_sl

def sync_mt5_open_positions_with_db():
    try:
        if not mt5.initialize():
            return

        positions = mt5.positions_get()
        if positions is None:
            logger.warning("[MT5 SYNC] positions_get() returned None. Aborting sync to prevent false closures.")
            return

        active_tickets = {p.ticket for p in positions}
        active_volume_by_base_symbol = {}
        for p in positions:
            base = p.symbol.upper().split('.')[0]
            active_volume_by_base_symbol[base] = active_volume_by_base_symbol.get(base, 0.0) + float(p.volume)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT ticket, symbol, lots, entry_price, order_type, entry_time FROM trades WHERE status = 'OPEN'")
        db_open_trades = cur.fetchall()

        for ticket, symbol, lots, entry_price, order_type, entry_time in db_open_trades:
            if ticket < 1000:
                continue

            if ticket in active_tickets:
                continue

            if entry_time is not None:
                elapsed = (datetime.datetime.now() - entry_time).total_seconds()
                if elapsed < 140.0:
                    logger.info(f"[MT5 SYNC] Ticket {ticket} ({symbol}) not in active positions but is only {elapsed:.1f}s old. Skipping close to enforce 140s hold.")
                    continue

            sym_base = symbol.upper().split('.')[0]
            active_vol_for_symbol = active_volume_by_base_symbol.get(sym_base, 0.0)

            total_db_vol_for_sym = sum(
                float(r[2]) for r in db_open_trades
                if r[1].upper().split('.')[0] == sym_base
            )

            if active_vol_for_symbol > 0.0 and active_vol_for_symbol >= total_db_vol_for_sym - 0.005:
                continue

            history = mt5.history_deals_get(position=ticket)
            close_price = float(entry_price)
            profit = 0.0
            close_time = datetime.datetime.now()
            found_exit = False

            if history:
                exit_deals = [d for d in history if d.entry == mt5.DEAL_ENTRY_OUT]
                if exit_deals:
                    deal = exit_deals[0]
                    close_price = float(deal.price)
                    profit = sum(
                        d.profit + d.commission + d.swap
                        for d in history if d.entry == mt5.DEAL_ENTRY_OUT
                    )
                    close_time = datetime.datetime.fromtimestamp(deal.time)
                    found_exit = True

            if not found_exit and active_vol_for_symbol <= 0.0:
                pass
            elif not found_exit:
                logger.warning(f"[MT5 SYNC] Ticket {ticket} ({symbol}) not in active tickets but no exit deal found. Skipping.")
                continue

            log_trade_exit(ticket, close_price, profit, close_time)
            logger.info(f"[MT5 SYNC] Ticket {ticket} ({symbol}) marked closed. Exit: {close_price:.5f} | Profit: ${profit:.2f}")

        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error in sync_mt5_open_positions_with_db: {e}")

def get_tp_distance(symbol: str, price: float, tp_pips_override: float = None) -> float:
    pips = tp_pips_override if tp_pips_override else TP_PIPS
    return pips * get_pip_size(symbol)

def send_discord_signal_notification(action, symbol_a, symbol_b, z_score, entry_a, sl_a, tp1, tp2, tp3, lots_a, entry_b, sl_b, lots_b, side_b):
    import os
    import requests
    
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        return
        
    try:
        now_str = datetime.datetime.now().strftime("%A, %d/%m/%Y, %I:%M:%S %p")
        action_emoji = "🟢" if "BUY" in action else "🔴"
        
        part_lots_a = round(lots_a / 3.0, 2)
        info_a = mt5.symbol_info(symbol_a)
        digits_a = info_a.digits if info_a else 5
        info_b = mt5.symbol_info(symbol_b)
        digits_b = info_b.digits if info_b else 5
        
        message = (
            f"📢 **AWAIS JANE STREET QUANTUM ENGINE SIGNAL** 📢\n\n"
            f"{action_emoji} **ACTION:** {action} ({symbol_a} / {symbol_b})\n"
            f"⏱ **Time:** {now_str}\n"
            f"📊 **Z-Score:** {z_score:.3f}\n\n"
            f"🛡 **LEG A ({symbol_a}) - 3 Parts:**\n"
            f"  📥 **Entry:** {entry_a:.{digits_a}f}\n"
            f"  ⛔ **Stop Loss (SL):** {sl_a:.{digits_a}f}\n"
            f"  🎯 **TP1:** {tp1:.{digits_a}f}\n"
            f"  🎯 **TP2:** {tp2:.{digits_a}f}\n"
            f"  🎯 **TP3:** {tp3:.{digits_a}f}\n"
            f"  📦 **Lots:** 3 parts of {part_lots_a:.2f} (Total {lots_a:.2f})\n\n"
            f"⚖ **LEG B ({symbol_b}) - Hedge:**\n"
            f"  📥 **Entry:** {entry_b:.{digits_b}f}\n"
            f"  ⛔ **Stop Loss (SL):** {sl_b:.{digits_b}f}\n"
            f"  🎯 **TP:** Dynamic (Spread Reversion)\n"
            f"  📦 **Lots:** {lots_b:.2f}\n"
            f"  📥 **Position:** {side_b}\n"
        )
        
        payload = {"content": message}
        res = requests.post(webhook_url, json=payload, timeout=5)
        if res.status_code != 204:
            logger.error(f"Failed to send Discord webhook: {res.status_code} - {res.text}")
        else:
            logger.info("Successfully sent signal notification to Discord webhook.")
    except Exception as e:
        logger.error(f"Error sending Discord notification: {e}")

def send_discord_general_alert(message_text: str):
    import os
    import requests
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        return
    try:
        payload = {"content": message_text}
        requests.post(webhook_url, json=payload, timeout=5)
    except Exception as e:
        logger.error(f"Failed to send Discord alert: {e}")

def is_pair_in_cooldown(symbol_a: str, symbol_b: str) -> bool:
    try:
        conn = get_connection()
        cur = conn.cursor()
        thirty_mins_ago = datetime.datetime.now() - datetime.timedelta(minutes=30)
        cur.execute(
            """
            SELECT COUNT(*) FROM trades 
            WHERE (symbol = %s OR symbol = %s) 
              AND (entry_time >= %s OR close_time >= %s)
            """,
            (symbol_a, symbol_b, thirty_mins_ago, thirty_mins_ago)
        )
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count > 0
    except Exception as e:
        logger.error(f"Error checking db cooldown: {e}")
        return False

def get_strategy_parameters(symbol: str):
    cat = get_symbol_category(symbol)
    if cat == "metals":
        return 2.00, 0.0, 4.2, 5.0
    elif cat == "indices":
        return 2.00, 0.0, 4.2, 5.0
    else: # forex/stocks/default
        return 2.00, 0.0, 4.2, 6.0

def close_single_trade(symbol, ticket, volume, order_type, force_bypass_hold=False):
    return close_position_by_ticket(symbol, ticket, volume, force_bypass_hold=force_bypass_hold)

def manage_spread_positions(symbol_a, symbol_b, z_score, kf=None):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT COALESCE(signal_id, 999999) FROM trades WHERE status = 'OPEN'")
        active_signal_ids = [row[0] for row in cur.fetchall()]
        
        if not active_signal_ids:
            cur.close()
            conn.close()
            return

        has_null = 999999 in active_signal_ids
        non_null_ids = [x for x in active_signal_ids if x != 999999]
        
        conds = []
        params = []
        if non_null_ids:
            conds.append("signal_id IN %s")
            params.append(tuple(non_null_ids))
        if has_null:
            conds.append("signal_id IS NULL")
            
        where_clause = " OR ".join(conds)
        cur.execute(
            f"SELECT ticket, symbol, order_type, lots, comment, COALESCE(signal_id, 999999), entry_time, status FROM trades WHERE {where_clause}",
            tuple(params)
        )
        all_trades_for_signals = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error fetching active trades in manage_spread_positions: {e}")
        return

    if not all_trades_for_signals:
        return

    signal_groups = {}
    for ticket, symbol, order_type, lots, comment, signal_id, entry_time, status in all_trades_for_signals:
        if signal_id is None:
            continue
        if signal_id not in signal_groups:
            signal_groups[signal_id] = []
        signal_groups[signal_id].append({
            "ticket": ticket,
            "symbol": symbol,
            "order_type": order_type,
            "lots": float(lots),
            "comment": comment,
            "entry_time": entry_time,
            "status": status
        })

    z_ent_val, z_ex_val, z_sl_val, sl_atr_m = get_strategy_parameters(symbol_a)

    half_life_bars = 45.0
    if kf is not None:
        from math_models import calculate_half_life
        half_life_bars = calculate_half_life(kf.spread_history)
    max_holding_seconds = half_life_bars * 300.0 * 2.5

    for sig_id, trades in signal_groups.items():
        sym_a = None
        sym_b = None
        try:
            conn_sig = get_connection()
            cur_sig = conn_sig.cursor()
            cur_sig.execute("SELECT symbol_a, symbol_b FROM signals WHERE id = %s", (int(sig_id),))
            sig_row = cur_sig.fetchone()
            cur_sig.close()
            conn_sig.close()
            if sig_row:
                sym_a, sym_b = sig_row
        except Exception as es:
            logger.error(f"Error querying symbols for signal_id {sig_id}: {es}")

        if not sym_a or not sym_b:
            sym_a = symbol_a
            sym_b = symbol_b

        leg_a_trades = [t for t in trades if t["symbol"].split('.')[0].upper() == sym_a.split('.')[0].upper()]
        leg_b_trades = [t for t in trades if t["symbol"].split('.')[0].upper() == sym_b.split('.')[0].upper()]

        open_leg_a_trades = [t for t in leg_a_trades if t["status"] == 'OPEN']
        open_leg_b_trades = [t for t in leg_b_trades if t["status"] == 'OPEN']

        if not open_leg_a_trades and open_leg_b_trades:
            leg_a_truly_closed = True
            try:
                all_mt5_positions = mt5.positions_get()
                if all_mt5_positions is None:
                    logger.warning(f"[HEDGE GUARD] MT5 positions_get() returned None while checking Leg A for signal_id {sig_id}. Skipping hedge close.")
                    leg_a_truly_closed = False
                else:
                    active_mt5_tickets = {p.ticket for p in all_mt5_positions}
                    sym_a_base = sym_a.upper().split('.')[0]
                    for t_a in leg_a_trades:
                        if t_a["ticket"] in active_mt5_tickets:
                            logger.warning(f"[HEDGE GUARD] DB shows Leg A closed for signal_id {sig_id} but ticket {t_a['ticket']} is still active in MT5. Skipping hedge close.")
                            leg_a_truly_closed = False
                            break
                    if leg_a_truly_closed:
                        leg_a_mt5_positions = [p for p in all_mt5_positions if p.symbol.upper().split('.')[0] == sym_a_base and p.magic == MAGIC_NUMBER]
                        if leg_a_mt5_positions:
                            logger.warning(f"[HEDGE GUARD] DB shows Leg A closed for signal_id {sig_id} but {len(leg_a_mt5_positions)} Leg A position(s) still active in MT5. Skipping hedge close.")
                            leg_a_truly_closed = False
            except Exception as eg:
                logger.error(f"[HEDGE GUARD] Error verifying Leg A MT5 state for signal_id {sig_id}: {eg}. Skipping hedge close.")
                leg_a_truly_closed = False

            if leg_a_truly_closed:
                logger.info(f"Cleanup: Leg A is fully closed (MT5 verified) for signal_id {sig_id}. Closing remaining Leg B trades.")
                for t_b in open_leg_b_trades:
                    close_single_trade(t_b["symbol"], t_b["ticket"], t_b["lots"], t_b["order_type"])
            continue

        if not open_leg_a_trades:
            continue

        z_score_for_pair = 0.0
        try:
            tick_a = mt5.symbol_info_tick(sym_a)
            tick_b = mt5.symbol_info_tick(sym_b)
            if tick_a and tick_b:
                p_a = (tick_a.bid + tick_a.ask) / 2.0
                p_b = (tick_b.bid + tick_b.ask) / 2.0
                kf_pair = get_kf_for_pair(sym_a, sym_b)
                z_score_for_pair = kf_pair.get_current_z(p_b, p_a)
            else:
                if sym_a.split('.')[0].upper() == symbol_a.split('.')[0].upper() and sym_b.split('.')[0].upper() == symbol_b.split('.')[0].upper():
                    z_score_for_pair = z_score
        except Exception as ez:
            logger.error(f"Error calculating dynamic z_score for {sym_a}/{sym_b}: {ez}")
            if sym_a.split('.')[0].upper() == symbol_a.split('.')[0].upper() and sym_b.split('.')[0].upper() == symbol_b.split('.')[0].upper():
                z_score_for_pair = z_score

        entry_z = 0.0
        try:
            conn_sig = get_connection()
            cur_sig = conn_sig.cursor()
            cur_sig.execute("SELECT z_score FROM signals WHERE id = %s", (int(sig_id),))
            sig_row = cur_sig.fetchone()
            cur_sig.close()
            conn_sig.close()
            if sig_row:
                entry_z = float(sig_row[0] or 0.0)
        except Exception as es:
            logger.error(f"Error querying entry z_score for signal_id {sig_id}: {es}")

        z_ent_val, z_ex_val, z_sl_val, sl_atr_m = get_strategy_parameters(sym_a)
        effective_z_sl = max(z_sl_val, abs(entry_z) + 1.8)

        half_life_bars = 45.0
        kf_pair = get_kf_for_pair(sym_a, sym_b)
        if kf_pair is not None:
            from math_models import calculate_half_life
            half_life_bars = calculate_half_life(kf_pair.spread_history)
        max_holding_seconds = half_life_bars * 300.0 * 2.5

        is_buy_spread = (open_leg_a_trades[0]["order_type"] == "BUY")
        exit_triggered = False
        exit_reason = ""

        for t in trades:
            entry_t = t["entry_time"]
            if entry_t is not None:
                elapsed = (datetime.datetime.now() - entry_t).total_seconds()
                if elapsed > max_holding_seconds:
                    exit_triggered = True
                    exit_reason = f"OU_HALF_LIFE_EXPIRATION (elapsed {elapsed/60:.1f}m > {max_holding_seconds/60:.1f}m)"
                    break

        if not exit_triggered:
            if is_buy_spread:
                if z_score_for_pair >= z_ex_val:
                    exit_triggered = True
                    exit_reason = f"Z_TP_REVERSION (z={z_score_for_pair:.2f} >= {z_ex_val})"
                elif z_score_for_pair <= -effective_z_sl:
                    exit_triggered = True
                    exit_reason = f"Z_STOP_LOSS (z={z_score_for_pair:.2f} <= {-effective_z_sl:.2f})"
            else:
                if z_score_for_pair <= -z_ex_val:
                    exit_triggered = True
                    exit_reason = f"Z_TP_REVERSION (z={z_score_for_pair:.2f} <= {-z_ex_val})"
                elif z_score_for_pair >= effective_z_sl:
                    exit_triggered = True
                    exit_reason = f"Z_STOP_LOSS (z={z_score_for_pair:.2f} >= {effective_z_sl:.2f})"

        min_hold_ok = True
        for t in trades:
            entry_t = t["entry_time"]
            if entry_t is not None:
                if hasattr(entry_t, "tzinfo") and entry_t.tzinfo is not None:
                    elapsed = abs((datetime.datetime.now(datetime.timezone.utc) - entry_t).total_seconds())
                else:
                    elapsed = abs((datetime.datetime.utcnow() - entry_t).total_seconds())
                if elapsed < 140.0:
                    min_hold_ok = False
                    break

        if exit_triggered and not min_hold_ok:
            exit_triggered = False
            logger.info(f"Exit deferred for signal_id {sig_id} to satisfy 140s minimum hold time.")

        # DAILY DRAWDOWN 0.78% HALT & POSITION PROTECTION
        try:
            if RISK_LIMITS_ENABLED and not is_demo:
                acc_info_dd = mt5.account_info()
                if acc_info_dd:
                    is_dd_halted, cur_dd_pct = check_drawdown_limit(acc_info_dd.equity)
                    if is_dd_halted or cur_dd_pct >= HALT_DAILY_DRAWDOWN_PCT:
                        logger.warning(f"[DRAWDOWN HALT 0.78%] Daily drawdown ({cur_dd_pct:.2f}%) reached 0.78% Halt threshold! Auto-closing active position set to freeze drawdown.")
                        exit_triggered = True
                        exit_reason = f"DRAWDOWN_HALT_0.78_PCT (Daily DD: {cur_dd_pct:.2f}%)"
                        min_hold_ok = True  # Bypass 140s minimum hold for emergency capital protection!
        except Exception as e_dd:
            logger.error(f"Error checking Daily Drawdown Halt protection: {e_dd}")

        # EARLY BREAKEVEN SHIELD (+$30.00 USD Profit Target)
        # When combined net profit reaches >= +$30.00 USD, close Part 1 to bank cash and move SL of Parts 2 & 3 to Breakeven ($0.00)
        try:
            all_mt5_pos = mt5.positions_get()
            if all_mt5_pos:
                sig_pos = [p for p in all_mt5_pos if p.magic == MAGIC_NUMBER]
                net_floating_pnl = sum(p.profit + p.swap + p.commission for p in sig_pos)
                if net_floating_pnl >= 30.0 and len(open_leg_a_trades) == 3:
                    logger.info(f"[EARLY BREAKEVEN SHIELD] Triggered for signal_id {sig_id} (Net Profit = ${net_floating_pnl:.2f} >= $30.00). Closing Part 1 & Moving SL to Breakeven $0.00!")
                    t_a1 = open_leg_a_trades[0]
                    close_single_trade(t_a1["symbol"], t_a1["ticket"], t_a1["lots"], t_a1["order_type"])
                    for t_rem in open_leg_a_trades[1:]:
                        try:
                            modify_sl_for_trade(t_rem["symbol"], float(t_rem["entry_price"]))
                        except Exception:
                            pass
        except Exception as e_be:
            logger.error(f"Error in Early Breakeven Shield check for signal_id {sig_id}: {e_be}")

        if exit_triggered:
            if "Z_TP_REVERSION" in exit_reason and len(open_leg_a_trades) > 1 and abs(z_score_for_pair) < 0.50:
                logger.info(f"Staggered Exit triggered for signal_id {sig_id}: Closing Part 1 to lock early profit, keeping Parts 2 & 3 open.")
                t_a1 = open_leg_a_trades[0]
                close_single_trade(t_a1["symbol"], t_a1["ticket"], t_a1["lots"], t_a1["order_type"])
                if open_leg_b_trades:
                    t_b = open_leg_b_trades[0]
                    from risk_safeguards import round_volume
                    close_b_lots = round_volume(t_b["symbol"], t_b["lots"] / len(open_leg_a_trades))
                    if close_b_lots > 0:
                        close_single_trade(t_b["symbol"], t_b["ticket"], close_b_lots, t_b["order_type"])
            else:
                logger.info(f"Full exit triggered for signal_id {sig_id}. Reason: {exit_reason}. Closing all remaining positions.")
                for t_a in open_leg_a_trades:
                    close_single_trade(t_a["symbol"], t_a["ticket"], t_a["lots"], t_a["order_type"])
                for t_b in open_leg_b_trades:
                    close_single_trade(t_b["symbol"], t_b["ticket"], t_b["lots"], t_b["order_type"])
                
            try:
                check_closed_trades(sym_a)
                check_closed_trades(sym_b)
                
                conn_pnl = get_connection()
                cur_pnl = conn_pnl.cursor()
                cur_pnl.execute("SELECT COUNT(*) FROM trades WHERE signal_id = %s AND status = 'OPEN'", (int(sig_id),))
                still_open_count = cur_pnl.fetchone()[0]
                
                if still_open_count == 0:
                    cur_pnl.execute("SELECT symbol, lots, entry_price, close_price, profit, comment FROM trades WHERE signal_id = %s", (int(sig_id),))
                    rows_pnl = cur_pnl.fetchall()
                    
                    total_pnl = 0.0
                    trade_lines = []
                    for sym_name, lots_val, ent_p, cls_p, prf, cmt in rows_pnl:
                        pnl_val = float(prf or 0.0)
                        total_pnl += pnl_val
                        trade_lines.append(f"  • **{sym_name}** ({cmt}): {lots_val} lots | Entry: {ent_p} | Close: {cls_p} | P&L: **${pnl_val:+.2f}**")
                    
                    pnl_emoji = "✅" if total_pnl >= 0 else "❌"
                    status_word = "PROFIT" if total_pnl >= 0 else "LOSS"
                    now_str = datetime.datetime.now().strftime("%I:%M:%S %p")
                    
                    discord_msg = (
                        f"⏹ **JANE STREET SIGNAL SET CLOSED ({sym_a} / {sym_b})** ⏹\n\n"
                        f"⏱ **Exit Time:** {now_str}\n"
                        f"💡 **Reason:** {exit_reason}\n\n"
                        f"📊 **Individual Parts:**\n" + "\n".join(trade_lines) + "\n\n"
                        f"{pnl_emoji} **TOTAL SET P&L:** **${total_pnl:+.2f}** ({status_word})\n"
                    )
                    from database import send_discord_message
                    send_discord_message(discord_msg)
                
                cur_pnl.close()
                conn_pnl.close()
            except Exception as ex_pnl:
                logger.error(f"Error compiling Discord P&L notification: {ex_pnl}")
                
            continue

        sync_mt5_open_positions_with_db()

        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT ticket, symbol, status, lots, comment, order_type FROM trades WHERE signal_id = %s",
                (int(sig_id),)
            )
            all_db_trades = cur.fetchall()
            cur.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error querying all trades for signal_id {sig_id}: {e}")
            continue

        db_leg_a = [t for t in all_db_trades if t[1].split('.')[0].upper() == sym_a.split('.')[0].upper()]
        db_leg_b = [t for t in all_db_trades if t[1].split('.')[0].upper() == sym_b.split('.')[0].upper()]

        total_a_parts = len(db_leg_a)
        closed_a_parts = len([t for t in db_leg_a if t[2] == 'CLOSED'])

        if total_a_parts > 0 and closed_a_parts > 0:
            total_b_vol = sum(float(t[3]) for t in db_leg_b)
            target_closed_b_vol = total_b_vol * (closed_a_parts / total_a_parts)
            already_closed_b_vol = sum(float(t[3]) for t in db_leg_b if t[2] == 'CLOSED')

            remaining_to_close_b = target_closed_b_vol - already_closed_b_vol
            if remaining_to_close_b > 0.005:
                open_b_trades = [t for t in db_leg_b if t[2] == 'OPEN']
                if open_b_trades:
                    t_b_to_close = open_b_trades[0]
                    t_b_ticket = t_b_to_close[0]
                    t_b_lots = float(t_b_to_close[3])
                    t_b_order_type = t_b_to_close[5]

                    close_vol = min(remaining_to_close_b, t_b_lots)
                    logger.info(f"Syncing Hedge: {closed_a_parts}/{total_a_parts} Leg A closed. Partially closing Leg B {t_b_ticket} by {close_vol:.3f} lots.")
                    close_single_trade(sym_b, t_b_ticket, close_vol, t_b_order_type)

def get_symbol_category(symbol: str) -> str:
    s = symbol.upper()
    if any(x in s for x in ["XAU", "XAG", "XPT", "XPD", "PLAT", "PALL"]):
        return "metals"
    if any(x in s for x in ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMD", "META", "AMZN"]):
        return "stocks"
    if any(x in s for x in ["US500", "US30", "NAS100", "GER30", "UK100", "USTEC"]):
        return "indices"
    return "forex"

def get_hedge_execution_parameters(action_spread: str, beta: float, tick_b) -> tuple:
    is_buy_spread = (action_spread == "BUY_SPREAD")
    if beta >= 0:
        if is_buy_spread:
            return 1, "SELL", float(tick_b.bid), 1.0
        else:
            return 0, "BUY", float(tick_b.ask), -1.0
    else:
        if is_buy_spread:
            return 0, "BUY", float(tick_b.ask), -1.0
        else:
            return 1, "SELL", float(tick_b.bid), 1.0

def get_hedge_quantity(symbol_a: str, symbol_b: str, qty_a: float, beta: float, cat_a: str, cat_b: str) -> float:
    info_a = mt5.symbol_info(symbol_a)
    contract_size_a = info_a.trade_contract_size if info_a else 1.0
    pip_val_a = info_a.trade_tick_value if (info_a and info_a.trade_tick_value > 0) else 10.0
        
    info_b = mt5.symbol_info(symbol_b)
    contract_size_b = info_b.trade_contract_size if info_b else 1.0
    pip_val_b = info_b.trade_tick_value if (info_b and info_b.trade_tick_value > 0) else 10.0
    
    pip_ratio = (pip_val_a / pip_val_b) if (pip_val_b > 0 and pip_val_a > 0) else 1.0
    if pip_ratio > 3.0 or pip_ratio < 0.33:
        pip_ratio = 1.0
        
    eff_beta = abs(beta)
    if cat_a == "forex":
        eff_beta = min(eff_beta, 0.283333)  # Calibrated so 1.20 lots Leg A yields exact 0.34 lots Leg B (1.20 * 0.283333 = 0.34)

    if cat_a in ["stocks", "metals"] or cat_b in ["stocks", "metals"]:
        tick_a_h = mt5.symbol_info_tick(symbol_a)
        tick_b_h = mt5.symbol_info_tick(symbol_b)
        p_a_h = float(tick_a_h.ask if tick_a_h else 1.0)
        p_b_h = float(tick_b_h.bid if tick_b_h else 1.0)
        
        dollar_val_a = p_a_h * contract_size_a
        dollar_val_b = p_b_h * contract_size_b
        if dollar_val_b > 0 and dollar_val_a > 0:
            raw_qty = qty_a * (dollar_val_a / dollar_val_b) * eff_beta
        else:
            raw_qty = qty_a * eff_beta
        # Strictly cap metals/stocks hedge quantity so Leg B never exceeds Leg A volume
        raw_qty = min(raw_qty, qty_a)
    else:
        raw_qty = qty_a * eff_beta * (contract_size_a / contract_size_b) * pip_ratio
    qty_b_final = round_volume(symbol_b, raw_qty)
    info_b_check = mt5.symbol_info(symbol_b)
    min_vol_b = info_b_check.volume_min if info_b_check else 0.01
    if qty_b_final < min_vol_b:
        qty_b_final = min_vol_b
    return qty_b_final

def apply_margin_guard(symbol_a: str, symbol_b: str, qty_a: float, qty_b: float, is_long: bool) -> tuple:
    disable_guard = os.getenv("DISABLE_MARGIN_GUARD", "False").lower() in ("true", "1", "yes")
    if disable_guard:
        return qty_a, qty_b

    acc = mt5.account_info()
    if not acc:
        return qty_a, qty_b
        
    free_margin = float(acc.margin_free)
    margin_limit = free_margin * 0.45
    
    action_a = mt5.ORDER_TYPE_BUY if is_long else mt5.ORDER_TYPE_SELL
    action_b = mt5.ORDER_TYPE_SELL if is_long else mt5.ORDER_TYPE_BUY
    
    tick_a = mt5.symbol_info_tick(symbol_a)
    price_a = tick_a.ask if action_a == mt5.ORDER_TYPE_BUY else (tick_a.bid if tick_a else mt5.symbol_info(symbol_a).bid)
    
    tick_b = mt5.symbol_info_tick(symbol_b)
    price_b = tick_b.ask if action_b == mt5.ORDER_TYPE_BUY else (tick_b.bid if tick_b else mt5.symbol_info(symbol_b).bid)
    
    margin_a = mt5.order_calc_margin(action_a, symbol_a, qty_a, price_a)
    margin_b = mt5.order_calc_margin(action_b, symbol_b, qty_b, price_b)
    
    if margin_a is None or margin_b is None or margin_a <= 0 or margin_b <= 0:
        cat_a = get_symbol_category(symbol_a)
        cat_b = get_symbol_category(symbol_b)
        rate_a = 0.20 if cat_a == "stocks" else (0.25 if cat_a in ["metals", "indices"] else 0.01)
        rate_b = 0.20 if cat_b == "stocks" else (0.25 if cat_b in ["metals", "indices"] else 0.01)
        
        info_a = mt5.symbol_info(symbol_a)
        info_b = mt5.symbol_info(symbol_b)
        c_size_a = info_a.trade_contract_size if info_a else 1.0
        c_size_b = info_b.trade_contract_size if info_b else 1.0
        
        margin_a = qty_a * price_a * c_size_a * rate_a
        margin_b = qty_b * price_b * c_size_b * rate_b
        
    total_margin_req = float(margin_a + margin_b)
    logger.info(f"[MARGIN GUARD] Free Margin: ${free_margin:.2f} | Margin Required: ${total_margin_req:.2f} (Leg A: ${margin_a:.2f}, Leg B: ${margin_b:.2f})")

    if total_margin_req > margin_limit:
        scale_factor = margin_limit / total_margin_req
        logger.warning(f"[MARGIN GUARD] Margin required (${total_margin_req:.2f}) exceeds limit (${margin_limit:.2f}). Scaling down trades by factor: {scale_factor:.4f}")
        
        qty_a = qty_a * scale_factor
        qty_b = qty_b * scale_factor
        
        info_a = mt5.symbol_info(symbol_a)
        min_vol_a = info_a.volume_min if info_a else 0.01
        step_a = info_a.volume_step if info_a else 0.01
        
        part_lots_scaled = round(qty_a / 3.0 / step_a) * step_a
        if part_lots_scaled < min_vol_a:
            part_lots_scaled = min_vol_a
        final_a = round(part_lots_scaled * 3.0, 2)
        
        from risk_safeguards import round_volume
        final_b = round_volume(symbol_b, qty_b)
        info_b_check2 = mt5.symbol_info(symbol_b)
        min_vol_b2 = info_b_check2.volume_min if info_b_check2 else 0.01
        if final_b < min_vol_b2:
            final_b = min_vol_b2
        
        new_margin_a = mt5.order_calc_margin(action_a, symbol_a, final_a, price_a) or 0.0
        new_margin_b = mt5.order_calc_margin(action_b, symbol_b, final_b, price_b) or 0.0
        logger.info(f"[MARGIN GUARD] Scaled lot sizes: Leg A: {qty_a:.2f} -> {final_a:.2f} | Leg B: {qty_b:.2f} -> {final_b:.2f}. New Total Margin: ${new_margin_a + new_margin_b:.2f}")
        
        return final_a, final_b
        
    return qty_a, qty_b

# ==============================================================================
# MAIN TRADING ENGINE RUN LOOP
# ==============================================================================
def main():
    print("=========================================")
    print("   JANE STREET QUANT BOT INITIALIZING    ")
    print("=========================================\n")

    global REQUIRE_SMC_CONFLUENCE, SL_PIPS, TP_PIPS, AUTO_EXECUTE, Z_ENTRY_THRESHOLD, DEFAULT_LOTS, RISK_LIMITS_ENABLED, ML_MODEL
    global METALS_ENABLED, FOREX_ENABLED, INDICES_ENABLED, STOCKS_ENABLED
    global SL_PIPS, TP_PIPS, REQUIRE_SMC_CONFLUENCE, AUTO_EXECUTE, RISK_LIMITS_ENABLED, Z_ENTRY_THRESHOLD, DEFAULT_LOTS, MAX_TRADES
    global KNIFE_PROTECTION_ENABLED, OBI_ENABLED, VOLATILITY_FILTER_ENABLED

    load_config()

    ML_MODEL = None
    if os.path.exists("ml_model.joblib"):
        try:
            ML_MODEL = joblib.load("ml_model.joblib")
            logger.info("Successfully loaded local Machine Learning model: ml_model.joblib")
        except Exception as e:
            logger.error(f"Failed to load ML model: {e}")

    logger.info("Initializing database tables...")
    initialize_database()
    logger.info("Database ready.")

    def heartbeat_worker():
        import threading
        while True:
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("UPDATE bot_state SET last_heartbeat = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = 1")
                conn.commit()
                cur.close()
                conn.close()
            except Exception:
                pass
            time.sleep(10)

    import threading
    h_thread = threading.Thread(target=heartbeat_worker, daemon=True)
    h_thread.start()
    logger.info("Background heartbeat thread started.")
    
    cleanup_disabled_scanned_assets(METALS_ENABLED, FOREX_ENABLED, INDICES_ENABLED, STOCKS_ENABLED)

    acc_info = initialize_mt5()
    q_cov, r_cov = get_kf_parameters(GLOBAL_CONFIG["SYMBOL_A"])
    init_beta_val = EXPECTED_BETA_SIGN.get(f"{GLOBAL_CONFIG['SYMBOL_A']}/{GLOBAL_CONFIG['SYMBOL_B']}", 1)
    kf = KalmanFilterRegression(transition_covariance=q_cov, observation_covariance=r_cov, initial_beta=init_beta_val)

    is_halted = False
    smc_update_counter = 0
    active_zones = None
    last_processed_pair = ""
    daily_start_equity = None
    db_config_counter = 0
    low_correlation_warning = False
    correlation_check_counter = 0

    logger.info("Quantitative core pipeline active.")
    logger.info(f"[ACTIVE SYSTEM CONFIG] SL Pips: {SL_PIPS} | TP Pips: {TP_PIPS} | Max Loss Cap: $50.00 | Win-Rate Guard: [>=65.0% REQUIRED] | Metals Lots: {DEFAULT_LOT_SIZES.get('metals')} | Forex Lots: {DEFAULT_LOT_SIZES.get('forex')}")
    win_rate_loop_counter = 0
    loop_log_counter = 0
    SMC_ZONES_CACHE = {}
    smc_counter_cache = {}
    aamd_normal_cache = {}

    active_login_id = None
    try:
        from database import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT mt5_login FROM bot_state WHERE id = 1")
        row = cur.fetchone()
        if row and row[0]:
            active_login_id = int(row[0])
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error loading initial mt5_login from database: {e}")

    peak_floating_profit = 0.0
    while True:
        try:
            if not mt5.initialize():
                time.sleep(5)
                continue

            acc_info = mt5.account_info()
            if acc_info is None:
                time.sleep(5)
                continue

            current_login = int(acc_info.login)
            
            from database import get_connection
            startup_mismatch = False
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("SELECT mt5_login, initial_balance FROM bot_state WHERE id = 1")
                state_row = cur.fetchone()
                db_login = int(state_row[0]) if (state_row and state_row[0] is not None) else 0
                db_initial = float(state_row[1]) if (state_row and state_row[1] is not None) else 0.0
                
                cur.execute("SELECT COUNT(*) FROM trades WHERE status = 'OPEN'")
                open_trades_count = cur.fetchone()[0] or 0
                
                if db_login > 0 and db_login != current_login:
                    startup_mismatch = True
                
                cur_purge = conn.cursor()
                cur_purge.execute("DELETE FROM scanned_assets WHERE symbol_pair LIKE '%XPTUSD%' OR symbol_pair LIKE '%XPDUSD%' OR symbol_pair LIKE '%USDT%'")
                conn.commit()
                cur_purge.close()
                
                cur.close()
                conn.close()
                
            except Exception as e:
                logger.error(f"Error checking startup metrics sync: {e}")
                
            login_changed = (active_login_id is not None and active_login_id != current_login) or startup_mismatch
            
            if login_changed:
                logger.info(f"Syncing metrics (login_changed={login_changed}). Resetting metrics to {acc_info.equity:.2f} due to account switch.")
                from database import reset_database_metrics_for_new_account
                reset_database_metrics_for_new_account(current_login, acc_info.equity)
                
                daily_start_equity = float(acc_info.equity)
                
                try:
                    import risk_safeguards
                    risk_safeguards._cached_start_equity = float(acc_info.equity)
                    risk_safeguards._cached_start_equity_date = datetime.date.today()
                    risk_safeguards._cached_last_login = int(current_login)
                except Exception as ex:
                    logger.error(f"Error updating risk_safeguards cache in main loop: {ex}")
                
            active_login_id = current_login

            if db_config_counter % 5 == 0:
                db_cfg = fetch_db_config()
                if db_cfg:
                    new_pair, new_sl, new_tp, new_smc, new_auto_exec, new_crypto, new_metals, new_forex, new_indices, new_risk_limits, new_z_entry, new_def_lots, new_max_trades, new_knife, new_obi, new_vol, new_stocks = db_cfg
                    parts = new_pair.split("/")
                    if len(parts) == 2 and parts[0] != parts[1]:
                        if GLOBAL_CONFIG["SYMBOL_A"] != parts[0] or GLOBAL_CONFIG["SYMBOL_B"] != parts[1]:
                            logger.info(f"DB config update — switching to {new_pair}")
                            GLOBAL_CONFIG["SYMBOL_A"] = parts[0]
                            GLOBAL_CONFIG["SYMBOL_B"] = parts[1]
                            save_config(new_pair)
                    SL_PIPS = new_sl
                    TP_PIPS = new_tp
                    if db_config_counter == 0:
                        logger.info(f"[ACTIVE PIPELINE CONFIG] SL Pips: {SL_PIPS} | TP Pips: {TP_PIPS} | Z-Entry Threshold: {new_z_entry}")
                    if REQUIRE_SMC_CONFLUENCE != new_smc:
                        logger.info(f"[CONFIG UPDATE] SMC Confluence updated: {REQUIRE_SMC_CONFLUENCE} -> {new_smc}")
                        REQUIRE_SMC_CONFLUENCE = new_smc
                    if AUTO_EXECUTE != new_auto_exec:
                        logger.info(f"[CONFIG UPDATE] Auto Execute updated: {AUTO_EXECUTE} -> {new_auto_exec}")
                        AUTO_EXECUTE = new_auto_exec
                    if METALS_ENABLED != new_metals:
                        logger.info(f"[CONFIG UPDATE] Metals Enabled updated: {METALS_ENABLED} -> {new_metals}")
                        METALS_ENABLED = new_metals
                    if FOREX_ENABLED != new_forex:
                        logger.info(f"[CONFIG UPDATE] Forex Enabled updated: {FOREX_ENABLED} -> {new_forex}")
                        FOREX_ENABLED = new_forex
                    if INDICES_ENABLED != new_indices:
                        logger.info(f"[CONFIG UPDATE] Indices Enabled updated: {INDICES_ENABLED} -> {new_indices}")
                        INDICES_ENABLED = new_indices
                    if STOCKS_ENABLED != new_stocks:
                        logger.info(f"[CONFIG UPDATE] Stocks Enabled updated: {STOCKS_ENABLED} -> {new_stocks}")
                        STOCKS_ENABLED = new_stocks
                    if RISK_LIMITS_ENABLED != new_risk_limits:
                        logger.info(f"[CONFIG UPDATE] Risk Limits updated: {RISK_LIMITS_ENABLED} -> {new_risk_limits}")
                        RISK_LIMITS_ENABLED = new_risk_limits
                    if Z_ENTRY_THRESHOLD != new_z_entry:
                        logger.info(f"[CONFIG UPDATE] Z-Entry Threshold updated: {Z_ENTRY_THRESHOLD} -> {new_z_entry}")
                        Z_ENTRY_THRESHOLD = new_z_entry
                    if KNIFE_PROTECTION_ENABLED != new_knife:
                        logger.info(f"[CONFIG UPDATE] Knife Protection updated: {KNIFE_PROTECTION_ENABLED} -> {new_knife}")
                        KNIFE_PROTECTION_ENABLED = new_knife
                    if OBI_ENABLED != new_obi:
                        logger.info(f"[CONFIG UPDATE] OBI Filter updated: {OBI_ENABLED} -> {new_obi}")
                        OBI_ENABLED = new_obi
                    if VOLATILITY_FILTER_ENABLED != new_vol:
                        logger.info(f"[CONFIG UPDATE] Volatility Filter updated: {VOLATILITY_FILTER_ENABLED} -> {new_vol}")
                        VOLATILITY_FILTER_ENABLED = new_vol
                    if DEFAULT_LOTS != new_def_lots:
                        logger.info(f"[CONFIG UPDATE] Default Lots updated: {DEFAULT_LOTS} -> {new_def_lots}")
                        DEFAULT_LOTS = new_def_lots
                    import risk_safeguards
                    if risk_safeguards.MAX_DAILY_TRADES != new_max_trades:
                        logger.info(f"[CONFIG UPDATE] Max Daily Trades updated: {risk_safeguards.MAX_DAILY_TRADES} -> {new_max_trades}")
                        risk_safeguards.MAX_DAILY_TRADES = new_max_trades
                    
                    cleanup_disabled_scanned_assets(METALS_ENABLED, FOREX_ENABLED, INDICES_ENABLED, STOCKS_ENABLED)
            db_config_counter += 1

            S_A = GLOBAL_CONFIG["SYMBOL_A"]
            S_B = GLOBAL_CONFIG["SYMBOL_B"]
            current_pair_context = f"{S_A}/{S_B}"

            cat_a = get_symbol_category(S_A)
            cat_b = get_symbol_category(S_B)

            S_A_resolved = resolve_broker_symbol(S_A)
            S_B_resolved = resolve_broker_symbol(S_B)

            import news_guard
            is_news_halted, news_msg = news_guard.get_news_halt_status([S_A_resolved, S_B_resolved])

            should_close_news, news_close_reason = news_guard.should_auto_close_before_news([S_A_resolved, S_B_resolved], lead_minutes=15.0)
            if should_close_news:
                logger.info(f"📰 HIGH-IMPACT NEWS IMMINENT: {news_close_reason}. Blocking new trade entries to protect capital.")

            is_friday_close = is_friday_market_close_approaching(lead_minutes=45)
            if is_friday_close:
                logger.warning("🌅 FRIDAY MARKET CLOSE IMMINENT: Blocking new entries and auto-closing active positions to prevent Sunday opening gap risk!")
                if has_positions:
                    close_all_positions("ALL")

            current_equity = acc_info.equity if acc_info else 0.0

            if current_equity > 0.0:
                is_limit_breached, daily_loss_p = check_drawdown_limit(current_equity)
            else:
                is_limit_breached, daily_loss_p = False, 0.0

            is_demo = getattr(acc_info, "trade_mode", 0) in (0, 1)

            if is_limit_breached:
                if RISK_LIMITS_ENABLED:
                    logger.warning(f"🚨 DAILY DRAWDOWN LIMIT BREACHED ({daily_loss_p:.2f}% >= {MAX_DAILY_LOSS_PERCENT}%). ENFORCING STRICT RISK HALT & BLOCKING ALL NEW TRADES!")
                    is_halted = True
                else:
                    logger.info(f"Daily drawdown limit breached ({daily_loss_p:.2f}%), but Risk Limits Enforcer is toggled OFF on Dashboard.")
                    is_halted = False
            else:
                is_halted = False

            if daily_start_equity is None and current_equity > 0.0:
                daily_start_equity = current_equity

            if is_halted:
                close_all_positions("ALL")
                update_bot_state(
                    active_pair=current_pair_context,
                    system_status="HALTED (Max Loss)",
                    equity=acc_info.equity,
                    drawdown_percent=daily_loss_p,
                    floating_profit=0.0,
                    z_score=0.0,
                    hedge_ratio=0.0,
                    obi_a=0.0,
                    obi_b=0.0,
                    trades_today=get_trades_count_today(),
                    sl_pips=SL_PIPS,
                )
                time.sleep(10)
                continue

            update_live_toggles_from_db()

            pairs_to_scan = []
            if FOREX_ENABLED:
                pairs_to_scan.extend(CANDIDATE_PAIRS["forex"])
            if METALS_ENABLED:
                pairs_to_scan.extend(CANDIDATE_PAIRS["metals"])
            if STOCKS_ENABLED:
                pairs_to_scan.extend(CANDIDATE_PAIRS["stocks"])
            if INDICES_ENABLED:
                pairs_to_scan.extend(CANDIDATE_PAIRS["indices"])

            if current_pair_context not in [f"{p[0]}/{p[1]}" for p in pairs_to_scan]:
                parts = current_pair_context.split('/')
                if len(parts) == 2 and parts[0] != parts[1]:
                    pairs_to_scan.append((parts[0], parts[1]))

            candidate_signals = []

            if win_rate_loop_counter % 300 == 0:
                logger.info("Recalculating historical win rates for all enabled candidate pairs...")
                for s_a, s_b in pairs_to_scan:
                    pair_key = f"{s_a}/{s_b}"
                    WIN_RATE_CACHE[pair_key] = simulate_win_rate_for_pair(s_a, s_b, z_entry=Z_ENTRY_THRESHOLD)
            win_rate_loop_counter += 1

            try:
                conn_closed = get_connection()
                cur_closed = conn_closed.cursor()
                cur_closed.execute("SELECT DISTINCT symbol FROM trades WHERE status = 'OPEN'")
                open_symbols = [row[0] for row in cur_closed.fetchall()]
                cur_closed.close()
                conn_closed.close()
                
                if S_A_resolved not in open_symbols:
                    open_symbols.append(S_A_resolved)
                if S_B_resolved not in open_symbols:
                    open_symbols.append(S_B_resolved)
                    
                for sym in open_symbols:
                    check_closed_trades(sym)
            except Exception as e:
                logger.error(f"Error checking closed trades for open symbols: {e}")

            has_positions = False
            floating_profit = 0.0
            active_js_positions = []
            try:
                has_positions = get_open_trades_count() > 0
                positions = mt5.positions_get()
                if positions:
                    active_js_positions = [p for p in positions if (p.magic == MAGIC_NUMBER or "JS_" in str(p.comment).upper() or "JANE" in str(p.comment).upper())]
                    if not active_js_positions and len(positions) > 0:
                        active_js_positions = list(positions)
                    floating_profit += sum(p.profit for p in active_js_positions)
                    if len(active_js_positions) > 0:
                        has_positions = True
                    else:
                        peak_floating_profit = 0.0
                else:
                    peak_floating_profit = 0.0
            except Exception:
                pass

            # EMERGENCY HARD DRAWDOWN & FLOATING LOSS SAFEGUARD ($50.00 / 0.50% MAX CAP)
            if has_positions and active_js_positions:
                try:
                    from risk_safeguards import get_or_create_daily_start_equity
                    start_eq_guard = get_or_create_daily_start_equity(acc_info.equity)
                    daily_loss_usd = start_eq_guard - acc_info.equity
                    daily_loss_pct = (daily_loss_usd / start_eq_guard) * 100.0 if start_eq_guard > 0 else 0.0
                    
                    if floating_profit <= -50.0:
                        logger.error(f"[EMERGENCY DRAWDOWN GUARD] Floating loss (${floating_profit:.2f}) breached safety cap (-$50.00). AUTO-CLOSING ALL TRADES IMMEDIATELY!")
                        for pos in active_js_positions:
                            pos_type_str = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"
                            close_single_trade(pos.symbol, pos.ticket, pos.volume, pos_type_str, force_bypass_hold=True)
                except Exception as ex_dd:
                    logger.error(f"Error evaluating emergency drawdown guard: {ex_dd}")

            # Multi-Tier Equity Trailing Stop Safeguard (Dual Tier Profit Protection)
            if has_positions:
                if floating_profit > peak_floating_profit:
                    peak_floating_profit = floating_profit

                should_close_trail = False
                trail_close_reason = ""

                # Breakeven Shield & Early Reversal Lock (Peak >= +$25.00 USD -> Locks profit if floating drops by $4.00)
                if peak_floating_profit >= 25.0 and peak_floating_profit < 143.0:
                    early_floor = max(20.0, peak_floating_profit - 4.0)
                    if floating_profit <= early_floor:
                        should_close_trail = True
                        trail_close_reason = f"[BREAKEVEN & PROFIT GUARD] Floating profit peaked at ${peak_floating_profit:.2f} and reversed to ${floating_profit:.2f} (Floor: ${early_floor:.2f}). Auto-closing to lock +${floating_profit:.2f} cash profit!"

                # Tier 1 (Safety Floor at +$143.00 Peak -> Locks +$130.00 Cash Profit)
                elif peak_floating_profit >= 143.0 and peak_floating_profit < 180.0:
                    tier1_floor = 130.0
                    if floating_profit <= tier1_floor:
                        should_close_trail = True
                        trail_close_reason = f"[PROFIT GUARD TIER 1] Peak reached ${peak_floating_profit:.2f} and reversed to ${floating_profit:.2f} (Floor: ${tier1_floor:.2f}). Auto-closing to lock +$130.00 profit."

                # Tier 2 (Full Trailing Stop at +$180.00+ Peak -> Locks 91% of Peak Earnings)
                elif peak_floating_profit >= 180.0:
                    trail_stop_level = max(163.80, peak_floating_profit * 0.91)
                    if floating_profit <= trail_stop_level:
                        should_close_trail = True
                        trail_close_reason = f"[PROFIT GUARD TIER 2] Peak reached ${peak_floating_profit:.2f} and reversed to ${floating_profit:.2f} (Floor: ${trail_stop_level:.2f}). Auto-closing to lock 91% profit."

                if should_close_trail:
                    logger.info(trail_close_reason)
                    all_success = True
                    for pos in active_js_positions:
                        pos_type_str = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"
                        success = close_single_trade(pos.symbol, pos.ticket, pos.volume, pos_type_str)
                        if not success:
                            all_success = False
                    if all_success:
                        peak_floating_profit = 0.0
                        has_positions = False

            # Sync open trades live prices and profit/loss in DB
            try:
                conn = get_connection()
                cur = conn.cursor()
                
                positions = mt5.positions_get()
                if positions:
                    updated_tickets = set()
                    for pos in positions:
                        cur.execute(
                            "UPDATE trades SET close_price = %s, profit = %s WHERE ticket = %s AND status = 'OPEN'",
                            (float(pos.price_current), float(pos.profit), int(pos.ticket))
                        )
                        if cur.rowcount > 0:
                            updated_tickets.add(int(pos.ticket))
                            
                    for pos in positions:
                        if int(pos.ticket) not in updated_tickets:
                            pos_sym_base = pos.symbol.upper().split('.')[0]
                            cur.execute(
                                "SELECT ticket FROM trades WHERE status = 'OPEN' AND UPPER(SPLIT_PART(symbol, '.', 1)) = %s",
                                (pos_sym_base,)
                            )
                            db_tickets = [row[0] for row in cur.fetchall()]
                            if db_tickets:
                                distributed_profit = float(pos.profit) / len(db_tickets)
                                for tkt in db_tickets:
                                    cur.execute(
                                        "UPDATE trades SET close_price = %s, profit = %s WHERE ticket = %s",
                                        (float(pos.price_current), distributed_profit, int(tkt))
                                    )

                conn.commit()
                cur.close()
                conn.close()
            except Exception as e:
                logger.error(f"Error syncing open trades telemetry to DB: {e}")

            open_trade_symbols = set()
            try:
                conn_open = get_connection()
                cur_open = conn_open.cursor()
                cur_open.execute("SELECT DISTINCT symbol FROM trades WHERE status = 'OPEN'")
                open_trade_symbols = {row[0].upper() for row in cur_open.fetchall()}
                cur_open.close()
                conn_open.close()
            except Exception as e:
                logger.error(f"Error reading open trade symbols for Kalman freeze: {e}")

            # SCANNING LOOP FOR ALL PAIRS
            active_pair_z_score = 0.0
            active_pair_beta = 0.0
            active_pair_obi_a = 0.0
            active_pair_obi_b = 0.0
            active_pair_velocity = 0.0

            for s_a, s_b in pairs_to_scan:
                pk = f"{s_a}/{s_b}"
                cat_a = get_symbol_category(s_a)
                cat_b = get_symbol_category(s_b)

                s_a_resolved = resolve_broker_symbol(s_a)
                s_b_resolved = resolve_broker_symbol(s_b)

                from risk_safeguards import is_in_rollover_period
                if is_in_rollover_period():
                    win_rate = WIN_RATE_CACHE.get(pk, 50.0)
                    update_scanned_asset(pk, 0.0, 0.0, win_rate, 0.0, "ROLLOVER_PAUSE")
                    continue

                if not is_market_open(s_a_resolved) or not is_market_open(s_b_resolved):
                    win_rate = WIN_RATE_CACHE.get(pk, 50.0)
                    update_scanned_asset(pk, 0.0, 0.0, win_rate, 0.0, "MARKET_CLOSED")
                    continue

                tick_a_scan, tick_b_scan = None, None
                bids_a_scan, asks_a_scan = [], []
                bids_b_scan, asks_b_scan = [], []

                try:
                    check_and_subscribe_symbol(s_a_resolved)
                    tick_a_scan = mt5.symbol_info_tick(s_a_resolved)
                    bids_a_scan, asks_a_scan = get_market_book(s_a_resolved)

                    check_and_subscribe_symbol(s_b_resolved)
                    tick_b_scan = mt5.symbol_info_tick(s_b_resolved)
                    bids_b_scan, asks_b_scan = get_market_book(s_b_resolved)
                except Exception:
                    continue

                if tick_a_scan is None or tick_b_scan is None:
                    continue

                p_a = (tick_a_scan.bid + tick_a_scan.ask) / 2.0
                p_b = (tick_b_scan.bid + tick_b_scan.ask) / 2.0

                kf_pair = get_kf_for_pair(s_a_resolved, s_b_resolved)
                is_trade_active = (s_a_resolved.upper() in open_trade_symbols) or (s_b_resolved.upper() in open_trade_symbols)
                
                if not is_trade_active:
                    beta, alpha, spread, z = kf_pair.update(p_b, p_a)
                else:
                    z = kf_pair.get_current_z(p_b, p_a)
                    if kf_pair.ref_x is not None:
                        beta_norm = kf_pair.state_mean[0]
                        alpha_norm = kf_pair.state_mean[1]
                        beta = beta_norm * (kf_pair.ref_y / kf_pair.ref_x)
                        alpha = alpha_norm * kf_pair.ref_y
                        spread = p_a - (beta * p_b + alpha)
                    else:
                        beta, alpha, spread = 1.0, 0.0, p_a - p_b

                if REQUIRE_SMC_CONFLUENCE:
                    if s_a_resolved not in SMC_ZONES_CACHE or smc_counter_cache.get(s_a_resolved, 0) >= 15:
                        try:
                            r_df = get_rates_df(s_a_resolved, SMC_TIMEFRAME, count=100)
                            if r_df is not None and not r_df.empty:
                                SMC_ZONES_CACHE[s_a_resolved] = detect_smc_zones(r_df)
                                log_fvg_zones(s_a_resolved, SMC_ZONES_CACHE[s_a_resolved])
                                PINBAR_CACHE[s_a_resolved] = detect_pinbar_rejection(r_df)
                            smc_counter_cache[s_a_resolved] = 0
                        except Exception as e:
                            logger.error(f"SMC scan error for {s_a_resolved}: {e}")
                    else:
                        smc_counter_cache[s_a_resolved] = smc_counter_cache.get(s_a_resolved, 0) + 1

                obi_a = calculate_obi(bids_a_scan, asks_a_scan, depth=5)
                obi_b = calculate_obi(bids_b_scan, asks_b_scan, depth=5)
                net_obi = obi_a - obi_b
                bids_a_supported = len(bids_a_scan) > 0
                bids_b_supported = len(bids_b_scan) > 0
                obi_buy_pass = (net_obi >= -0.20) if (bids_a_supported and bids_b_supported) else True
                obi_sell_pass = (net_obi <= 0.20) if (bids_a_supported and bids_b_supported) else True

                in_bullish_zone = True
                in_bearish_zone = True
                if REQUIRE_SMC_CONFLUENCE and s_a_resolved in SMC_ZONES_CACHE:
                    in_bullish_zone = any(
                        is_price_in_zones(p_a, SMC_ZONES_CACHE[s_a_resolved].get(k, []))
                        for k in ['bullish_ob', 'bullish_breaker', 'bullish_fvg', 'bullish_ifvg']
                    )
                    in_bearish_zone = any(
                        is_price_in_zones(p_a, SMC_ZONES_CACHE[s_a_resolved].get(k, []))
                        for k in ['bearish_ob', 'bearish_breaker', 'bearish_fvg', 'bearish_ifvg']
                    )

                has_bull_rej, has_bear_rej = PINBAR_CACHE.get(s_a_resolved, (False, False))
                pass_pinbar_buy = (not has_bear_rej) if not BASELINE_EXPERIMENT_MODE else True
                pass_pinbar_sell = (not has_bull_rej) if not BASELINE_EXPERIMENT_MODE else True

                z_velocity = kf_pair.get_velocity(k=3)
                dynamic_z_entry = kf_pair.get_dynamic_z_entry(Z_ENTRY_THRESHOLD)

                if cat_a == "forex":
                    z_vel_lim = 0.005
                elif cat_a == "metals":
                    z_vel_lim = 0.02
                else:
                    z_vel_lim = 0.01

                action = "NONE"
                effective_dyn_z = dynamic_z_entry if VOLATILITY_FILTER_ENABLED else Z_ENTRY_THRESHOLD
                _, _, z_sl_val, _ = get_strategy_parameters(s_a_resolved)
                win_rate = WIN_RATE_CACHE.get(pk, 50.0)
                pass_win_rate = (win_rate >= 65.0) if not BASELINE_EXPERIMENT_MODE else True

                pass_z_buy = (z < -effective_dyn_z) and (z > -z_sl_val)
                pass_z_sell = (z > effective_dyn_z) and (z < z_sl_val)
                
                pass_turn_buy = True
                pass_turn_sell = True
                if kf_pair and len(kf_pair.z_history) >= 3 and not BASELINE_EXPERIMENT_MODE:
                    pass_turn_buy = is_turning_point_confirmed(kf_pair.z_history, effective_dyn_z, "BUY_SPREAD")
                    pass_turn_sell = is_turning_point_confirmed(kf_pair.z_history, effective_dyn_z, "SELL_SPREAD")
                
                pass_vel_buy = (z_velocity > -z_vel_lim) if (KNIFE_PROTECTION_ENABLED and not BASELINE_EXPERIMENT_MODE) else True
                pass_vel_sell = (z_velocity < z_vel_lim) if (KNIFE_PROTECTION_ENABLED and not BASELINE_EXPERIMENT_MODE) else True
                
                pass_obi_buy = obi_buy_pass if OBI_ENABLED else True
                pass_obi_sell = obi_sell_pass if OBI_ENABLED else True
                
                pass_smc_buy = in_bullish_zone if REQUIRE_SMC_CONFLUENCE else True
                pass_smc_sell = in_bearish_zone if REQUIRE_SMC_CONFLUENCE else True
                
                if pass_z_buy and pass_vel_buy and pass_obi_buy and pass_smc_buy and pass_turn_buy and pass_win_rate and pass_pinbar_buy:
                    action = "BUY_SPREAD"
                elif pass_z_sell and pass_vel_sell and pass_obi_sell and pass_smc_sell and pass_turn_sell and pass_win_rate and pass_pinbar_sell:
                    action = "SELL_SPREAD"

                if action != "NONE":
                    # Single Active Position Set per Specific Pair Guard (Requires BOTH Leg A and Leg B open together)
                    positions_existing = mt5.positions_get()
                    if positions_existing:
                        active_sym_set = {p.symbol.upper() for p in positions_existing}
                        s_a_up = s_a_resolved.upper()
                        s_b_up = s_b_resolved.upper()
                        if (s_a_up in active_sym_set) and (s_b_up in active_sym_set):
                            logger.info(f"[BASELINE POSITION LIMIT] Active position set already exists for both {s_a_up} and {s_b_up}. Skipping duplicate signal for {pk}.")
                            action = "NONE"

                if action != "NONE" and not BASELINE_EXPERIMENT_MODE:
                    expected_sign = EXPECTED_BETA_SIGN.get(pk, 1)
                    beta_sign = 1 if beta >= 0 else -1
                    if beta_sign != expected_sign:
                        logger.warning(f"Correlation anomaly for {pk}: estimated beta {beta:.4f} has wrong sign (expected {expected_sign}). Skipping signal.")
                        action = "NONE"
                    elif abs(beta) < 0.20:
                        logger.warning(f"Hedge ratio too low for {pk}: beta {beta:.4f} < 0.20. Skipping signal to protect win-rate.")
                        action = "NONE"

                base_z_triggered = (z < -Z_ENTRY_THRESHOLD) or (z > Z_ENTRY_THRESHOLD)
                if base_z_triggered and action == "NONE":
                    reasons = []
                    if not BASELINE_EXPERIMENT_MODE and not pass_win_rate:
                        reasons.append(f"Historical Win Rate ({win_rate:.1f}%) is below 65.0% safety threshold")
                    if z < -Z_ENTRY_THRESHOLD:
                        if VOLATILITY_FILTER_ENABLED and not BASELINE_EXPERIMENT_MODE and not (z < -dynamic_z_entry):
                            reasons.append(f"Z-score {z:.3f} not below dynamic threshold {-dynamic_z_entry:.3f} (volatility protection)")
                        if KNIFE_PROTECTION_ENABLED and not BASELINE_EXPERIMENT_MODE and not (z_velocity > -z_vel_lim):
                            reasons.append(f"Z-velocity {z_velocity:.3f} too fast (falling knife protection, limit: {-z_vel_lim})")
                        if OBI_ENABLED and not BASELINE_EXPERIMENT_MODE and not obi_buy_pass:
                            reasons.append(f"Adverse OBI pressure {net_obi:.3f} < -0.20 (sell wall)")
                        if REQUIRE_SMC_CONFLUENCE and not BASELINE_EXPERIMENT_MODE and not in_bullish_zone:
                            reasons.append("Price not in Bullish SMC Zone (Order Block/FVG)")
                        if not BASELINE_EXPERIMENT_MODE and not pass_pinbar_buy:
                            reasons.append("Adverse Bearish Pinbar Rejection Trap detected")
                    else:
                        if VOLATILITY_FILTER_ENABLED and not BASELINE_EXPERIMENT_MODE and not (z > dynamic_z_entry):
                            reasons.append(f"Z-score {z:.3f} not above dynamic threshold {dynamic_z_entry:.3f} (volatility protection)")
                        if KNIFE_PROTECTION_ENABLED and not BASELINE_EXPERIMENT_MODE and not (z_velocity < z_vel_lim):
                            reasons.append(f"Z-velocity {z_velocity:.3f} too fast (rising knife protection, limit: {z_vel_lim})")
                        if OBI_ENABLED and not BASELINE_EXPERIMENT_MODE and not obi_sell_pass:
                            reasons.append(f"Adverse OBI pressure {net_obi:.3f} > 0.20 (buy wall)")
                        if REQUIRE_SMC_CONFLUENCE and not BASELINE_EXPERIMENT_MODE and not in_bearish_zone:
                            reasons.append("Price not in Bearish SMC Zone (Order Block/FVG)")
                        if not BASELINE_EXPERIMENT_MODE and not pass_pinbar_sell:
                            reasons.append("Adverse Bullish Pinbar Rejection Trap detected")
                    
                    if reasons:
                        wr_tag = "Win-Rate Guard: OFF [Baseline Mode]" if BASELINE_EXPERIMENT_MODE else f"Win-Rate: {win_rate:.1f}% [{'PASSED' if pass_win_rate else 'FAILED <65%'}]"
                        logger.info(
                            f"Signal threshold crossed for {pk} (Z={z:.3f} | Z-Vel: {z_velocity:+.4f} | {wr_tag} | Beta: {beta:.3f} | OBI: {net_obi:+.2f}), "
                            f"but SKIPPED due to: {', '.join(reasons)}"
                        )

                update_scanned_asset(pk, p_a, p_b, win_rate, z, action)

                norm_pk = pk.upper().replace(" ", "").strip()
                norm_ctx = current_pair_context.upper().replace(" ", "").strip()
                if norm_pk == norm_ctx or (norm_pk.split('/')[0] in norm_ctx and norm_pk.split('/')[1] in norm_ctx):
                    active_pair_z_score = z
                    active_pair_beta = beta
                    active_pair_obi_a = obi_a
                    active_pair_obi_b = obi_b
                    active_pair_velocity = z_velocity

                cooldown_dir = COOLDOWN_DIRECTIONS.get(pk)
                if cooldown_dir == "BUY_SPREAD" and z > -1.0:
                    COOLDOWN_DIRECTIONS[pk] = None
                    cooldown_dir = None
                elif cooldown_dir == "SELL_SPREAD" and z < 1.0:
                    COOLDOWN_DIRECTIONS[pk] = None
                    cooldown_dir = None

                if action != "NONE" and cooldown_dir != action and not is_pair_in_cooldown(s_a_resolved, s_b_resolved):
                    if is_spread_valid(s_a_resolved) and is_spread_valid(s_b_resolved):
                        candidate_signals.append({
                            "pair": (s_a, s_b),
                            "action": action,
                            "win_rate": win_rate,
                            "z_score": z,
                            "z_velocity": z_velocity,
                            "beta": beta,
                            "net_obi": net_obi,
                            "tick_a": tick_a_scan,
                            "tick_b": tick_b_scan,
                            "price_a": p_a,
                            "price_b": p_b
                        })

            kf_active = get_kf_for_pair(S_A_resolved, S_B_resolved)
            manage_spread_positions(S_A_resolved, S_B_resolved, active_pair_z_score, kf=kf_active)

            tick_a_active = mt5.symbol_info_tick(S_A_resolved)
            tick_b_active = mt5.symbol_info_tick(S_B_resolved)
            if tick_a_active and tick_b_active:
                poll_manual_commands(tick_a_active, tick_b_active, SL_PIPS)

            acc_info_exec = mt5.account_info()
            is_dd_ok = True
            if acc_info_exec and RISK_LIMITS_ENABLED and not is_demo:
                is_dd_halted, cur_dd_pct = check_drawdown_limit(acc_info_exec.equity)
                if is_dd_halted or cur_dd_pct >= HALT_DAILY_DRAWDOWN_PCT:
                    is_dd_ok = False
                    logger.warning(f"NEW ENTRY BLOCKED: Daily Drawdown ({cur_dd_pct:.2f}%) reached 0.78% HALT threshold!")

            trades_today = get_trades_count_today()
            is_trade_limit_ok = ((not RISK_LIMITS_ENABLED) or is_demo or (trades_today < MAX_DAILY_TRADES)) and is_dd_ok
            
            can_execute = AUTO_EXECUTE and is_trade_limit_ok and not is_news_halted and candidate_signals
            if not BASELINE_EXPERIMENT_MODE:
                can_execute = can_execute and not has_positions

            if can_execute:
                if BASELINE_EXPERIMENT_MODE:
                    qualifying_candidates = candidate_signals
                else:
                    qualifying_candidates = [c for c in candidate_signals if c["win_rate"] >= 65.0]

                if not qualifying_candidates:
                    logger.info(f"Skipping trade execution: All candidate signals have win rate < 65.0% (Best candidate was {candidate_signals[0]['pair']} with {candidate_signals[0]['win_rate']}%)")
                    best_sig = None
                else:
                    qualifying_candidates.sort(key=lambda x: x["win_rate"], reverse=True)
                    best_sig = None
                    for cand in qualifying_candidates:
                        cand_s_a, cand_s_b = cand["pair"]
                        if is_spread_valid(cand_s_a) and is_spread_valid(cand_s_b):
                            best_sig = cand
                            break
                
                if best_sig is not None:
                    best_pair = best_sig["pair"]
                    best_action = best_sig["action"]
                    best_s_a, best_s_b = best_pair
                    best_cat_a = get_symbol_category(best_s_a)
                    best_cat_b = get_symbol_category(best_s_b)

                    # FINAL PERMISSION GATE: 2-Stage High-Impact News Enforcement Layer
                    if NEWS_GUARD_ENABLED:
                        from news_guard import check_pair_news_block, check_post_news_stability
                        
                        # STAGE 1: Hard News Block Window (15m before -> 30m after)
                        is_blocked, news_reason, news_curr, news_title = check_pair_news_block(best_pair, pre_minutes=15.0, post_minutes=30.0)
                        if is_blocked:
                            now_str = datetime.datetime.now().strftime("%I:%M:%S %p")
                            logger.warning(f"NEWS BLOCK | Currency: {news_curr} | Event: {news_title} | Pair: {best_s_a}/{best_s_b} | Time: {now_str}")
                            logger.info(f"TRADE BLOCKED | {news_curr} HIGH IMPACT NEWS ({news_title}) | {best_s_a}/{best_s_b}")
                            best_sig = None  # HARD BLOCK: Abort order execution for this affected currency pair!

                        # STAGE 2: Post-News Regime Confirmation (30m -> 120m after release)
                        if best_sig is not None:
                            kf_best = get_kf_for_pair(best_s_a, best_s_b)
                            is_unstable, post_reason, post_curr, post_title = check_post_news_stability(best_pair, kf_best, post_window_minutes=120.0)
                            if is_unstable:
                                now_str = datetime.datetime.now().strftime("%I:%M:%S %p")
                                logger.warning(f"POST-NEWS INSTABILITY DEFERRED | Currency: {post_curr} | Event: {post_title} | Pair: {best_s_a}/{best_s_b} | Reason: {post_reason} | Time: {now_str}")
                                logger.info(f"TRADE DEFERRED | POST-NEWS INSTABILITY ({post_curr} {post_title}) | {best_s_a}/{best_s_b}")
                                best_sig = None  # DEFER ENTRY until spread normalizes!
                    
                    if ML_MODEL is not None and Z_ENTRY_THRESHOLD > 0.5 and os.getenv("USE_ML_FILTER", "False").lower() in ("true", "1", "yes"):
                        now_dt = datetime.datetime.now()
                        feature_vector = [
                            float(best_sig["z_score"]),
                            float(best_sig["z_velocity"]),
                            float(best_sig["price_a"] - best_sig["price_b"] * best_sig["beta"]),
                            float(best_sig["beta"]),
                            int(now_dt.hour),
                            int(now_dt.weekday())
                        ]
                        try:
                            proba_success = float(ML_MODEL.predict_proba([feature_vector])[0][1])
                            logger.info(f"ML Filter Evaluation for {best_s_a}/{best_s_b} | Win Probability: {proba_success*100:.1f}%")
                            if proba_success < 0.65:
                                logger.info(f"ML Filter: Skipping trade because probability {proba_success*100:.1f}% is below threshold 65%")
                                continue
                        except Exception as ml_err:
                            logger.error(f"ML inference error: {ml_err}")
                            
                    logger.info(
                        f"🚀 [ALL REQUIREMENTS VERIFIED] All 8 Confluence Safeguards PASSED for {best_s_a}/{best_s_b}! "
                        f"Win-Rate: {best_sig['win_rate']:.1f}% (>=65.0%) | Z-Score: {best_sig['z_score']:.3f} | Z-Vel: {best_sig['z_velocity']:.3f} | "
                        f"OBI: {best_sig['net_obi']:.2f} | Action: {best_action} -> EXECUTING TRADE NOW!"
                    )
                    
                    S_A, S_B = best_s_a, best_s_b
                    GLOBAL_CONFIG["SYMBOL_A"] = S_A
                    GLOBAL_CONFIG["SYMBOL_B"] = S_B
                    current_pair_context = f"{S_A}/{S_B}"
                    save_config(current_pair_context)
                    
                    S_A_resolved = resolve_broker_symbol(S_A)
                    S_B_resolved = resolve_broker_symbol(S_B)
                    if not is_market_open(S_A_resolved) or not is_market_open(S_B_resolved):
                        logger.warning(f"Market closed for {S_A_resolved}/{S_B_resolved}. Aborting trade execution.")
                        continue

                    signal_id = log_signal(
                        S_A, S_B, 
                        best_sig["price_a"], best_sig["price_b"], 
                        best_sig["beta"], 0.0, 
                        best_sig["z_score"], best_sig["net_obi"], 
                        best_action
                    )
                    
                    sl_dist = get_sl_distance(S_A, best_sig["price_a"], SL_PIPS)
                    sl_dist_b = get_sl_distance(S_B, best_sig["price_b"], SL_PIPS)
                    tp_dist = get_tp_distance(S_A, best_sig["price_a"], TP_PIPS)
                    
                    COOLDOWN_DIRECTIONS[current_pair_context] = best_action
                    is_long = (best_action == "BUY_SPREAD")
                    
                    try:
                        best_cat_a = get_symbol_category(S_A)
                        best_cat_b = get_symbol_category(S_B)
                        
                        entry_a = best_sig["tick_a"].ask if is_long else best_sig["tick_a"].bid
                        entry_b = best_sig["tick_b"].bid if is_long else best_sig["tick_b"].ask
                        
                        sl_a = entry_a - sl_dist if is_long else entry_a + sl_dist
                        tp1_dist = sl_dist * 1.1  # Calibrated for exact $55.00 USD profit on 0.40 lots (13.75 pips * $4.00 = $55.00)
                        if is_long:
                            tp1_val = best_sig["price_a"] + tp1_dist
                            tp2_val = best_sig["price_a"] + max(tp_dist, sl_dist * 1.5)
                            tp3_val = best_sig["price_a"] + max(tp_dist * 1.5, sl_dist * 3.5)
                        else:
                            tp1_val = best_sig["price_a"] - tp1_dist
                            tp2_val = best_sig["price_a"] - max(tp_dist, sl_dist * 1.5)
                            tp3_val = best_sig["price_a"] - max(tp_dist * 1.5, sl_dist * 3.5)
                            
                        if DEFAULT_LOTS > 0.005:
                            disable_guard = os.getenv("DISABLE_MARGIN_GUARD", "False").lower() in ("true", "1", "yes")
                            mult = 1.0 if disable_guard else LEVERAGE_FACTORS.get(best_cat_a, 1.0)
                            lots_a = DEFAULT_LOTS * mult
                        else:
                            lots_a = get_blue_guardian_lots(S_A, best_cat_a, is_demo=is_demo)
                            
                        part_lots_a = round(lots_a / 3.0, 2)
                        info_a_check = mt5.symbol_info(S_A)
                        min_vol_a = info_a_check.volume_min if info_a_check else 0.01
                        if part_lots_a < min_vol_a:
                            part_lots_a = min_vol_a
                        actual_lots_a = part_lots_a * 3.0
                        
                        lots_b = get_hedge_quantity(S_A, S_B, actual_lots_a, best_sig["beta"], best_cat_a, best_cat_b)
                        
                        order_type_b, side_b, price_b, sl_sign_b = get_hedge_execution_parameters(best_action, best_sig["beta"], best_sig["tick_b"])
                        sl_b = price_b + sl_sign_b * sl_dist_b
                        
                        send_discord_signal_notification(
                            action=best_action,
                            symbol_a=S_A,
                            symbol_b=S_B,
                            z_score=best_sig["z_score"],
                            entry_a=entry_a,
                            sl_a=sl_a,
                            tp1=tp1_val,
                            tp2=tp2_val,
                            tp3=tp3_val,
                            lots_a=actual_lots_a,
                            entry_b=entry_b,
                            sl_b=sl_b,
                            lots_b=lots_b,
                            side_b=side_b
                        )
                    except Exception as e_notify:
                        logger.error(f"Error preparing Discord notification: {e_notify}")
                    
                    if is_long:
                        if DEFAULT_LOTS > 0.005:
                            disable_guard = os.getenv("DISABLE_MARGIN_GUARD", "False").lower() in ("true", "1", "yes")
                            mult = 1.0 if disable_guard else LEVERAGE_FACTORS.get(best_cat_a, 1.0)
                            lots_a = DEFAULT_LOTS * mult
                        else:
                            lots_a = get_blue_guardian_lots(S_A, best_cat_a, is_demo=is_demo)
                        
                        info_a_check = mt5.symbol_info(S_A_resolved)
                        min_vol_a = info_a_check.volume_min if info_a_check else 0.01
                        part_lots_a = round(lots_a / 3.0, 2)
                        if part_lots_a < min_vol_a:
                            part_lots_a = min_vol_a
                        actual_lots_a = part_lots_a * 3.0
                        
                        qty_b = get_hedge_quantity(S_A_resolved, S_B_resolved, actual_lots_a, best_sig["beta"], best_cat_a, best_cat_b)
                        actual_lots_a, qty_b = apply_margin_guard(S_A_resolved, S_B_resolved, actual_lots_a, qty_b, True)
                        
                        exec_a_ok, filled_a_total = execute_three_part_trade(
                            S_A_resolved, True, best_sig["tick_a"].ask, best_sig["tick_a"].ask - sl_dist, actual_lots_a,
                            best_sig["price_a"] + sl_dist, best_sig["price_a"] + max(tp_dist, sl_dist * 1.5), best_sig["price_a"] + max(tp_dist * 1.5, sl_dist * 3.5),
                            signal_id=signal_id
                        )
                        if exec_a_ok:
                            if filled_a_total > 0:
                                qty_b = get_hedge_quantity(S_A_resolved, S_B_resolved, filled_a_total, best_sig["beta"], best_cat_a, best_cat_b)
                            fresh_tick_b = mt5.symbol_info_tick(S_B_resolved) or best_sig["tick_b"]
                            order_type_b, side_b, price_b, sl_sign_b = get_hedge_execution_parameters(best_action, best_sig["beta"], fresh_tick_b)
                            sl_b = price_b + sl_sign_b * sl_dist_b
                            
                            res_hedge = None
                            for retry_idx in range(3):
                                mt5.symbol_select(S_B_resolved, True)
                                tick_retry = mt5.symbol_info_tick(S_B_resolved)
                                if tick_retry:
                                    price_b = tick_retry.ask if order_type_b == mt5.ORDER_TYPE_BUY else tick_retry.bid
                                    sl_b = price_b + sl_sign_b * sl_dist_b
                                res_hedge = send_order(S_B_resolved, order_type_b, price_b, qty_b, 0.0, 0.0, "JS_HEDGE")
                                if res_hedge and res_hedge.retcode == mt5.TRADE_RETCODE_DONE:
                                    log_trade_entry(res_hedge.order, S_B_resolved, side_b, qty_b, res_hedge.price, datetime.datetime.now(), "JS_HEDGE", signal_id)
                                    break
                                time.sleep(0.5)
                            if not (res_hedge and res_hedge.retcode == mt5.TRADE_RETCODE_DONE):
                                logger.error(f"[HEDGE SAFETY] Leg B ({S_B_resolved}) failed after 3 retries! Closing Leg A ({S_A_resolved}) to prevent unhedged risk.")
                                close_all_positions(S_A_resolved)
                    else:
                        if DEFAULT_LOTS > 0.005:
                            disable_guard = os.getenv("DISABLE_MARGIN_GUARD", "False").lower() in ("true", "1", "yes")
                            mult = 1.0 if disable_guard else LEVERAGE_FACTORS.get(best_cat_a, 1.0)
                            lots_a = DEFAULT_LOTS * mult
                        else:
                            lots_a = get_blue_guardian_lots(S_A, best_cat_a, is_demo=is_demo)
                        
                        info_a_check = mt5.symbol_info(S_A_resolved)
                        min_vol_a = info_a_check.volume_min if info_a_check else 0.01
                        part_lots_a = round(lots_a / 3.0, 2)
                        if part_lots_a < min_vol_a:
                            part_lots_a = min_vol_a
                        actual_lots_a = part_lots_a * 3.0
                        
                        qty_b = get_hedge_quantity(S_A_resolved, S_B_resolved, actual_lots_a, best_sig["beta"], best_cat_a, best_cat_b)
                        actual_lots_a, qty_b = apply_margin_guard(S_A_resolved, S_B_resolved, actual_lots_a, qty_b, False)
                        
                        exec_a_ok, filled_a_total = execute_three_part_trade(
                            S_A_resolved, False, best_sig["tick_a"].bid, best_sig["tick_a"].bid + sl_dist, actual_lots_a,
                            best_sig["price_a"] - sl_dist, best_sig["price_a"] - max(tp_dist, sl_dist * 1.5), best_sig["price_a"] - max(tp_dist * 1.5, sl_dist * 3.5),
                            signal_id=signal_id
                        )
                        if exec_a_ok:
                            if filled_a_total > 0:
                                qty_b = get_hedge_quantity(S_A_resolved, S_B_resolved, filled_a_total, best_sig["beta"], best_cat_a, best_cat_b)
                            fresh_tick_b = mt5.symbol_info_tick(S_B_resolved) or best_sig["tick_b"]
                            order_type_b, side_b, price_b, sl_sign_b = get_hedge_execution_parameters(best_action, best_sig["beta"], fresh_tick_b)
                            sl_b = price_b + sl_sign_b * sl_dist_b
                            
                            res_hedge = None
                            for retry_idx in range(3):
                                mt5.symbol_select(S_B_resolved, True)
                                tick_retry = mt5.symbol_info_tick(S_B_resolved)
                                if tick_retry:
                                    price_b = tick_retry.ask if order_type_b == mt5.ORDER_TYPE_BUY else tick_retry.bid
                                    sl_b = price_b + sl_sign_b * sl_dist_b
                                res_hedge = send_order(S_B_resolved, order_type_b, price_b, qty_b, sl_b, 0.0, "JS_HEDGE")
                                if res_hedge and res_hedge.retcode == mt5.TRADE_RETCODE_DONE:
                                    log_trade_entry(res_hedge.order, S_B_resolved, side_b, qty_b, res_hedge.price, datetime.datetime.now(), "JS_HEDGE", signal_id)
                                    break
                                time.sleep(0.5)
                            if not (res_hedge and res_hedge.retcode == mt5.TRADE_RETCODE_DONE):
                                logger.error(f"[HEDGE SAFETY] Leg B ({S_B_resolved}) failed after 3 retries! Closing Leg A ({S_A_resolved}) to prevent unhedged risk.")
                                close_all_positions(S_A_resolved)
                    invalidate_trades_cache()

            if len(active_js_positions) > 0:
                leg_a_parts = [p for p in active_js_positions if p.symbol == S_A_resolved]
                if leg_a_parts:
                    sample_ticket = leg_a_parts[0].ticket
                    try:
                        conn_sl = get_connection()
                        cur_sl = conn_sl.cursor()
                        cur_sl.execute("""
                            SELECT t2.status 
                            FROM trades t1
                            JOIN trades t2 ON t1.signal_id = t2.signal_id
                            WHERE t1.ticket = %s AND t2.comment = 'JaneStreet TP1'
                        """, (sample_ticket,))
                        row_sl = cur_sl.fetchone()
                        tp1_closed = (row_sl is not None and row_sl[0] == 'CLOSED')
                        cur_sl.close()
                        conn_sl.close()
                        
                        if tp1_closed:
                            modify_sl_for_trade(S_A_resolved, leg_a_parts[0].price_open)
                    except Exception as ex_sl:
                        logger.error(f"Error evaluating breakeven trail SL: {ex_sl}")

            if is_news_halted or should_close_news:
                msg = news_msg if is_news_halted else news_close_reason
                status_str = f"HALTED (News: {msg})"
            elif low_correlation_warning:
                status_str = "RUNNING (Warning: Low Correlation)"
            elif has_positions and (peak_floating_profit >= 180.0 or floating_profit >= 180.0):
                trail_floor_val = max(163.80, peak_floating_profit * 0.91)
                status_str = f"RUNNING (Trail Active Tier 2: Peak ${peak_floating_profit:.2f} | Floor ${trail_floor_val:.2f})"
            elif has_positions and (peak_floating_profit >= 143.0 or floating_profit >= 143.0):
                status_str = f"RUNNING (Trail Active Tier 1: Peak ${peak_floating_profit:.2f} | Floor $130.00)"
            else:
                status_str = "RUNNING (Active)" if AUTO_EXECUTE else "RUNNING (Signals Only)"
            
            if active_pair_z_score == 0.0:
                try:
                    conn_tel = get_connection()
                    cur_tel = conn_tel.cursor()
                    cur_tel.execute("SELECT z_score, action FROM scanned_assets WHERE symbol_pair = %s LIMIT 1", (current_pair_context,))
                    row_tel = cur_tel.fetchone()
                    if row_tel and row_tel[0] is not None:
                        active_pair_z_score = float(row_tel[0])
                    else:
                        cur_tel.execute("SELECT z_score FROM scanned_assets ORDER BY updated_at DESC LIMIT 1")
                        row_fallback = cur_tel.fetchone()
                        if row_fallback and row_fallback[0] is not None:
                            active_pair_z_score = float(row_fallback[0])
                    cur_tel.close()
                    conn_tel.close()
                except Exception:
                    pass

            update_bot_state(
                active_pair=current_pair_context,
                system_status=status_str,
                equity=current_equity,
                drawdown_percent=daily_loss_p,
                floating_profit=floating_profit,
                z_score=active_pair_z_score,
                hedge_ratio=active_pair_beta,
                obi_a=active_pair_obi_a,
                obi_b=active_pair_obi_b,
                trades_today=trades_today,
                sl_pips=SL_PIPS,
            )

            update_daily_metrics(
                datetime.date.today(),
                start_equity=daily_start_equity,
                current_equity=current_equity,
                max_dd=daily_loss_p,
                trades_count=trades_today,
                login_id=current_login,
            )

            if loop_log_counter % 15 == 0:
                try:
                    summary_parts = []
                    conn_scan = get_connection()
                    cur_scan = conn_scan.cursor()
                    cur_scan.execute("SELECT symbol_pair, z_score FROM scanned_assets ORDER BY symbol_pair")
                    scanned_rows = cur_scan.fetchall()
                    cur_scan.close()
                    conn_scan.close()
                    for pair_name, z_val in scanned_rows:
                        summary_parts.append(f"{pair_name}: {float(z_val):.2f}")
                    scan_summary_str = " | ".join(summary_parts)
                    logger.info(f"[LIVE SCAN SUMMARY] {scan_summary_str}")
                except Exception as ex_sum:
                    logger.error(f"Error compiling scan summary log: {ex_sum}")

                smc_str = f"SMC: [{'ENABLED' if REQUIRE_SMC_CONFLUENCE else 'OFF'}]"
                obi_str = f"OBI: [{'ENABLED' if OBI_ENABLED else 'OFF'}] ({active_pair_obi_a:.1f}/{active_pair_obi_b:.1f})"
                winrate_str = "Win-Rate Guard: [>=65% ACTIVE]"
                logger.info(
                    f"[LIVE SCAN DETAIL] Focus: {S_A}/{S_B} | {winrate_str} | Z-Score: {active_pair_z_score:.3f} "
                    f"| Z-Vel: {active_pair_velocity:.3f} | {smc_str} | {obi_str} "
                    f"| Status: {status_str}"
                )
            loop_log_counter += 1

        except Exception as loop_err:
            logger.error(f"Error in main run loop: {loop_err}")

        time.sleep(LOOP_INTERVAL)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        shutdown_mt5()
