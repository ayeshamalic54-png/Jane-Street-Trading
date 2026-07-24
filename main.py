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

from math_models import KalmanFilterRegression, calculate_obi, test_cointegration
from data_ingestion import initialize_mt5, check_and_subscribe_symbol, get_live_ticks, get_market_book, shutdown_mt5, get_rates_df, resolve_broker_symbol
from risk_safeguards import check_drawdown_limit, calculate_lots, is_spread_valid, get_trades_count_today, MAX_DAILY_TRADES, invalidate_trades_cache, round_volume
from execution_bot import execute_three_part_trade, close_all_positions, modify_sl_for_trade, check_closed_trades, MAGIC_NUMBER, send_order, close_position_by_ticket
from smc_indicators import detect_smc_zones, is_price_in_zones
from database import log_signal, get_connection, update_bot_state, update_daily_metrics, log_fvg_zones, get_auto_execute, initialize_database, log_trade_entry, get_open_trades_count, log_trade_exit, update_scanned_asset
from binance_execution import (
    get_binance_usdt_balance,
    calculate_binance_quantity,
    execute_three_part_binance_trade,
    close_all_binance_positions,
    check_closed_binance_trades,
    send_signed_request,
    get_binance_live_tick,
    get_binance_market_book,
    get_binance_rates_df,
    close_binance_partial,
    get_symbol_filters
)

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

# BUG FIX 1: Default to EURUSD/GBPUSD (was EURUSD/EURUSD causing z-score ~0)
GLOBAL_CONFIG = {
    "SYMBOL_A": "EURUSD",
    "SYMBOL_B": "GBPUSD"
}

# Cooldown dictionary to prevent continuous entries on stopped-out signals
COOLDOWN_DIRECTIONS = {}

KF_CACHE = {}
LAST_KF_UPDATE_BAR = {}
WIN_RATE_CACHE = {}

KNIFE_PROTECTION_ENABLED = True
OBI_ENABLED = True
VOLATILITY_FILTER_ENABLED = True

# Dashboard API base URL — update to your Replit URL when deployed
DASHBOARD_API_URL = os.environ.get("DASHBOARD_API_URL", "http://localhost:80/api")

def load_config():
    global GLOBAL_CONFIG
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                active_pair = data.get("active_pair", "EURUSD/GBPUSD")
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
    Reads active_pair, sl_pips, tp_pips, smc_enabled, and auto_execute directly from the postgres database
    to avoid HTTP dependency and connection issues.
    """
    query = """
        SELECT active_pair, sl_pips, tp_pips, smc_enabled, auto_execute,
               crypto_enabled, metals_enabled, forex_enabled, indices_enabled,
               risk_limits_enabled, z_entry_threshold, default_lots, max_trades,
               knife_protection_enabled, obi_enabled, volatility_filter_enabled
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
            active_pair = row[0] or "EURUSD/GBPUSD"
            parts = active_pair.split('/')
            is_crypto = False
            if len(parts) == 2:
                p0, p1 = parts[0].upper(), parts[1].upper()
                if p0.endswith("USDT") or p1.endswith("USDT") or any(x in p0 or x in p1 for x in ["BTC", "ETH", "SOL", "BNB", "AVAX", "XRP", "ADA", "DOGE", "MATIC", "LTC", "LINK", "DOT", "UNI", "SHIB"]):
                    is_crypto = True
            
            # If the database pair is crypto, override it to EURUSD/GBPUSD immediately
            if is_crypto:
                logger.info("Overriding database invalid active_pair config to EURUSD/GBPUSD")
                active_pair = "EURUSD/GBPUSD"
                cur.execute("UPDATE bot_state SET active_pair = %s, crypto_enabled = false WHERE id = 1", (active_pair,))
                conn.commit()
                
            cur.close()
            conn.close()
            return (
                active_pair,
                float(row[1] or 20.0),
                float(row[2] or 40.0),
                bool(row[3] if row[3] is not None else True),
                bool(row[4] if row[4] is not None else True),
                False, # Hardcoded crypto_enabled to False
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


def poll_manual_commands(tick_a, tick_b, sl_pips: float):
    """
    Checks for pending manual trade commands directly from the database table trade_commands
    and executes them via MT5/Binance. Acks each command back directly via SQL update.
    """
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
                elif cat == "crypto":
                    tick = get_binance_live_tick(symbol)
                    if tick is None:
                        raise RuntimeError(f"No tick data for crypto {symbol}")
                    price = tick.ask if is_long else tick.bid
                    sl_dist = get_sl_distance(symbol, price, cmd_sl)
                    tp_dist = float(price * (cmd_tp / 100.0))
                    
                    if is_long:
                        sl_price = price - sl_dist
                        tp1 = price + sl_dist
                        tp2 = price + tp_dist
                        tp3 = price + sl_dist * 3.5
                    else:
                        sl_price = price + sl_dist
                        tp1 = price - sl_dist
                        tp2 = price - tp_dist
                        tp3 = price - sl_dist * 3.5
                        
                    risk_pct = lots * 100.0 if lots <= 1.0 else lots
                    usdt_bal, _ = get_binance_usdt_balance()
                    total_qty = calculate_binance_quantity(symbol, sl_dist, usdt_bal, risk_pct=risk_pct)
                    
                    filters = get_symbol_filters(symbol)
                    min_qty = filters["stepSize"] if filters else 0.001
                    if total_qty < min_qty * 3.0:
                        total_qty = min_qty * 3.0
                        logger.info(f"Manual crypto trade quantity adjusted to minimum 3-part limit: {total_qty:.4f}")
                        
                    ok = execute_three_part_binance_trade(
                        symbol=symbol,
                        is_long=is_long,
                        entry_price=price,
                        sl_price=sl_price,
                        total_qty=total_qty,
                        tp1=tp1,
                        tp2=tp2,
                        tp3=tp3,
                        signal_id=manual_signal_id
                    )
                    err_msg = None if ok else "Binance order rejected"
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
                        tp2 = price + tp_dist
                        tp3 = price + sl_dist * 3.5
                    else:
                        sl_price = price + sl_dist
                        tp1 = price - sl_dist
                        tp2 = price - tp_dist
                        tp3 = price - sl_dist * 3.5
                        
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

            # Update status in db directly
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
REQUIRE_SMC_CONFLUENCE = True
AUTO_EXECUTE = True          # toggled from dashboard via DB
CRYPTO_ENABLED = True
METALS_ENABLED = True
FOREX_ENABLED = True
INDICES_ENABLED = True
RISK_LIMITS_ENABLED = True
SMC_TIMEFRAME = mt5.TIMEFRAME_M5
LOOP_INTERVAL = 2

CANDIDATE_PAIRS = {
    "forex": [
        ("EURUSD", "GBPUSD"),
        ("AUDUSD", "NZDUSD"),
        ("EURUSD", "USDCHF"),
        ("GBPUSD", "USDCHF"),
    ],
    "metals": [
        ("XAUUSD", "XAGUSD"),
    ],
    "crypto": [
        ("BTCUSDT", "ETHUSDT"),
        ("SOLUSDT", "BTCUSDT"),
        ("ETHUSDT", "SOLUSDT"),
    ],
    "indices": [
        ("AAPL", "MSFT"),
        ("MSFT", "GOOGL"),
        ("NVDA", "AMD"),
        ("US500", "NAS100"),
    ]
}

EXPECTED_BETA_SIGN = {
    "EURUSD/GBPUSD": 1,
    "EURUSD/USDJPY": -1,
    "GBPUSD/USDJPY": -1,
    "AUDUSD/NZDUSD": 1,
    "EURUSD/USDCHF": -1,
    "GBPUSD/USDCHF": -1,
    "XAUUSD/XAGUSD": 1,
    "BTCUSDT/ETHUSDT": 1,
    "SOLUSDT/BTCUSDT": 1,
    "ETHUSDT/SOLUSDT": 1,
    "AAPL/MSFT": 1,
    "MSFT/GOOGL": 1,
    "NVDA/AMD": 1,
    "US500/NAS100": 1
}

DEFAULT_LOT_SIZES = {
    "metals": 0.15,
    "forex": 1.20,
    "indices": 0.60,
    "stocks": 6.00,
    "crypto": 0.06
}

def simulate_win_rate_for_pair(symbol_a: str, symbol_b: str, z_entry=2.0, z_exit=0.0, z_sl=4.2) -> float:
    """
    Runs a historical Kalman filter spread simulation on the last 150 bars
    to calculate the win rate of mean-reversion trades.
    """
    try:
        cat_a = get_symbol_category(symbol_a)
        cat_b = get_symbol_category(symbol_b)
        
        # Fetch rates
        if cat_a == "crypto":
            df_a = get_binance_rates_df(symbol_a, timeframe_minutes=5, count=150)
        else:
            if not mt5.initialize():
                return 50.0
            check_and_subscribe_symbol(symbol_a)
            df_a = get_rates_df(symbol_a, mt5.TIMEFRAME_M5, count=150)
            
        if cat_b == "crypto":
            df_b = get_binance_rates_df(symbol_b, timeframe_minutes=5, count=150)
        else:
            if not mt5.initialize():
                return 50.0
            check_and_subscribe_symbol(symbol_b)
            df_b = get_rates_df(symbol_b, mt5.TIMEFRAME_M5, count=150)
            
        if df_a is None or df_b is None or df_a.empty or df_b.empty:
            return 50.0
            
        min_len = min(len(df_a), len(df_b))
        if min_len < 30:
            return 50.0
            
        close_a = df_a['close'].iloc[-min_len:].values
        close_b = df_b['close'].iloc[-min_len:].values
        
        # Run Kalman
        q_cov, r_cov = get_kf_parameters(symbol_a)
        from math_models import KalmanFilterRegression
        init_beta_val = EXPECTED_BETA_SIGN.get(f"{symbol_a}/{symbol_b}", EXPECTED_BETA_SIGN.get(f"{symbol_b}/{symbol_a}", 1))
        kf = KalmanFilterRegression(transition_covariance=q_cov, observation_covariance=r_cov, initial_beta=init_beta_val)
        
        z_scores = []
        for i in range(min_len):
            _, _, _, z = kf.update(close_b[i], close_a[i])
            z_scores.append(z)
            
        # Sim trades
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
                        
        if total_trades == 0:
            return 50.0
        return float(round((win_trades / total_trades) * 100.0, 1))
    except Exception as e:
        logger.warning(f"Error simulating win rate for {symbol_a}/{symbol_b}: {e}")
        return 50.0

def cleanup_disabled_scanned_assets(crypto_on, metals_on, forex_on, indices_on):
    try:
        conn = get_connection()
        cur = conn.cursor()
        if not crypto_on:
            cur.execute("DELETE FROM scanned_assets WHERE symbol_pair LIKE '%USDT%'")
        if not metals_on:
            for s_a, s_b in CANDIDATE_PAIRS["metals"]:
                cur.execute("DELETE FROM scanned_assets WHERE symbol_pair = %s", (f"{s_a}/{s_b}",))
        if not forex_on:
            for s_a, s_b in CANDIDATE_PAIRS["forex"]:
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
        
        # Warm up the filter with historical data
        try:
            cat_a = get_symbol_category(symbol_a)
            cat_b = get_symbol_category(symbol_b)
            if cat_a == "crypto":
                df_a = get_binance_rates_df(symbol_a, timeframe_minutes=5, count=100)
            else:
                df_a = get_rates_df(symbol_a, mt5.TIMEFRAME_M5, count=100)
                
            if cat_b == "crypto":
                df_b = get_binance_rates_df(symbol_b, timeframe_minutes=5, count=100)
            else:
                df_b = get_rates_df(symbol_b, mt5.TIMEFRAME_M5, count=100)
                
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

# BUG FIX 2: Fixed SL in pips instead of 3x bid-ask spread
SL_PIPS = 10.0
SL_PIPS_JPY = 0.10
TP_PIPS = 20.0

def get_pip_size(symbol: str) -> float:
    s = symbol.upper()
    if "JPY" in s:
        return 0.01
    if "XAU" in s:
        return 1.0
    if "XAG" in s:
        return 0.1
    if "BTC" in s:
        return 1.0
    if "ETH" in s:
        return 0.1
    if any(x in s for x in ["SOL", "BNB", "AVAX"]):
        return 0.01
    if any(x in s for x in ["XRP", "ADA", "DOGE", "MATIC"]):
        return 0.0001
    # Handle Indices & Stocks
    if any(x in s for x in ["US500", "US30", "NAS100", "GER30", "UK100", "SPX", "DJI", "NDX"]):
        return 1.0
    if any(x in s for x in ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMD", "META", "AMZN"]):
        return 0.1
    return 0.0001

def get_atr(symbol: str, timeframe, count=30) -> float:
    cat = get_symbol_category(symbol)
    if cat == "crypto":
        df = get_binance_rates_df(symbol, timeframe_minutes=5, count=count)
    else:
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


def get_kf_parameters(symbol: str):
    # Normalized prices use standard optimal scale-independent parameters
    cat = get_symbol_category(symbol)
    if cat == "metals":
        return 1e-8, 1e-5
    elif cat == "indices":
        return 1e-7, 1e-4
    elif cat == "crypto":
        return 1e-8, 1e-5
    elif cat == "forex":
        return 1e-9, 1e-6
    else: # stocks/default
        return 1e-7, 1e-4


def get_sl_distance(symbol: str, price: float, sl_pips_override: float = None) -> float:
    """
    Returns SL distance in price units. Uses dashboard-configured sl_pips value.
    Guarantees that the Stop Loss is at least 1.5 * ATR (from 5-minute candles)
    to protect against market noise and invalid tight SLs on Gold/Indices.
    """
    pips = sl_pips_override if sl_pips_override else SL_PIPS
    cat = get_symbol_category(symbol)
    if cat == "crypto":
        base_sl = float(price * (pips / 100.0))
    else:
        base_sl = pips * get_pip_size(symbol)
        
    # Safeguard: Fetch M5 ATR and ensure SL is at least 1.5 * ATR
    try:
        atr = get_atr(symbol, mt5.TIMEFRAME_M5, count=30)
        if atr is not None and atr > 0:
            min_sl = atr * 1.5
            if base_sl < min_sl:
                logger.info(f"SL of {base_sl:.5f} is too tight for {symbol} (noise boundary: {min_sl:.5f}). Automatically adjusted to 1.5 * ATR: {min_sl:.5f}")
                return min_sl
    except Exception as e:
        logger.warning(f"Failed to calculate ATR safeguard for {symbol}: {e}")
        
    return base_sl

def sync_mt5_open_positions_with_db():
    """
    Syncs open MT5 tickets with the database trades table.
    Supports both Hedging and Netting accounts by checking symbol-based volumes.
    """
    try:
        if not mt5.initialize():
            return
            
        positions = mt5.positions_get()
        if positions is None:
            return
            
        # Group active positions by symbol (case-insensitive)
        active_positions_by_symbol = {}
        for p in positions:
            active_positions_by_symbol[p.symbol.upper()] = p
        
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT ticket, symbol, lots, entry_price, order_type FROM trades WHERE status = 'OPEN'")
        db_open_trades = cur.fetchall()
        
        # Group db open trades by symbol
        db_trades_by_symbol = {}
        for row in db_open_trades:
            sym = row[1].upper()
            if sym not in db_trades_by_symbol:
                db_trades_by_symbol[sym] = []
            db_trades_by_symbol[sym].append(row)

        for sym, db_rows in db_trades_by_symbol.items():
            active_pos = active_positions_by_symbol.get(sym)
            
            if active_pos is None:
                # No active position in MT5 for this symbol at all. All db trades for this symbol are closed.
                for ticket, symbol, lots, entry_price, order_type in db_rows:
                    if ticket < 1000:
                        continue
                    history = mt5.history_deals_get(position=ticket)
                    close_price = float(entry_price)
                    profit = 0.0
                    close_time = datetime.datetime.now()
                    if history:
                        for deal in history:
                            if deal.entry == mt5.DEAL_ENTRY_OUT:
                                close_price = float(deal.price)
                                profit = float(deal.profit)
                                close_time = datetime.datetime.fromtimestamp(deal.time)
                                break
                    log_trade_exit(ticket, close_price, profit, close_time)
                    logger.info(f"[MT5 SYNC] Netting close: Ticket {ticket} ({symbol}) detected closed (no active position).")
            else:
                # Active position exists in MT5. Verify volume to handle netting scale-down.
                db_rows_sorted = sorted(db_rows, key=lambda x: x[0])
                total_db_volume = sum(float(r[2]) for r in db_rows_sorted)
                active_volume = float(active_pos.volume)
                
                if active_volume < total_db_volume - 0.005:
                    volume_to_close = total_db_volume - active_volume
                    for ticket, symbol, lots, entry_price, order_type in db_rows_sorted:
                        lots_val = float(lots)
                        if volume_to_close >= lots_val - 0.005:
                            history = mt5.history_deals_get(position=ticket)
                            close_price = float(entry_price)
                            profit = 0.0
                            close_time = datetime.datetime.now()
                            if history:
                                for deal in history:
                                    if deal.entry == mt5.DEAL_ENTRY_OUT:
                                        close_price = float(deal.price)
                                        profit = float(deal.profit)
                                        close_time = datetime.datetime.fromtimestamp(deal.time)
                                        break
                            log_trade_exit(ticket, close_price, profit, close_time)
                            logger.info(f"[MT5 SYNC] Netting scale-down: Ticket {ticket} ({symbol}) marked closed (volume reduced).")
                            volume_to_close -= lots_val
                        else:
                            break
                            
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error in sync_mt5_open_positions_with_db: {e}")

def get_tp_distance(symbol: str, price: float, tp_pips_override: float = None) -> float:
    """
    Returns TP distance in price units. Uses dashboard-configured tp_pips value.
    """
    pips = tp_pips_override if tp_pips_override else TP_PIPS
    cat = get_symbol_category(symbol)
    if cat == "crypto":
        return float(price * (pips / 100.0))
    else:
        return pips * get_pip_size(symbol)

def is_pair_in_cooldown(symbol_a: str, symbol_b: str) -> bool:
    """
    Returns True if a trade for this symbol pair was closed in the last 30 minutes.
    This acts as a restart-proof database-backed cooldown safeguard.
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        # Look for trades closed in the last 30 minutes
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
        return 2.4, 0.0, 4.2, 5.0  # z_entry, z_exit, z_sl, sl_atr_mult
    elif cat == "indices":
        return 2.4, 0.0, 4.2, 5.0
    elif cat == "crypto":
        return 2.3, 0.0, 4.2, 6.0
    else: # forex/default
        return 2.3, 0.0, 4.2, 6.0

def close_single_trade(symbol, ticket, volume, order_type):
    cat = get_symbol_category(symbol)
    if cat == "crypto":
        is_long = (order_type.upper() == "BUY")
        ok = close_binance_partial(symbol, volume, is_long)
        if ok:
            log_trade_exit(ticket, 0.0, 0.0, datetime.datetime.now())
        return ok
    else:
        return close_position_by_ticket(symbol, ticket, volume)

def manage_spread_positions(symbol_a, symbol_b, z_score, kf=None):
    """
    Monitors active positions for symbol_a and symbol_b.
    1. Handles dynamic Z-score exits (mean reversion and Z-score SL).
    2. Handles Ornstein-Uhlenbeck statistical half-life time-based exits.
    3. Synchronizes Leg B (hedge) when Leg A parts are closed by the broker.
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        # Find signal_ids that have at least one OPEN trade for these symbols
        cur.execute(
            "SELECT DISTINCT signal_id FROM trades WHERE status = 'OPEN' AND symbol IN (%s, %s) AND signal_id IS NOT NULL",
            (symbol_a, symbol_b)
        )
        active_signal_ids = [row[0] for row in cur.fetchall()]
        
        if not active_signal_ids:
            cur.close()
            conn.close()
            return

        # Fetch ALL trades (both OPEN and CLOSED) for these active signal_ids so we can detect closed Leg A parts
        cur.execute(
            "SELECT ticket, symbol, order_type, lots, comment, signal_id, entry_time, status FROM trades WHERE signal_id IN %s",
            (tuple(active_signal_ids),)
        )
        all_trades_for_signals = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error fetching active trades in manage_spread_positions: {e}")
        return

    if not all_trades_for_signals:
        return

    # Group trades by signal_id
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

    # Compute Ornstein-Uhlenbeck statistical half-life limit
    half_life_bars = 45.0
    if kf is not None:
        from math_models import calculate_half_life
        half_life_bars = calculate_half_life(kf.spread_history)
    max_holding_seconds = half_life_bars * 300.0 * 2.5  # M5 bars * 300s/bar * 2.5 multiplier

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

        leg_a_trades = [t for t in trades if t["symbol"].upper() == sym_a.upper()]
        leg_b_trades = [t for t in trades if t["symbol"].upper() == sym_b.upper()]

        open_leg_a_trades = [t for t in leg_a_trades if t["status"] == 'OPEN']
        open_leg_b_trades = [t for t in leg_b_trades if t["status"] == 'OPEN']

        # 1. Cleanup check: If Leg A has NO open trades left but Leg B still has open trades, close Leg B immediately
        if not open_leg_a_trades and open_leg_b_trades:
            logger.info(f"Cleanup: Leg A is fully closed for signal_id {sig_id}. Closing remaining Leg B trades.")
            for t_b in open_leg_b_trades:
                close_single_trade(t_b["symbol"], t_b["ticket"], t_b["lots"], t_b["order_type"])
            continue

        if not open_leg_a_trades:
            continue

        # Dynamically calculate the Z-score for this specific pair
        z_score_for_pair = 0.0
        try:
            tick_a = mt5.symbol_info_tick(sym_a) if get_symbol_category(sym_a) != "crypto" else get_binance_live_tick(sym_a)
            tick_b = mt5.symbol_info_tick(sym_b) if get_symbol_category(sym_b) != "crypto" else get_binance_live_tick(sym_b)
            if tick_a and tick_b:
                p_a = (tick_a.bid + tick_a.ask) / 2.0
                p_b = (tick_b.bid + tick_b.ask) / 2.0
                kf_pair = get_kf_for_pair(sym_a, sym_b)
                z_score_for_pair = kf_pair.get_current_z(p_b, p_a)
            else:
                if sym_a.upper() == symbol_a.upper() and sym_b.upper() == symbol_b.upper():
                    z_score_for_pair = z_score
        except Exception as ez:
            logger.error(f"Error calculating dynamic z_score for {sym_a}/{sym_b}: {ez}")
            if sym_a.upper() == symbol_a.upper() and sym_b.upper() == symbol_b.upper():
                z_score_for_pair = z_score

        # Fetch the actual entry Z-score of the signal to calculate a relative Z Stop Loss
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

        # Compute Ornstein-Uhlenbeck statistical half-life limit
        half_life_bars = 45.0
        kf_pair = get_kf_for_pair(sym_a, sym_b)
        if kf_pair is not None:
            from math_models import calculate_half_life
            half_life_bars = calculate_half_life(kf_pair.spread_history)
        max_holding_seconds = half_life_bars * 300.0 * 2.5

        is_buy_spread = (open_leg_a_trades[0]["order_type"] == "BUY")
        exit_triggered = False
        exit_reason = ""

        # Check statistical half-life time exit first
        for t in trades:
            entry_t = t["entry_time"]
            if entry_t is not None:
                elapsed = (datetime.datetime.now() - entry_t).total_seconds()
                if elapsed > max_holding_seconds:
                    exit_triggered = True
                    exit_reason = f"OU_HALF_LIFE_EXPIRATION (elapsed {elapsed/60:.1f}m > {max_holding_seconds/60:.1f}m)"
                    break

        # Check standard Z-score exit conditions if time exit didn't trigger
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

        # Safeguard: FundedNext Consistency Rule (trades closed under 30s)
        min_hold_ok = True
        for t in trades:
            entry_t = t["entry_time"]
            if entry_t is not None:
                elapsed = (datetime.datetime.now() - entry_t).total_seconds()
                if elapsed < 35.0:
                    min_hold_ok = False
                    break

        if exit_triggered and not min_hold_ok:
            exit_triggered = False
            logger.info(f"Exit deferred for signal_id {sig_id} to satisfy 35s minimum hold time.")

        if exit_triggered:
            logger.info(f"Dynamic exit triggered for signal_id {sig_id}. Reason: {exit_reason}. Closing all positions.")
            for t_a in open_leg_a_trades:
                close_single_trade(t_a["symbol"], t_a["ticket"], t_a["lots"], t_a["order_type"])
            for t_b in open_leg_b_trades:
                close_single_trade(t_b["symbol"], t_b["ticket"], t_b["lots"], t_b["order_type"])
            continue

        # 2. Sync MT5 open positions with database so closed TP1/TP2 tickets update immediately
        sync_mt5_open_positions_with_db()

        # 3. Hedge scale-out sync:
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

        db_leg_a = [t for t in all_db_trades if t[1].upper() == sym_a.upper()]
        db_leg_b = [t for t in all_db_trades if t[1].upper() == sym_b.upper()]

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
    # Crypto disabled completely in this Forex/Metals/Indices instance
    if any(x in s for x in ["XAU", "XAG"]):
        return "metals"
    if any(x in s for x in ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMD", "META", "AMZN", "US500", "US30", "NAS100", "GER30", "UK100"]):
        return "indices"
    return "forex"

def get_hedge_execution_parameters(action_spread: str, beta: float, tick_b) -> tuple:
    """
    Returns (order_type, side, price, sl_sign) for Leg B order
    taking into account spread action and correlation (sign of beta).
    """
    is_buy_spread = (action_spread == "BUY_SPREAD")
    # For positive correlation (beta >= 0), Leg B is traded in opposite direction of Leg A
    # For negative correlation (beta < 0), Leg B is traded in same direction as Leg A
    if beta >= 0:
        if is_buy_spread:
            return 1, "SELL", float(tick_b.bid), 1.0  # mt5.ORDER_TYPE_SELL = 1
        else:
            return 0, "BUY", float(tick_b.ask), -1.0  # mt5.ORDER_TYPE_BUY = 0
    else:
        if is_buy_spread:
            return 0, "BUY", float(tick_b.ask), -1.0  # mt5.ORDER_TYPE_BUY = 0
        else:
            return 1, "SELL", float(tick_b.bid), 1.0  # mt5.ORDER_TYPE_SELL = 1

def get_hedge_quantity(symbol_a: str, symbol_b: str, qty_a: float, beta: float, cat_a: str, cat_b: str) -> float:
    """
    Calculates the correct hedge quantity for Leg B based on Leg A quantity, beta,
    and the relative contract sizes of symbol_a and symbol_b.
    """
    if cat_b == "crypto":
        if cat_a == "crypto":
            contract_ratio = 1.0
        else:
            info_a = mt5.symbol_info(symbol_a)
            contract_ratio = info_a.trade_contract_size if info_a else 1.0
            
        filters_b = get_symbol_filters(symbol_b)
        qty_prec_b = filters_b["quantityPrecision"] if filters_b else 3
        return round(qty_a * abs(beta) * contract_ratio, qty_prec_b)
    else:
        if cat_a == "crypto":
            contract_size_a = 1.0
        else:
            info_a = mt5.symbol_info(symbol_a)
            contract_size_a = info_a.trade_contract_size if info_a else 1.0
            
        info_b = mt5.symbol_info(symbol_b)
        contract_size_b = info_b.trade_contract_size if info_b else 1.0
        
        raw_qty = qty_a * abs(beta) * (contract_size_a / contract_size_b)
        return round_volume(symbol_b, raw_qty)


# ==============================================================================
# MAIN TRADING ENGINE RUN LOOP
# ==============================================================================
def main():
    print("=========================================")
    print("   JANE STREET QUANT BOT INITIALIZING    ")
    print("=========================================\n")

    global REQUIRE_SMC_CONFLUENCE, SL_PIPS, TP_PIPS, AUTO_EXECUTE, Z_ENTRY_THRESHOLD, DEFAULT_LOTS, RISK_LIMITS_ENABLED, ML_MODEL
    global CRYPTO_ENABLED, METALS_ENABLED, FOREX_ENABLED, INDICES_ENABLED
    global SL_PIPS, TP_PIPS, REQUIRE_SMC_CONFLUENCE, AUTO_EXECUTE, RISK_LIMITS_ENABLED, Z_ENTRY_THRESHOLD, DEFAULT_LOTS, MAX_TRADES
    global KNIFE_PROTECTION_ENABLED, OBI_ENABLED, VOLATILITY_FILTER_ENABLED

    load_config()

    # Load local ML model if it exists
    ML_MODEL = None
    if os.path.exists("ml_model.joblib"):
        try:
            ML_MODEL = joblib.load("ml_model.joblib")
            logger.info("Successfully loaded local Machine Learning model: ml_model.joblib")
        except Exception as e:
            logger.error(f"Failed to load ML model: {e}")

    # ── BUG FIX 3: Create all DB tables before anything tries to write to them ──
    logger.info("Initializing database tables...")
    initialize_database()
    logger.info("Database ready.")

    # Start background heartbeat thread to keep dashboard online during long loops
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
    
    # Clean up any stale disabled categories on startup
    cleanup_disabled_scanned_assets(CRYPTO_ENABLED, METALS_ENABLED, FOREX_ENABLED, INDICES_ENABLED)

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
    win_rate_loop_counter = 0
    loop_log_counter = 0
    SMC_ZONES_CACHE = {}
    smc_counter_cache = {}

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
            
            # Check if there is an account switch OR a startup mismatch on 0 trades today
            from database import get_connection
            startup_mismatch = False
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("SELECT initial_balance FROM bot_state WHERE id = 1")
                state_row = cur.fetchone()
                db_initial = float(state_row[0]) if (state_row and state_row[0] is not None) else 0.0
                
                # Check trades count today
                import datetime
                today_date = datetime.date.today()
                cur.execute("SELECT trades_today FROM daily_metrics WHERE trading_date = %s", (today_date,))
                metrics_row = cur.fetchone()
                trades_today_val = metrics_row[0] if metrics_row else 0
                
                # Check active positions count
                cur.execute("SELECT COUNT(*) FROM trades WHERE status = 'OPEN'")
                open_trades_count = cur.fetchone()[0] or 0
                
                cur.close()
                conn.close()
                
            except Exception as e:
                logger.error(f"Error checking startup metrics sync: {e}")
                
            login_changed = (active_login_id is not None and active_login_id != current_login)
            
            if login_changed:
                logger.info(f"Syncing metrics (login_changed={login_changed}). Resetting metrics to {acc_info.equity:.2f} due to account switch.")
                from database import reset_database_metrics_for_new_account
                reset_database_metrics_for_new_account(current_login, acc_info.equity)
                
                # Reset local daily start equity in memory to the new account's equity
                daily_start_equity = float(acc_info.equity)
                
                # Update safeguards cache here to prevent circular imports
                try:
                    import risk_safeguards
                    import datetime
                    risk_safeguards._cached_start_equity = float(acc_info.equity)
                    risk_safeguards._cached_start_equity_date = datetime.date.today()
                    risk_safeguards._cached_last_login = int(current_login)
                except Exception as ex:
                    logger.error(f"Error updating risk_safeguards cache in main loop: {ex}")
                
            active_login_id = current_login

            # ── DB CONFIG SYNC (every ~10s) ─────────────────────────────────
            if db_config_counter % 5 == 0:
                db_cfg = fetch_db_config()
                if db_cfg:
                    new_pair, new_sl, new_tp, new_smc, new_auto_exec, new_crypto, new_metals, new_forex, new_indices, new_risk_limits, new_z_entry, new_def_lots, new_max_trades, new_knife, new_obi, new_vol = db_cfg
                    parts = new_pair.split("/")
                    if len(parts) == 2 and parts[0] != parts[1]:
                        if GLOBAL_CONFIG["SYMBOL_A"] != parts[0] or GLOBAL_CONFIG["SYMBOL_B"] != parts[1]:
                            logger.info(f"DB config update — switching to {new_pair}")
                            GLOBAL_CONFIG["SYMBOL_A"] = parts[0]
                            GLOBAL_CONFIG["SYMBOL_B"] = parts[1]
                            save_config(new_pair)
                    if SL_PIPS != new_sl:
                        logger.info(f"[CONFIG UPDATE] SL Pips updated: {SL_PIPS} -> {new_sl}")
                        SL_PIPS = new_sl
                    if TP_PIPS != new_tp:
                        logger.info(f"[CONFIG UPDATE] TP Pips updated: {TP_PIPS} -> {new_tp}")
                        TP_PIPS = new_tp
                    if REQUIRE_SMC_CONFLUENCE != new_smc:
                        logger.info(f"[CONFIG UPDATE] SMC Confluence updated: {REQUIRE_SMC_CONFLUENCE} -> {new_smc}")
                        REQUIRE_SMC_CONFLUENCE = new_smc
                    if AUTO_EXECUTE != new_auto_exec:
                        logger.info(f"[CONFIG UPDATE] Auto Execute updated: {AUTO_EXECUTE} -> {new_auto_exec}")
                        AUTO_EXECUTE = new_auto_exec
                    if CRYPTO_ENABLED != new_crypto:
                        CRYPTO_ENABLED = False
                    if METALS_ENABLED != new_metals:
                        logger.info(f"[CONFIG UPDATE] Metals Enabled updated: {METALS_ENABLED} -> {new_metals}")
                        METALS_ENABLED = new_metals
                    if FOREX_ENABLED != new_forex:
                        logger.info(f"[CONFIG UPDATE] Forex Enabled updated: {FOREX_ENABLED} -> {new_forex}")
                        FOREX_ENABLED = new_forex
                    if INDICES_ENABLED != new_indices:
                        logger.info(f"[CONFIG UPDATE] Indices Enabled updated: {INDICES_ENABLED} -> {new_indices}")
                        INDICES_ENABLED = new_indices
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
                    
                    # Clean up disabled categories in the database immediately
                    cleanup_disabled_scanned_assets(CRYPTO_ENABLED, METALS_ENABLED, FOREX_ENABLED, INDICES_ENABLED)
            db_config_counter += 1

            S_A = GLOBAL_CONFIG["SYMBOL_A"]
            S_B = GLOBAL_CONFIG["SYMBOL_B"]
            current_pair_context = f"{S_A}/{S_B}"

            cat_a = get_symbol_category(S_A)
            cat_b = get_symbol_category(S_B)

            # Resolve broker aliases for active pair
            S_A_resolved = resolve_broker_symbol(S_A) if cat_a != "crypto" else S_A
            S_B_resolved = resolve_broker_symbol(S_B) if cat_b != "crypto" else S_B

            # News Guard check
            import news_guard
            is_news_halted, news_msg = news_guard.get_news_halt_status([S_A_resolved, S_B_resolved])

            # Determine equity based on asset class
            if cat_a == "crypto":
                try:
                    usdt_bal, _ = get_binance_usdt_balance()
                    current_equity = usdt_bal
                except Exception:
                    current_equity = 0.0
            else:
                current_equity = acc_info.equity if acc_info else 0.0

            # Calculate daily drawdown using the correct equity (only if equity > 0.0)
            if current_equity > 0.0:
                is_limit_breached, daily_loss_p = check_drawdown_limit(current_equity)
            else:
                is_limit_breached, daily_loss_p = False, 0.0

            # Detect if it's a demo or contest account
            is_demo = getattr(acc_info, "trade_mode", 0) in (0, 1)  # 0 is DEMO, 1 is CONTEST

            if is_limit_breached:
                if is_demo or not RISK_LIMITS_ENABLED:
                    logger.info(f"Daily drawdown limit breached ({daily_loss_p:.2f}%), but bypassing on Demo/Contest account or when Risk Limits are disabled.")
                    is_halted = False
                else:
                    is_halted = True
            else:
                is_halted = False

            if daily_start_equity is None and current_equity > 0.0:
                daily_start_equity = current_equity

            if is_halted:
                close_all_positions(S_A_resolved)
                close_all_positions(S_B_resolved)
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

            # ── 1. COMPILE CANDIDATE PAIRS ──
            pairs_to_scan = []
            if FOREX_ENABLED:
                pairs_to_scan.extend(CANDIDATE_PAIRS["forex"])
            if METALS_ENABLED:
                pairs_to_scan.extend(CANDIDATE_PAIRS["metals"])
            if CRYPTO_ENABLED:
                pairs_to_scan.extend(CANDIDATE_PAIRS["crypto"])
            if INDICES_ENABLED:
                pairs_to_scan.extend(CANDIDATE_PAIRS["indices"])

            # Include custom pair if set and not already in pool
            if current_pair_context not in [f"{p[0]}/{p[1]}" for p in pairs_to_scan]:
                parts = current_pair_context.split('/')
                if len(parts) == 2 and parts[0] != parts[1]:
                    pairs_to_scan.append((parts[0], parts[1]))

            candidate_signals = []

            # Periodically update win rates
            if win_rate_loop_counter % 300 == 0:
                logger.info("Recalculating historical win rates for all enabled candidate pairs...")
                for s_a, s_b in pairs_to_scan:
                    pair_key = f"{s_a}/{s_b}"
                    WIN_RATE_CACHE[pair_key] = simulate_win_rate_for_pair(s_a, s_b, z_entry=Z_ENTRY_THRESHOLD)
            win_rate_loop_counter += 1

            # Check closed trades for all currently open symbols in the database
            try:
                conn_closed = get_connection()
                cur_closed = conn_closed.cursor()
                cur_closed.execute("SELECT DISTINCT symbol FROM trades WHERE status = 'OPEN'")
                open_symbols = [row[0] for row in cur_closed.fetchall()]
                cur_closed.close()
                conn_closed.close()
                
                # Always ensure S_A and S_B are in the list to be checked
                if S_A_resolved not in open_symbols:
                    open_symbols.append(S_A_resolved)
                if S_B_resolved not in open_symbols:
                    open_symbols.append(S_B_resolved)
                    
                for sym in open_symbols:
                    cat = get_symbol_category(sym)
                    if cat == "crypto":
                        check_closed_binance_trades(sym)
                    else:
                        check_closed_trades(sym)
            except Exception as e:
                logger.error(f"Error checking closed trades for open symbols: {e}")

            # Fetch active positions in MT5/Binance
            has_positions = False
            floating_profit = 0.0
            active_js_positions = []
            try:
                has_positions = get_open_trades_count() > 0
                positions = mt5.positions_get()
                active_js_positions = [p for p in positions if p.magic == MAGIC_NUMBER] if positions else []
                floating_profit += sum(p.profit for p in active_js_positions)
                if len(active_js_positions) > 0:
                    has_positions = True
                else:
                    peak_floating_profit = 0.0
            except Exception:
                pass

            # ── Equity Trailing Stop Safeguard (Profit Lock) ──
            if has_positions and floating_profit >= 60.00:
                if floating_profit > peak_floating_profit:
                    peak_floating_profit = floating_profit
                    logger.info(f"[EQUITY TRAIL] New peak floating profit: ${peak_floating_profit:.2f}")
                
                trail_stop_level = peak_floating_profit * 0.89 # 11% trailing distance (locks in 89% of peak profit)
                if floating_profit <= trail_stop_level:
                    logger.info(f"[EQUITY TRAIL] Floating profit ${floating_profit:.2f} fell below trailing stop level ${trail_stop_level:.2f} (Peak: ${peak_floating_profit:.2f}). Closing all positions to lock profits.")
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
                    for pos in positions:
                        cur.execute(
                            "UPDATE trades SET close_price = %s, profit = %s WHERE ticket = %s AND status = 'OPEN'",
                            (float(pos.price_current), float(pos.profit), int(pos.ticket))
                        )

                cur.execute("SELECT ticket, symbol, order_type, lots, entry_price FROM trades WHERE status = 'OPEN'")
                open_trades = cur.fetchall()
                for ticket, symbol, order_type, lots, entry_price in open_trades:
                    cat = get_symbol_category(symbol)
                    if cat == "crypto":
                        tick = get_binance_live_tick(symbol)
                        if tick:
                            price_val = (tick.bid + tick.ask) / 2.0
                            mult = 1.0 if order_type.upper() == "BUY" else -1.0
                            profit_val = (price_val - float(entry_price)) * float(lots) * mult
                            cur.execute(
                                "UPDATE trades SET close_price = %s, profit = %s WHERE ticket = %s",
                                (float(price_val), float(profit_val), int(ticket))
                            )
                conn.commit()
                cur.close()
                conn.close()
            except Exception as e:
                logger.error(f"Error syncing open trades telemetry to DB: {e}")

            # ── 2. SCANNING LOOP FOR ALL PAIRS ──
            active_pair_z_score = 0.0
            active_pair_beta = 0.0
            active_pair_obi_a = 0.0
            active_pair_obi_b = 0.0
            active_pair_velocity = 0.0

            for s_a, s_b in pairs_to_scan:
                pk = f"{s_a}/{s_b}"
                cat_a = get_symbol_category(s_a)
                cat_b = get_symbol_category(s_b)

                # Resolve broker aliases for MT5 symbols
                s_a_resolved = resolve_broker_symbol(s_a) if cat_a != "crypto" else s_a
                s_b_resolved = resolve_broker_symbol(s_b) if cat_b != "crypto" else s_b

                # Fetch ticks
                tick_a_scan, tick_b_scan = None, None
                bids_a_scan, asks_a_scan = [], []
                bids_b_scan, asks_b_scan = [], []

                try:
                    if cat_a == "crypto":
                        tick_a_scan = get_binance_live_tick(s_a_resolved)
                        bids_a_scan, asks_a_scan = get_binance_market_book(s_a_resolved)
                    else:
                        check_and_subscribe_symbol(s_a_resolved)
                        tick_a_scan = mt5.symbol_info_tick(s_a_resolved)
                        bids_a_scan, asks_a_scan = get_market_book(s_a_resolved)

                    if cat_b == "crypto":
                        tick_b_scan = get_binance_live_tick(s_b_resolved)
                        bids_b_scan, asks_b_scan = get_binance_market_book(s_b_resolved)
                    else:
                        check_and_subscribe_symbol(s_b_resolved)
                        tick_b_scan = mt5.symbol_info_tick(s_b_resolved)
                        bids_b_scan, asks_b_scan = get_market_book(s_b_resolved)
                except Exception:
                    continue

                if tick_a_scan is None or tick_b_scan is None:
                    continue

                p_a = (tick_a_scan.bid + tick_a_scan.ask) / 2.0
                p_b = (tick_b_scan.bid + tick_b_scan.ask) / 2.0

                # Kalman update (Only update parameters once per M5 bar; compute Z dynamically in between)
                kf_pair = get_kf_for_pair(s_a_resolved, s_b_resolved)
                now_dt = datetime.datetime.now()
                bar_key = (now_dt.year, now_dt.month, now_dt.day, now_dt.hour, now_dt.minute // 5)
                if LAST_KF_UPDATE_BAR.get(pk) != bar_key:
                    beta, alpha, spread, z = kf_pair.update(p_b, p_a)
                    LAST_KF_UPDATE_BAR[pk] = bar_key
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

                # SMC update
                if s_a_resolved not in SMC_ZONES_CACHE or smc_counter_cache.get(s_a_resolved, 0) >= 15:
                    try:
                        if cat_a == "crypto":
                            r_df = get_binance_rates_df(s_a_resolved, timeframe_minutes=5, count=100)
                        else:
                            r_df = get_rates_df(s_a_resolved, SMC_TIMEFRAME, count=100)
                        if r_df is not None and not r_df.empty:
                            SMC_ZONES_CACHE[s_a_resolved] = detect_smc_zones(r_df)
                            log_fvg_zones(s_a_resolved, SMC_ZONES_CACHE[s_a_resolved])
                        smc_counter_cache[s_a_resolved] = 0
                    except Exception as e:
                        logger.error(f"SMC scan error for {s_a_resolved}: {e}")
                else:
                    smc_counter_cache[s_a_resolved] = smc_counter_cache.get(s_a_resolved, 0) + 1

                # Signal check
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

                z_velocity = kf_pair.get_velocity(k=3)
                dynamic_z_entry = kf_pair.get_dynamic_z_entry(Z_ENTRY_THRESHOLD)

                if cat_a == "forex":
                    z_vel_lim = 0.02
                elif cat_a == "metals":
                    z_vel_lim = 0.08
                else:
                    z_vel_lim = 0.05

                action = "NONE"
                # Evaluate active protections based strictly on Dashboard Toggles (at all Z-thresholds)
                effective_dyn_z = dynamic_z_entry if VOLATILITY_FILTER_ENABLED else Z_ENTRY_THRESHOLD
                _, _, z_sl_val, _ = get_strategy_parameters(s_a_resolved)
                
                pass_z_buy = (z < -effective_dyn_z) and (z > -z_sl_val)
                pass_z_sell = (z > effective_dyn_z) and (z < z_sl_val)
                
                pass_vel_buy = (z_velocity > -z_vel_lim) if KNIFE_PROTECTION_ENABLED else True
                pass_vel_sell = (z_velocity < z_vel_lim) if KNIFE_PROTECTION_ENABLED else True
                
                pass_obi_buy = obi_buy_pass if OBI_ENABLED else True
                pass_obi_sell = obi_sell_pass if OBI_ENABLED else True
                
                pass_smc_buy = in_bullish_zone if REQUIRE_SMC_CONFLUENCE else True
                pass_smc_sell = in_bearish_zone if REQUIRE_SMC_CONFLUENCE else True
                
                if pass_z_buy and pass_vel_buy and pass_obi_buy and pass_smc_buy:
                    action = "BUY_SPREAD"
                elif pass_z_sell and pass_vel_sell and pass_obi_sell and pass_smc_sell:
                    action = "SELL_SPREAD"

                # Validate beta sign and magnitude to prevent same-side hedge order anomalies
                if action != "NONE":
                    expected_sign = EXPECTED_BETA_SIGN.get(pk, 1)
                    beta_sign = 1 if beta >= 0 else -1
                    if beta_sign != expected_sign:
                        logger.warning(f"Correlation anomaly for {pk}: estimated beta {beta:.4f} has wrong sign (expected {expected_sign}). Skipping signal.")
                        action = "NONE"
                    elif abs(beta) < 0.05:
                        logger.warning(f"Hedge ratio too low for {pk}: beta {beta:.4f}. Skipping signal.")
                        action = "NONE"

                # Debug log why signal was skipped if base Z threshold was crossed but action is NONE
                base_z_triggered = (z < -Z_ENTRY_THRESHOLD) or (z > Z_ENTRY_THRESHOLD)
                if base_z_triggered and action == "NONE":
                    reasons = []
                    if z < -Z_ENTRY_THRESHOLD:
                        if VOLATILITY_FILTER_ENABLED and not (z < -dynamic_z_entry):
                            reasons.append(f"Z-score {z:.3f} not below dynamic threshold {-dynamic_z_entry:.3f} (volatility protection)")
                        if KNIFE_PROTECTION_ENABLED and not (z_velocity > -z_vel_lim):
                            reasons.append(f"Z-velocity {z_velocity:.3f} too fast (falling knife protection, limit: {-z_vel_lim})")
                        if OBI_ENABLED and not obi_buy_pass:
                            reasons.append(f"Adverse OBI pressure {net_obi:.3f} < -0.20 (sell wall)")
                        if REQUIRE_SMC_CONFLUENCE and not in_bullish_zone:
                            reasons.append("Price not in Bullish SMC Zone (Order Block/FVG)")
                    else:
                        if VOLATILITY_FILTER_ENABLED and not (z > dynamic_z_entry):
                            reasons.append(f"Z-score {z:.3f} not above dynamic threshold {dynamic_z_entry:.3f} (volatility protection)")
                        if KNIFE_PROTECTION_ENABLED and not (z_velocity < z_vel_lim):
                            reasons.append(f"Z-velocity {z_velocity:.3f} too fast (rising knife protection, limit: {z_vel_lim})")
                        if OBI_ENABLED and not obi_sell_pass:
                            reasons.append(f"Adverse OBI pressure {net_obi:.3f} > 0.20 (buy wall)")
                        if REQUIRE_SMC_CONFLUENCE and not in_bearish_zone:
                            reasons.append("Price not in Bearish SMC Zone (Order Block/FVG)")
                    
                    if reasons:
                        logger.info(f"Signal threshold crossed for {pk} (Z={z:.3f}), but skipped due to: {', '.join(reasons)}")

                win_rate = WIN_RATE_CACHE.get(pk, 50.0)
                update_scanned_asset(pk, p_a, p_b, win_rate, z, action)

                # Track telemetry for current active pair
                if pk.upper().strip() == current_pair_context.upper().strip():
                    active_pair_z_score = z
                    active_pair_beta = beta
                    active_pair_obi_a = obi_a
                    active_pair_obi_b = obi_b
                    active_pair_velocity = z_velocity

                # Cooldown checks
                cooldown_dir = COOLDOWN_DIRECTIONS.get(pk)
                if cooldown_dir == "BUY_SPREAD" and z > -1.0:
                    COOLDOWN_DIRECTIONS[pk] = None
                    cooldown_dir = None
                elif cooldown_dir == "SELL_SPREAD" and z < 1.0:
                    COOLDOWN_DIRECTIONS[pk] = None
                    cooldown_dir = None

                if action != "NONE" and cooldown_dir != action and not is_pair_in_cooldown(s_a_resolved, s_b_resolved):
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

            # ── 3. MANAGE ACTIVE POSITION EXITS ──
            kf_active = get_kf_for_pair(S_A_resolved, S_B_resolved)
            manage_spread_positions(S_A_resolved, S_B_resolved, active_pair_z_score, kf=kf_active)

            # ── 4. MANUAL TRADE COMMANDS ──
            tick_a_active = mt5.symbol_info_tick(S_A_resolved) if get_symbol_category(S_A_resolved) != "crypto" else get_binance_live_tick(S_A_resolved)
            tick_b_active = mt5.symbol_info_tick(S_B_resolved) if get_symbol_category(S_B_resolved) != "crypto" else get_binance_live_tick(S_B_resolved)
            if tick_a_active and tick_b_active:
                poll_manual_commands(tick_a_active, tick_b_active, SL_PIPS)

            # ── 5. ALGO TRADING & AUTO-EXECUTION ──
            trades_today = get_trades_count_today()
            is_trade_limit_ok = (not RISK_LIMITS_ENABLED) or is_demo or (trades_today < MAX_DAILY_TRADES)
            
            if AUTO_EXECUTE and not has_positions and is_trade_limit_ok and not is_news_halted and candidate_signals:
                # Prioritize current active pair signal first, fallback to scanning highest win-rate signal second
                active_pair_sig = None
                for sig in candidate_signals:
                    if sig["pair"] == (S_A, S_B) or sig["pair"] == (GLOBAL_CONFIG["SYMBOL_A"], GLOBAL_CONFIG["SYMBOL_B"]):
                        active_pair_sig = sig
                        break

                if active_pair_sig:
                    logger.info(f"Signal detected on current active pair {S_A}/{S_B}. Executing active pair trade.")
                    best_sig = active_pair_sig
                else:
                    # Sort candidate signals by win rate descending
                    candidate_signals.sort(key=lambda x: x["win_rate"], reverse=True)
                    best_sig = candidate_signals[0]
                
                best_pair = best_sig["pair"]
                best_action = best_sig["action"]
                best_s_a, best_s_b = best_pair
                best_cat_a = get_symbol_category(best_s_a)
                best_cat_b = get_symbol_category(best_s_b)
                
                if (best_cat_a == "crypto" or is_spread_valid(best_s_a)) and (best_cat_b == "crypto" or is_spread_valid(best_s_b)):
                    
                    # Machine Learning Filter evaluation
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
                            
                    logger.info(f"Scanning selected pair: {best_s_a}/{best_s_b} with max win rate {best_sig['win_rate']}% and action {best_action}")
                    
                    # Switch active pair
                    S_A, S_B = best_s_a, best_s_b
                    GLOBAL_CONFIG["SYMBOL_A"] = S_A
                    GLOBAL_CONFIG["SYMBOL_B"] = S_B
                    current_pair_context = f"{S_A}/{S_B}"
                    save_config(current_pair_context)
                    
                    # Log signal
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
                    
                    if is_long:
                        if best_cat_a == "crypto":
                            usdt_bal, _ = get_binance_usdt_balance()
                            qty_a = calculate_binance_quantity(S_A, sl_dist, usdt_bal)
                            qty_b = get_hedge_quantity(S_A, S_B, qty_a, best_sig["beta"], best_cat_a, best_cat_b)
                            
                            if execute_three_part_binance_trade(
                                S_A, True, best_sig["tick_a"].ask, best_sig["tick_a"].ask - sl_dist, qty_a,
                                best_sig["price_a"] + sl_dist, best_sig["price_a"] + tp_dist, best_sig["price_a"] + sl_dist * 3.5,
                                signal_id=signal_id
                            ):
                                order_type_b, side_b, price_b, sl_sign_b = get_hedge_execution_parameters(best_action, best_sig["beta"], best_sig["tick_b"])
                                sl_b = price_b + sl_sign_b * sl_dist_b
                                if best_cat_b == "crypto":
                                    hedge_params = {"symbol": S_B, "side": side_b, "type": "MARKET", "quantity": qty_b}
                                    h_res = send_signed_request("POST", "/fapi/v1/order", hedge_params)
                                    if h_res and h_res.status_code == 200:
                                        avg_price_b = float(h_res.json().get("avgPrice") or price_b)
                                        log_trade_entry(h_res.json()["orderId"], S_B, side_b, qty_b, avg_price_b, datetime.datetime.now(), "Binance JS_HEDGE", signal_id)
                                        price_prec = get_symbol_filters(S_B)["pricePrecision"] if get_symbol_filters(S_B) else 2
                                        opp_side_b = "BUY" if side_b == "SELL" else "SELL"
                                        send_signed_request("POST", "/fapi/v1/order", {"symbol": S_B, "side": opp_side_b, "type": "STOP_MARKET", "stopPrice": round(sl_b, price_prec), "closePosition": "true", "timeInForce": "GTC"})
                                else:
                                    res_hedge = send_order(S_B, order_type_b, price_b, qty_b, sl_b, 0.0, "JS_HEDGE")
                                    if res_hedge and res_hedge.retcode == mt5.TRADE_RETCODE_DONE:
                                        log_trade_entry(res_hedge.order, S_B, side_b, qty_b, res_hedge.price, datetime.datetime.now(), "JS_HEDGE", signal_id)
                        else:
                            lots_a = DEFAULT_LOTS if DEFAULT_LOTS > 0.005 else DEFAULT_LOT_SIZES.get(best_cat_a, 0.15)
                            # Apply 3-part safeguard scaling correction
                            info_a_check = mt5.symbol_info(S_A)
                            min_vol_a = info_a_check.volume_min if info_a_check else 0.01
                            part_lots_a = round(lots_a / 3.0, 2)
                            if part_lots_a < min_vol_a:
                                part_lots_a = min_vol_a
                            actual_lots_a = part_lots_a * 3.0
                            
                            qty_b = get_hedge_quantity(S_A, S_B, actual_lots_a, best_sig["beta"], best_cat_a, best_cat_b)
                            
                            if execute_three_part_trade(
                                S_A, True, best_sig["tick_a"].ask, best_sig["tick_a"].ask - sl_dist, lots_a,
                                best_sig["price_a"] + sl_dist, best_sig["price_a"] + tp_dist, best_sig["price_a"] + sl_dist * 3.5,
                                signal_id=signal_id
                            ):
                                order_type_b, side_b, price_b, sl_sign_b = get_hedge_execution_parameters(best_action, best_sig["beta"], best_sig["tick_b"])
                                sl_b = price_b + sl_sign_b * sl_dist_b
                                if best_cat_b == "crypto":
                                    hedge_params = {"symbol": S_B, "side": side_b, "type": "MARKET", "quantity": qty_b}
                                    h_res = send_signed_request("POST", "/fapi/v1/order", hedge_params)
                                    if h_res and h_res.status_code == 200:
                                        avg_price_b = float(h_res.json().get("avgPrice") or price_b)
                                        log_trade_entry(h_res.json()["orderId"], S_B, side_b, qty_b, avg_price_b, datetime.datetime.now(), "Binance JS_HEDGE", signal_id)
                                        price_prec = get_symbol_filters(S_B)["pricePrecision"] if get_symbol_filters(S_B) else 2
                                        opp_side_b = "BUY" if side_b == "SELL" else "SELL"
                                        send_signed_request("POST", "/fapi/v1/order", {"symbol": S_B, "side": opp_side_b, "type": "STOP_MARKET", "stopPrice": round(sl_b, price_prec), "closePosition": "true", "timeInForce": "GTC"})
                                else:
                                    res_hedge = send_order(S_B, order_type_b, price_b, qty_b, sl_b, 0.0, "JS_HEDGE")
                                    if res_hedge and res_hedge.retcode == mt5.TRADE_RETCODE_DONE:
                                        log_trade_entry(res_hedge.order, S_B, side_b, qty_b, res_hedge.price, datetime.datetime.now(), "JS_HEDGE", signal_id)
                    else:
                        if best_cat_a == "crypto":
                            usdt_bal, _ = get_binance_usdt_balance()
                            qty_a = calculate_binance_quantity(S_A, sl_dist, usdt_bal)
                            qty_b = get_hedge_quantity(S_A, S_B, qty_a, best_sig["beta"], best_cat_a, best_cat_b)
                            
                            if execute_three_part_binance_trade(
                                S_A, False, best_sig["tick_a"].bid, best_sig["tick_a"].bid + sl_dist, qty_a,
                                best_sig["price_a"] - sl_dist, best_sig["price_a"] - tp_dist, best_sig["price_a"] - sl_dist * 3.5,
                                signal_id=signal_id
                            ):
                                order_type_b, side_b, price_b, sl_sign_b = get_hedge_execution_parameters(best_action, best_sig["beta"], best_sig["tick_b"])
                                sl_b = price_b + sl_sign_b * sl_dist_b
                                if best_cat_b == "crypto":
                                    hedge_params = {"symbol": S_B, "side": side_b, "type": "MARKET", "quantity": qty_b}
                                    h_res = send_signed_request("POST", "/fapi/v1/order", hedge_params)
                                    if h_res and h_res.status_code == 200:
                                        avg_price_b = float(h_res.json().get("avgPrice") or price_b)
                                        log_trade_entry(h_res.json()["orderId"], S_B, side_b, qty_b, avg_price_b, datetime.datetime.now(), "Binance JS_HEDGE", signal_id)
                                        price_prec = get_symbol_filters(S_B)["pricePrecision"] if get_symbol_filters(S_B) else 2
                                        opp_side_b = "BUY" if side_b == "SELL" else "SELL"
                                        send_signed_request("POST", "/fapi/v1/order", {"symbol": S_B, "side": opp_side_b, "type": "STOP_MARKET", "stopPrice": round(sl_b, price_prec), "closePosition": "true", "timeInForce": "GTC"})
                                else:
                                    res_hedge = send_order(S_B, order_type_b, price_b, qty_b, sl_b, 0.0, "JS_HEDGE")
                                    if res_hedge and res_hedge.retcode == mt5.TRADE_RETCODE_DONE:
                                        log_trade_entry(res_hedge.order, S_B, side_b, qty_b, res_hedge.price, datetime.datetime.now(), "JS_HEDGE", signal_id)
                        else:
                            lots_a = DEFAULT_LOTS if DEFAULT_LOTS > 0.005 else DEFAULT_LOT_SIZES.get(best_cat_a, 0.15)
                            # Apply 3-part safeguard scaling correction
                            info_a_check = mt5.symbol_info(S_A)
                            min_vol_a = info_a_check.volume_min if info_a_check else 0.01
                            part_lots_a = round(lots_a / 3.0, 2)
                            if part_lots_a < min_vol_a:
                                part_lots_a = min_vol_a
                            actual_lots_a = part_lots_a * 3.0
                            
                            qty_b = get_hedge_quantity(S_A, S_B, actual_lots_a, best_sig["beta"], best_cat_a, best_cat_b)
                            
                            if execute_three_part_trade(
                                S_A, False, best_sig["tick_a"].bid, best_sig["tick_a"].bid + sl_dist, lots_a,
                                best_sig["price_a"] - sl_dist, best_sig["price_a"] - tp_dist, best_sig["price_a"] - sl_dist * 3.5,
                                signal_id=signal_id
                            ):
                                order_type_b, side_b, price_b, sl_sign_b = get_hedge_execution_parameters(best_action, best_sig["beta"], best_sig["tick_b"])
                                sl_b = price_b + sl_sign_b * sl_dist_b
                                if best_cat_b == "crypto":
                                    hedge_params = {"symbol": S_B, "side": side_b, "type": "MARKET", "quantity": qty_b}
                                    h_res = send_signed_request("POST", "/fapi/v1/order", hedge_params)
                                    if h_res and h_res.status_code == 200:
                                        avg_price_b = float(h_res.json().get("avgPrice") or price_b)
                                        log_trade_entry(h_res.json()["orderId"], S_B, side_b, qty_b, avg_price_b, datetime.datetime.now(), "Binance JS_HEDGE", signal_id)
                                        price_prec = get_symbol_filters(S_B)["pricePrecision"] if get_symbol_filters(S_B) else 2
                                        opp_side_b = "BUY" if side_b == "SELL" else "SELL"
                                        send_signed_request("POST", "/fapi/v1/order", {"symbol": S_B, "side": opp_side_b, "type": "STOP_MARKET", "stopPrice": round(sl_b, price_prec), "closePosition": "true", "timeInForce": "GTC"})
                                else:
                                    res_hedge = send_order(S_B, order_type_b, price_b, qty_b, sl_b, 0.0, "JS_HEDGE")
                                    if res_hedge and res_hedge.retcode == mt5.TRADE_RETCODE_DONE:
                                        log_trade_entry(res_hedge.order, S_B, side_b, qty_b, res_hedge.price, datetime.datetime.now(), "JS_HEDGE", signal_id)
                    invalidate_trades_cache()

            # Trail Stop Loss if active
            best_cat_a_check = get_symbol_category(S_A)
            if best_cat_a_check != "crypto" and len(active_js_positions) > 0:
                leg_a_parts = [p for p in active_js_positions if p.symbol == S_A]
                comments = [p.comment for p in leg_a_parts]
                if not any("JS_TP1" in c for c in comments) and leg_a_parts:
                    modify_sl_for_trade(S_A, leg_a_parts[0].price_open)

            # Update dashboard status
            if is_news_halted:
                status_str = f"HALTED ({news_msg})"
            elif low_correlation_warning:
                status_str = "RUNNING (Warning: Low Correlation)"
            else:
                status_str = "RUNNING (Active)" if AUTO_EXECUTE else "RUNNING (Signals Only)"
            
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
            )

            if loop_log_counter % 15 == 0:
                logger.info(
                    f"[LIVE SCAN] Active: {S_A}/{S_B} | Z-Score: {active_pair_z_score:.3f} "
                    f"| Z-Velocity: {active_pair_velocity:.3f} | OBI A/B: {active_pair_obi_a:.1f}/{active_pair_obi_b:.1f} "
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
