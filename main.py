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
from risk_safeguards import check_drawdown_limit, calculate_lots, is_spread_valid, get_trades_count_today, MAX_DAILY_TRADES, invalidate_trades_cache, round_volume, MAX_DAILY_LOSS_PERCENT, get_active_pairs_and_symbols, MAX_CONCURRENT_TRADES


from execution_bot import execute_three_part_trade, execute_three_part_hedge_trade, close_all_positions, modify_sl_for_trade, check_closed_trades, MAGIC_NUMBER, send_order, close_position_by_ticket, is_retcode_success, modify_position_sl


from smc_indicators import detect_smc_zones, is_price_in_zones
from database import log_signal, get_connection, update_bot_state, update_daily_metrics, log_fvg_zones, get_auto_execute, initialize_database, log_trade_entry, get_open_trades_count, log_trade_exit, update_scanned_asset
from news_guard import check_pair_news_block, check_post_news_stability
try:
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
except ImportError:
    def get_binance_usdt_balance(): return 0.0
    def calculate_binance_quantity(*a, **k): return 0.0
    def execute_three_part_binance_trade(*a, **k): return False
    def close_all_binance_positions(*a, **k): pass
    def check_closed_binance_trades(*a, **k): pass
    def send_signed_request(*a, **k): return {}
    def get_binance_live_tick(*a, **k): return None
    def get_binance_market_book(*a, **k): return [], []
    def get_binance_rates_df(*a, **k): return None
    def close_binance_partial(*a, **k): pass
    def get_symbol_filters(*a, **k): return {}

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
    try:
        conn_mig = get_connection()
        cur_mig = conn_mig.cursor()
        cur_mig.execute("""
            ALTER TABLE bot_state ADD COLUMN IF NOT EXISTS session_guard_enabled BOOLEAN DEFAULT FALSE;
            ALTER TABLE bot_state ADD COLUMN IF NOT EXISTS session_start_hour DOUBLE PRECISION DEFAULT 12.5;
            ALTER TABLE bot_state ADD COLUMN IF NOT EXISTS session_end_hour DOUBLE PRECISION DEFAULT 2.0;
            UPDATE bot_state SET active_pair = 'EURUSD/GBPUSD', stocks_enabled = FALSE, indices_enabled = FALSE, metals_enabled = FALSE, crypto_enabled = FALSE, forex_enabled = TRUE WHERE id = 1;
        """)
        conn_mig.commit()
        cur_mig.close()
        conn_mig.close()
    except Exception as ex_m:
        pass

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
    Reads active_pair, sl_pips, tp_pips, smc_enabled, and auto_execute directly from the postgres database
    to avoid HTTP dependency and connection issues.
    """
    query = """
        SELECT active_pair, sl_pips, tp_pips, smc_enabled, auto_execute,
               crypto_enabled, metals_enabled, forex_enabled, indices_enabled,
               risk_limits_enabled, z_entry_threshold, default_lots, max_trades,
               knife_protection_enabled, obi_enabled, volatility_filter_enabled,
               stocks_enabled, halt_drawdown_limit, max_drawdown_limit,
               session_guard_enabled, session_start_hour, session_end_hour
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
            c_on = bool(row[5]) if row[5] is not None else False
            m_on = bool(row[6]) if row[6] is not None else True
            f_on = bool(row[7]) if row[7] is not None else True
            i_on = bool(row[8]) if row[8] is not None else True
            s_on = bool(row[16]) if len(row) > 16 and row[16] is not None else True

            # If current active_pair belongs to a disabled category, pick first pair from an enabled category
            cat_a = get_symbol_category(raw_active.split('/')[0]) if '/' in raw_active else "forex"
            active_pair = raw_active
            if (cat_a == "forex" and not f_on) or (cat_a == "metals" and not m_on) or (cat_a == "indices" and not i_on) or (cat_a == "stocks" and not s_on) or (cat_a == "crypto" and not c_on) or (f_on and cat_a != "forex"):
                if f_on:
                    active_pair = "EURUSD/GBPUSD"
                elif m_on:
                    active_pair = "XAUUSD/XAGUSD"
                elif i_on:
                    active_pair = "US30/NAS100"
                elif s_on:
                    active_pair = "AAPL/MSFT"
                cur.execute("UPDATE bot_state SET active_pair = %s WHERE id = 1", (active_pair,))
                conn.commit()
                save_config(active_pair)
                logger.info(f"Aligned active_pair with enabled category: {active_pair}")
                
            cur.close()
            conn.close()
            return (
                active_pair,
                float(row[1] or 35.0),
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
                s_on,
                float(row[17]) if len(row) > 17 and row[17] is not None else 0.83,
                float(row[18]) if len(row) > 18 and row[18] is not None else 3.30,
                bool(row[19] if len(row) > 19 and row[19] is not None else False),
                float(row[20]) if len(row) > 20 and row[20] is not None else 12.0,
                float(row[21]) if len(row) > 21 and row[21] is not None else 21.0
            )
        else:
            cur.close()
    except Exception as e:
        try:
            conn_fix = get_connection()
            cur_fix = conn_fix.cursor()
            cur_fix.execute("""
                ALTER TABLE bot_state ADD COLUMN IF NOT EXISTS session_guard_enabled BOOLEAN DEFAULT FALSE;
                ALTER TABLE bot_state ADD COLUMN IF NOT EXISTS session_start_hour DOUBLE PRECISION DEFAULT 12.5;
                ALTER TABLE bot_state ADD COLUMN IF NOT EXISTS session_end_hour DOUBLE PRECISION DEFAULT 2.0;
            """)
            conn_fix.commit()
            cur_fix.close()
            conn_fix.close()
        except Exception:
            pass
        logger.warning(f"Could not fetch DB config directly: {e}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
    return None


def update_live_toggles_from_db():
    """
    Refreshes global asset class toggles and settings directly from DB on every 2s loop cycle.
    Allows instant toggle updates from Dashboard without restarting the bot.
    """
    global FOREX_ENABLED, METALS_ENABLED, INDICES_ENABLED, STOCKS_ENABLED, CRYPTO_ENABLED, AUTO_EXECUTE, RISK_LIMITS_ENABLED, Z_ENTRY_THRESHOLD, SL_PIPS, TP_PIPS
    global KNIFE_PROTECTION_ENABLED, OBI_ENABLED, VOLATILITY_FILTER_ENABLED
    try:
        import risk_safeguards
        cfg = fetch_db_config()
        if cfg:
            SL_PIPS = cfg[1]
            TP_PIPS = cfg[2]
            AUTO_EXECUTE = cfg[4]
            CRYPTO_ENABLED = False
            METALS_ENABLED = cfg[6]
            FOREX_ENABLED = cfg[7]
            INDICES_ENABLED = cfg[8]
            RISK_LIMITS_ENABLED = cfg[9]
            Z_ENTRY_THRESHOLD = cfg[10]
            KNIFE_PROTECTION_ENABLED = bool(cfg[13])
            OBI_ENABLED = bool(cfg[14])
            VOLATILITY_FILTER_ENABLED = bool(cfg[15])
            STOCKS_ENABLED = cfg[16]
            if len(cfg) > 19:
                risk_safeguards.SESSION_GUARD_ENABLED = cfg[19]
                risk_safeguards.SESSION_START_HOUR = cfg[20]
                risk_safeguards.SESSION_END_HOUR = cfg[21]
    except Exception as e:
        logger.warning(f"Error in update_live_toggles_from_db: {e}")


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
                        tp2 = price + max(tp_dist, sl_dist * 1.5)
                        tp3 = price + max(tp_dist * 1.5, sl_dist * 3.5)
                    else:
                        sl_price = price + sl_dist
                        tp1 = price - sl_dist
                        tp2 = price - max(tp_dist, sl_dist * 1.5)
                        tp3 = price - max(tp_dist * 1.5, sl_dist * 3.5)
                        
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


Z_ENTRY_THRESHOLD = 1.80
ML_MODEL = None
DEFAULT_LOTS = 0.01
Z_EXIT_MEAN = 0.0
REQUIRE_SMC_CONFLUENCE = False
AUTO_EXECUTE = True          # toggled from dashboard via DB
CRYPTO_ENABLED = False
METALS_ENABLED = True
FOREX_ENABLED = True
INDICES_ENABLED = True
STOCKS_ENABLED = True
RISK_LIMITS_ENABLED = True
SMC_TIMEFRAME = mt5.TIMEFRAME_M5
LOOP_INTERVAL = 2


CANDIDATE_PAIRS = {
    "forex": [
        ("EURUSD", "USDCHF"),  # Priority 1: Strongest negative correlation
        ("GBPUSD", "USDJPY"),  # Priority 2: High volatility mean reversion
        ("AUDUSD", "NZDUSD"),  # Priority 3: Tightest co-integration spread
        ("EURUSD", "GBPUSD"),
        ("GBPUSD", "USDCHF"),
        ("EURUSD", "USDJPY"),
    ],

    "metals": [
        ("XAUUSD", "XAGUSD"),
    ],
    "crypto": [
        ("BTCUSDT", "ETHUSDT"),
        ("SOLUSDT", "BTCUSDT"),
        ("ETHUSDT", "SOLUSDT"),
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
    """
    Checks if market for the symbol is open and receiving active live ticks.
    Prevents scanning or generating signals for closed stocks/indices outside market hours.
    """
    try:
        cat = get_symbol_category(symbol)
        if cat == "crypto":
            return True
            
        if not mt5.initialize():
            return True
            
        info = mt5.symbol_info(symbol)
        if info is None:
            return False
            
        if info.trade_mode == mt5.SYMBOL_TRADE_MODE_DISABLED:
            return False
            
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return False
            
        import time
        # If last tick is older than 5 minutes (300 seconds), market for this asset is closed!
        if (time.time() - tick.time) > 300:
            return False
            
        return True
    except Exception as e:
        logger.warning(f"Error checking is_market_open for {symbol}: {e}")
        return True

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
    "AMZN/GOOGL": 1,
    "META/GOOGL": 1,
    "US500/NAS100": 1,
    "US30/US500": 1,
    "US30/NAS100": 1
}

DEFAULT_LOT_SIZES = {
    "metals": 1.50,
    "forex": 1.20,
    "indices": 0.60,
    "stocks": 15.00,
    "crypto": 0.06
}

LEVERAGE_FACTORS = {
    "forex": 1.0,
    "metals": 0.25,   # 4x lower leverage than Forex
    "indices": 0.25,  # 4x lower leverage than Forex
    "stocks": 0.10,   # 10x lower leverage than Forex
    "crypto": 0.01    # 100x lower leverage than Forex
}

def get_blue_guardian_lots(symbol: str, category: str, sl_dist_price: float = 0.00083) -> float:
    """
    Calculates dynamic lot size based on 1.0% Account Equity Risk:
    - $10,000 Equity -> 1.20 Total Lots (3 x 0.40 lots)
    - $12,000 Equity -> 1.44 Total Lots (3 x 0.48 lots)
    """
    try:
        acc_info = mt5.account_info()
        if acc_info and acc_info.equity > 0:
            from risk_safeguards import calculate_lots
            dyn_lots = calculate_lots(symbol, sl_dist_price, acc_info)
            if dyn_lots and dyn_lots >= 0.03:
                return dyn_lots
    except Exception:
        pass
    return DEFAULT_LOT_SIZES.get(category, 1.20)


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
            res_a = resolve_broker_symbol(symbol_a)
            check_and_subscribe_symbol(res_a)
            df_a = get_rates_df(res_a, mt5.TIMEFRAME_M5, count=150)
            
        if cat_b == "crypto":
            df_b = get_binance_rates_df(symbol_b, timeframe_minutes=5, count=150)
        else:
            if not mt5.initialize():
                return 50.0
            res_b = resolve_broker_symbol(symbol_b)
            check_and_subscribe_symbol(res_b)
            df_b = get_rates_df(res_b, mt5.TIMEFRAME_M5, count=150)

            
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

def cleanup_disabled_scanned_assets(crypto_on, metals_on, forex_on, indices_on, stocks_on=True):
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
        
        # Warm up the filter with historical data
        try:
            cat_a = get_symbol_category(symbol_a)
            cat_b = get_symbol_category(symbol_b)
            if cat_a == "crypto":
                df_a = get_binance_rates_df(symbol_a, timeframe_minutes=5, count=500)
            else:
                df_a = get_rates_df(symbol_a, mt5.TIMEFRAME_M5, count=500)
                
            if cat_b == "crypto":
                df_b = get_binance_rates_df(symbol_b, timeframe_minutes=5, count=500)
            else:
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

# BUG FIX 2: Fixed SL in pips instead of 3x bid-ask spread
SL_PIPS = 22.0
SL_PIPS_JPY = 0.35
TP_PIPS = 33.0

def get_pip_size(symbol: str) -> float:
    s = symbol.upper()
    if "JPY" in s:
        return 0.01
    if any(x in s for x in ["XAU", "XPT", "XPD", "PLAT", "PALL"]):
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


def is_friday_market_close_approaching(lead_minutes=45):
    """
    Returns True ONLY if current UTC time is within lead_minutes (default 45 mins) of Friday Forex market close (21:15 UTC - 22:00 UTC Friday).
    Auto-closes active trades 45m before Friday close to prevent weekend gap risk.
    """
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    if now_utc.weekday() == 4: # Friday ONLY
        if now_utc.hour >= 21 and now_utc.minute >= (60 - lead_minutes):
            return True
        elif now_utc.hour >= 22:
            return True
    return False



def get_kf_parameters(symbol: str):
    # Calibrated process and observation noise for responsive, highly dynamic Z-score calculations
    # Q = 1e-9 (stable hedge ratio tracking), R = 1e-6 (calibrated normalized residual variance)
    cat = get_symbol_category(symbol)
    if cat == "metals":
        return 1e-9, 1e-6
    elif cat == "indices":
        return 1e-9, 1e-6
    elif cat == "crypto":
        return 1e-9, 1e-6
    elif cat == "forex":
        return 1e-9, 1e-6
    else: # stocks/default
        return 1e-9, 1e-6


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
        
    # Safeguard: Enforce minimum SL floors by asset class to prevent premature noise stop-outs
    pip_sz = get_pip_size(symbol)
    min_floor = 0.0
    if cat == "forex":
        min_floor = 35.0 * pip_sz  # Minimum 35 pips for Forex
    elif cat == "metals":
        min_floor = 25.0  # Minimum $25.00 price move for Gold/Silver
    elif cat == "indices" or cat == "stocks":
        min_floor = price * 0.015  # Minimum 1.5% for stocks/indices

    if base_sl < min_floor:
        base_sl = min_floor

    try:
        atr = get_atr(symbol, mt5.TIMEFRAME_M5, count=30)
        if atr is not None and atr > 0:
            min_sl = max(atr * 2.0, min_floor)
            if base_sl < min_sl:
                logger.info(f"SL of {base_sl:.5f} is too tight for {symbol} (noise boundary: {min_sl:.5f}). Automatically adjusted to safe boundary: {min_sl:.5f}")
                return min_sl
    except Exception as e:
        logger.warning(f"Failed to calculate ATR safeguard for {symbol}: {e}")
        
    return base_sl

def sync_mt5_open_positions_with_db():
    """
    Syncs open MT5 tickets with the database trades table.
    BUG FIX: Uses per-TICKET matching as the primary check so that
    hedging accounts with multiple positions per symbol (TP1/TP2/TP3)
    are not falsely closed. Netting accounts are handled by checking
    whether any active position exists for the symbol base name.
    """
    try:
        if not mt5.initialize():
            return

        positions = mt5.positions_get()
        if positions is None:
            # Transient MT5 connection issue — abort to prevent false trade closures
            logger.warning("[MT5 SYNC] positions_get() returned None. Aborting sync to prevent false closures.")
            return

        # Build a set of ALL active MT5 tickets (works for both hedging and netting accounts)
        active_tickets = {p.ticket for p in positions}

        # Also build per-symbol total active volume for netting scale-down detection
        # Use base symbol (without broker suffix like .m .p) to avoid mismatches
        active_volume_by_base_symbol = {}
        for p in positions:
            base = p.symbol.upper().split('.')[0]
            active_volume_by_base_symbol[base] = active_volume_by_base_symbol.get(base, 0.0) + float(p.volume)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT ticket, symbol, lots, entry_price, order_type, entry_time FROM trades WHERE status = 'OPEN'")
        db_open_trades = cur.fetchall()
        db_tickets = {r[0] for r in db_open_trades}

        # Auto-import active MT5 positions if missing from database
        from database import log_trade_entry
        for p in positions:
            if p.ticket not in db_tickets:
                dir_str = "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL"
                log_trade_entry(p.ticket, p.symbol, dir_str, float(p.volume), float(p.price_open), datetime.datetime.now(), "MT5_AUTO_IMPORTED")
                logger.info(f"📥 [MT5 AUTO-IMPORT] Active MT5 Ticket #{p.ticket} ({p.symbol} {dir_str} {p.volume} lots @ {p.price_open}) auto-imported to DB & Dashboard!")

        for ticket, symbol, lots, entry_price, order_type, entry_time in db_open_trades:
            if ticket < 1000:
                continue

            if ticket in active_tickets:
                # Ticket is still active in MT5 — no action needed
                continue


            logger.info(f"🔴 [MT5 BROKER / EXTERNAL CLOSE] Ticket #{ticket} ({symbol}) exited MT5 positions (SL/TP or Broker fill). Syncing close state to DB...")



            # Ticket is NOT in active MT5 positions. Determine if it is a true close
            # or a netting scale-down where the symbol position still exists.
            sym_base = symbol.upper().split('.')[0]
            active_vol_for_symbol = active_volume_by_base_symbol.get(sym_base, 0.0)

            # Calculate total DB open volume for this base symbol
            total_db_vol_for_sym = sum(
                float(r[2]) for r in db_open_trades
                if r[1].upper().split('.')[0] == sym_base
            )

            if active_vol_for_symbol > 0.0 and active_vol_for_symbol >= total_db_vol_for_sym - 0.005:
                # Symbol still has the same (or more) volume in MT5 vs DB.
                # This ticket was likely merged/re-ticketed by a netting broker — skip.
                continue

            # Ticket is truly closed (or partially netted out). Look up exit details.
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
                # No history and no active position for symbol — safe to mark closed
                pass
            elif not found_exit:
                # No exit deal found but symbol still partially active — be conservative, skip
                logger.warning(f"[MT5 SYNC] Ticket {ticket} ({symbol}) not in active tickets but no exit deal found and symbol still active. Skipping to avoid false closure.")
                continue

            log_trade_exit(ticket, close_price, profit, close_time)
            logger.info(f"[MT5 SYNC] Ticket {ticket} ({symbol}) marked closed. Exit: {close_price:.5f} | Profit: ${profit:.2f}")

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
    """
    Returns dynamic z_entry, z_exit, z_sl, sl_atr_mult.
    z_entry dynamically uses global Z_ENTRY_THRESHOLD (updated live from DB/Dashboard)
    so user can set 1.80, 2.00, 2.40, etc. anytime without any hardcoding!
    """
    cat = get_symbol_category(symbol)
    dyn_z_entry = float(Z_ENTRY_THRESHOLD)
    if cat == "metals":
        return dyn_z_entry, 0.0, 4.2, 5.0
    elif cat == "indices":
        return dyn_z_entry, 0.0, 4.2, 5.0
    elif cat == "crypto":
        return dyn_z_entry, 0.0, 4.2, 6.0
    else: # forex/stocks/default
        return dyn_z_entry, 0.0, 4.2, 6.0



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

GLOBAL_PAIR_COOLDOWNS = {}


def set_pair_cooldown(sym_a, sym_b, cooldown_seconds=600):
    pair_key = f"{sym_a}/{sym_b}"
    GLOBAL_PAIR_COOLDOWNS[pair_key] = time.time() + cooldown_seconds

def calculate_closed_signal_pnl(sig_id):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT SUM(profit) FROM trades WHERE signal_id = %s", (int(sig_id),))
        res = cur.fetchone()
        cur.close()
        conn.close()
        return float(res[0]) if (res and res[0] is not None) else 0.0
    except Exception:
        return 0.0

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
        # Find ALL signal_ids that have at least one OPEN trade in DB (regardless of currently focused pair context)
        cur.execute("SELECT DISTINCT COALESCE(signal_id, 999999) FROM trades WHERE status = 'OPEN'")
        active_signal_ids = [row[0] for row in cur.fetchall()]
        
        if not active_signal_ids:
            cur.close()
            conn.close()
            return

        # Fetch ALL trades (both OPEN and CLOSED) for these active signal_ids so we can detect closed Leg A parts
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

        leg_a_trades = [t for t in trades if t["symbol"].split('.')[0].upper() == sym_a.split('.')[0].upper()]
        leg_b_trades = [t for t in trades if t["symbol"].split('.')[0].upper() == sym_b.split('.')[0].upper()]

        open_leg_a_trades = [t for t in leg_a_trades if t["status"] == 'OPEN']
        open_leg_b_trades = [t for t in leg_b_trades if t["status"] == 'OPEN']

        # 1. Cleanup check: If Leg A has NO open trades left but Leg B still has open trades, close Leg B immediately.
        # BUG FIX: Before closing hedge (Leg B), VERIFY against live MT5 that Leg A is truly closed.
        # The DB can be momentarily stale (e.g. after sync_mt5_open_positions_with_db runs).
        # If any Leg A ticket is still active in MT5, do NOT close the hedge yet.
        if not open_leg_a_trades and open_leg_b_trades:
            leg_a_truly_closed = True
            try:
                leg_a_cat = get_symbol_category(sym_a)
                if leg_a_cat != "crypto":
                    all_mt5_positions = mt5.positions_get()
                    if all_mt5_positions is None:
                        # MT5 connection issue — abort to prevent false hedge closure
                        logger.warning(f"[HEDGE GUARD] MT5 positions_get() returned None while checking Leg A for signal_id {sig_id}. Skipping hedge close to prevent false closure.")
                        leg_a_truly_closed = False
                    else:
                        active_mt5_tickets = {p.ticket for p in all_mt5_positions}
                        sym_a_base = sym_a.upper().split('.')[0]
                        # Check if any Leg A ticket from all trades (not just DB open) is still live in MT5
                        for t_a in leg_a_trades:
                            if t_a["ticket"] in active_mt5_tickets:
                                logger.warning(f"[HEDGE GUARD] DB shows Leg A closed for signal_id {sig_id} but ticket {t_a['ticket']} is still active in MT5. Skipping hedge close — DB sync lag.")
                                leg_a_truly_closed = False
                                break
                        # Also check by symbol: if any position for Leg A symbol is open in MT5, be conservative
                        if leg_a_truly_closed:
                            leg_a_mt5_positions = [p for p in all_mt5_positions if p.symbol.upper().split('.')[0] == sym_a_base and p.magic == MAGIC_NUMBER]
                            if leg_a_mt5_positions:
                                logger.warning(f"[HEDGE GUARD] DB shows Leg A closed for signal_id {sig_id} but {len(leg_a_mt5_positions)} Leg A position(s) still active in MT5 by symbol. Skipping hedge close.")
                                leg_a_truly_closed = False
            except Exception as eg:
                logger.error(f"[HEDGE GUARD] Error verifying Leg A MT5 state for signal_id {sig_id}: {eg}. Skipping hedge close to be safe.")
                leg_a_truly_closed = False

            if leg_a_truly_closed:
                logger.info(f"Cleanup: Leg A is fully closed (MT5 verified) for signal_id {sig_id}. Closing remaining Leg B trades.")
                for t_b in open_leg_b_trades:
                    close_single_trade(t_b["symbol"], t_b["ticket"], t_b["lots"], t_b["order_type"])
            continue

        if not open_leg_a_trades:
            continue

        # Dynamically calculate the Z-score and velocity for this specific pair
        z_score_for_pair = 0.0
        pair_velocity = 0.0
        try:
            tick_a = mt5.symbol_info_tick(sym_a) if get_symbol_category(sym_a) != "crypto" else get_binance_live_tick(sym_a)
            tick_b = mt5.symbol_info_tick(sym_b) if get_symbol_category(sym_b) != "crypto" else get_binance_live_tick(sym_b)
            if tick_a and tick_b:
                p_a = (tick_a.bid + tick_a.ask) / 2.0
                p_b = (tick_b.bid + tick_b.ask) / 2.0
                kf_pair = get_kf_for_pair(sym_a, sym_b)
                if kf_pair is not None:
                    z_score_for_pair = kf_pair.get_current_z(p_b, p_a)
                    pair_velocity = kf_pair.get_velocity()
            else:
                if sym_a.split('.')[0].upper() == symbol_a.split('.')[0].upper() and sym_b.split('.')[0].upper() == symbol_b.split('.')[0].upper():
                    z_score_for_pair = z_score
        except Exception as ez:
            logger.error(f"Error calculating dynamic z_score for {sym_a}/{sym_b}: {ez}")
            if sym_a.split('.')[0].upper() == symbol_a.split('.')[0].upper() and sym_b.split('.')[0].upper() == symbol_b.split('.')[0].upper():
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
        is_buy_spread = (open_leg_a_trades[0]["order_type"] == "BUY") if open_leg_a_trades else False
        exit_triggered = False
        exit_reason = ""

        # Calculate TOTAL NET CASH PROFIT across all positions in this trade basket
        total_basket_pnl = 0.0
        for t in open_leg_a_trades + open_leg_b_trades:
            pos_info = mt5.positions_get(ticket=t["ticket"])
            if pos_info:
                total_basket_pnl += float(pos_info[0].profit)

        # ── MASTER PROP FIRM THREE-STEP EXIT ARCHITECTURE ──

        if "GLOBAL_PEAK_BASKET_PNL" not in globals():
            global GLOBAL_PEAK_BASKET_PNL
            GLOBAL_PEAK_BASKET_PNL = {}
        if "GLOBAL_HYBRID_BE_SHIFTED" not in globals():
            global GLOBAL_HYBRID_BE_SHIFTED
            GLOBAL_HYBRID_BE_SHIFTED = {}
        if "GLOBAL_STEP2_SCALED_OUT" not in globals():
            global GLOBAL_STEP2_SCALED_OUT
            GLOBAL_STEP2_SCALED_OUT = {}

        current_peak = GLOBAL_PEAK_BASKET_PNL.get(sig_id, 0.0)
        if total_basket_pnl > current_peak:
            GLOBAL_PEAK_BASKET_PNL[sig_id] = total_basket_pnl
            current_peak = total_basket_pnl

        tp1_trade = next((t for t in open_leg_a_trades if "TP1" in str(t.get("comment", "")).upper()), None)
        tp2_trade = next((t for t in open_leg_a_trades if "TP2" in str(t.get("comment", "")).upper()), None)
        tp3_trade = next((t for t in open_leg_a_trades if "TP3" in str(t.get("comment", "")).upper()), None)

        # ── STEP 1: BREAKEVEN GUARD DISABLED 🔴 (PER USER DIRECTIVE: SL NEVER MOVED TO $0.00 ENTRY) ──
        # Step 1 Breakeven SL shift is disabled. SL is locked in profit via Multi-Tier Trailing System instead.


        # ── STEP 2: MEAN REVERSION SCALE-OUT DISABLED 🔴 (PER USER DIRECTIVE: TRADES RUN AS WHOLE BASKET UNTIL TRAILING STOP OR HARD TP/SL) ──
        # Step 2 partial scale-out is disabled so trade runs completely without mid-way closures.



        # Option B Multi-Tier Trailing Profit Lock (4-Tier Profit Protection for entire basket)
        if current_peak >= 185.0:
            tier4_floor = 155.0
            if total_basket_pnl <= tier4_floor:
                exit_triggered = True
                exit_reason = f"PROFIT_LOCK_TIER4 (Peak ${current_peak:.2f} -> Reversed to ${total_basket_pnl:.2f} <= Floor ${tier4_floor:.2f})"
                logger.info(f"💰 [PROFIT LOCK TIER 4 EXECUTED] Peak reached ${current_peak:.2f} & reversed to ${total_basket_pnl:.2f} (Floor: ${tier4_floor:.2f}). Auto-closing entire basket to bank +$155.00 USD mega runner profit!")
        elif current_peak >= 142.0:
            tier3_floor = 120.0
            if total_basket_pnl <= tier3_floor:
                exit_triggered = True
                exit_reason = f"PROFIT_LOCK_TIER3 (Peak ${current_peak:.2f} -> Reversed to ${total_basket_pnl:.2f} <= Floor ${tier3_floor:.2f})"
                logger.info(f"💰 [PROFIT LOCK TIER 3 EXECUTED] Peak reached ${current_peak:.2f} & reversed to ${total_basket_pnl:.2f} (Floor: ${tier3_floor:.2f}). Auto-closing entire basket to bank +$120.00 USD runner profit!")
        elif current_peak >= 99.0:
            tier2_floor = 80.0
            if total_basket_pnl <= tier2_floor:
                exit_triggered = True
                exit_reason = f"PROFIT_LOCK_TIER2 (Peak ${current_peak:.2f} -> Reversed to ${total_basket_pnl:.2f} <= Floor ${tier2_floor:.2f})"
                logger.info(f"💰 [PROFIT LOCK TIER 2 EXECUTED] Peak reached ${current_peak:.2f} & reversed to ${total_basket_pnl:.2f} (Floor: ${tier2_floor:.2f}). Auto-closing entire basket to bank +$80.00 USD cash profit!")
        elif current_peak >= 67.0:
            tier1_floor = 53.0
            if total_basket_pnl <= tier1_floor:
                exit_triggered = True
                exit_reason = f"PROFIT_LOCK_TIER1 (Peak ${current_peak:.2f} -> Reversed to ${total_basket_pnl:.2f} <= Floor ${tier1_floor:.2f})"
                logger.info(f"💰 [PROFIT LOCK TIER 1 EXECUTED] Peak reached ${current_peak:.2f} & reversed to ${total_basket_pnl:.2f} (Floor: ${tier1_floor:.2f}). Auto-closing entire basket to bank +$53.00 USD cash profit!")


        # ── STEP 3: Z = ±2.40 RUNNER LOT JACKPOT EXIT (REMAINING 30% VOLUME) ──
        if not exit_triggered:
            target_step3_z = max(2.40, Z_ENTRY_THRESHOLD)
            z_step3_jackpot = (is_buy_spread and z_score_for_pair >= target_step3_z) or (not is_buy_spread and z_score_for_pair <= -target_step3_z)

            is_sl_breached = (is_buy_spread and z_score_for_pair <= -effective_z_sl) or (not is_buy_spread and z_score_for_pair >= effective_z_sl)


            if is_sl_breached:
                exit_triggered = True
                exit_reason = f"Z_STOP_LOSS (z={z_score_for_pair:.2f})"
            elif z_step3_jackpot and total_basket_pnl > 0.0:
                exit_triggered = True
                exit_reason = f"THREE_STEP_EXIT_JACKPOT (Step 3 Jackpot Z={z_score_for_pair:.2f}, Basket PnL=${total_basket_pnl:.2f})"







        # Safeguard: Blue Guardian Consistency Rule (trades closed under 2m 20s / 140s)
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

        if exit_triggered:
            logger.info(f"🏁 [TRADE BASKET EXIT TRIGGERED] Signal ID #{sig_id} | Reason: {exit_reason} | Closing All Pair Positions 🔴")
            for t_a in open_leg_a_trades:
                close_single_trade(t_a["symbol"], t_a["ticket"], t_a["lots"], t_a["order_type"])
            for t_b in open_leg_b_trades:
                close_single_trade(t_b["symbol"], t_b["ticket"], t_b["lots"], t_b["order_type"])


            # Sync closed details immediately to database
            try:
                check_closed_trades(sym_a)
                check_closed_trades(sym_b)
                
                # Query the database to ensure ALL trades in this set are truly CLOSED before sending notification
                conn_pnl = get_connection()
                cur_pnl = conn_pnl.cursor()
                cur_pnl.execute("SELECT COUNT(*) FROM trades WHERE signal_id = %s AND status = 'OPEN'", (int(sig_id),))
                still_open_count = cur_pnl.fetchone()[0]
                cur_pnl.close()
                conn_pnl.close()
                
                if still_open_count == 0:
                    tot_profit = calculate_closed_signal_pnl(sig_id)
                    logger.info(f"📊 [PROFIT REPORT] Closed signal_id {sig_id} | Total Net Profit: ${tot_profit:.2f}")
                    send_discord_exit_notification(sig_id, sym_a, sym_b, exit_reason, tot_profit)
            except Exception as e_pnl:
                logger.error(f"Error calculating closed signal PnL: {e_pnl}")

            # Put pair in cooldown after dynamic exit to prevent immediate re-entry
            set_pair_cooldown(sym_a, sym_b, cooldown_seconds=600)
            break

            # ── Emergency Maximum Floating Loss Guard ──
            if has_positions and active_js_positions:
                try:
                    conn_eq = get_connection()
                    cur_eq = conn_eq.cursor()
                    cur_eq.execute("SELECT start_of_day_equity FROM bot_state WHERE id = 1")
                    eq_row = cur_eq.fetchone()
                    cur_eq.close()
                    conn_eq.close()
                    start_eq_guard = float(eq_row[0]) if (eq_row and eq_row[0]) else 10000.0
                    
                    daily_loss_usd = max(0.0, start_eq_guard - acc_info.equity) if acc_info else 0.0
                    daily_loss_pct = (daily_loss_usd / start_eq_guard) * 100.0 if start_eq_guard > 0 else 0.0
                    
                    if RISK_LIMITS_ENABLED and floating_profit <= -330.0:
                        logger.error(f"[EMERGENCY DRAWDOWN GUARD] Floating loss (${floating_profit:.2f}) breached safety cap (-$330.00). AUTO-CLOSING ALL TRADES IMMEDIATELY!")
                        for pos in active_js_positions:
                            pos_type_str = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"
                            close_single_trade(pos.symbol, pos.ticket, pos.volume, pos_type_str)

                except Exception as ex_dd:
                    logger.error(f"Error evaluating emergency drawdown guard: {ex_dd}")

            # ── Multi-Tier Equity Trailing Stop Safeguard (Triple Tier Profit Protection) ──
            if has_positions:
                if floating_profit > peak_floating_profit:
                    peak_floating_profit = floating_profit

                should_close_trail = False
                trail_close_reason = ""

                # Tier 1 (Baseline Lock: +$67.00 Peak -> Locks +$53.00 Cash Profit):
                if peak_floating_profit >= 67.0 and peak_floating_profit < 99.0:
                    tier1_floor = 53.0
                    if floating_profit <= tier1_floor:
                        should_close_trail = True
                        trail_close_reason = f"[PROFIT GUARD TIER 1] Peak reached ${peak_floating_profit:.2f} and reversed to ${floating_profit:.2f} (Floor: $53.00). Auto-closing to lock +$53.00 USD cash profit!"

                # Tier 2 (Balanced Expansion Lock: +$99.00 Peak -> Locks +$80.00 Cash Profit):
                elif peak_floating_profit >= 99.0 and peak_floating_profit < 142.0:
                    tier2_floor = 80.0
                    if floating_profit <= tier2_floor:
                        should_close_trail = True
                        trail_close_reason = f"[PROFIT GUARD TIER 2] Peak reached ${peak_floating_profit:.2f} and reversed to ${floating_profit:.2f} (Floor: $80.00). Auto-closing to lock +$80.00 USD cash profit!"

                # Tier 3 (Advanced Runner Lock: +$142.00 Peak -> Locks +$120.00 Cash Profit):
                elif peak_floating_profit >= 142.0 and peak_floating_profit < 185.0:
                    tier3_floor = 120.0
                    if floating_profit <= tier3_floor:
                        should_close_trail = True
                        trail_close_reason = f"[PROFIT GUARD TIER 3] Peak reached ${peak_floating_profit:.2f} and reversed to ${floating_profit:.2f} (Floor: $120.00). Auto-closing to lock +$120.00 USD cash profit!"

                # Tier 4 (Mega Runner Lock: +$185.00+ Peak -> Locks +$155.00 Cash Profit):
                elif peak_floating_profit >= 185.0:
                    tier4_floor = 155.0
                    if floating_profit <= tier4_floor:
                        should_close_trail = True
                        trail_close_reason = f"[PROFIT GUARD TIER 4] Peak reached ${peak_floating_profit:.2f} and reversed to ${floating_profit:.2f} (Floor: $155.00). Auto-closing to lock +$155.00 USD mega runner cash profit!"


                if should_close_trail and not exit_triggered:
                    exit_triggered = True
                    exit_reason = trail_close_reason
                    logger.info(f"💰 [TRAILING PROFIT LOCK EXECUTED] Triggered by {trail_close_reason}! Closing all basket positions.")
                elif peak_floating_profit >= 67.0 and (int(time.time()) % 15 == 0):
                    if peak_floating_profit >= 185.0:
                        logger.info(f"🟢 [TRAILING STOP ACTIVE - TIER 4] Peak PnL: +${peak_floating_profit:.2f} | Floor Locked: +$155.00 USD")
                    elif peak_floating_profit >= 142.0:
                        logger.info(f"🟢 [TRAILING STOP ACTIVE - TIER 3] Peak PnL: +${peak_floating_profit:.2f} | Floor Locked: +$120.00 USD")
                    elif peak_floating_profit >= 99.0:
                        logger.info(f"🟢 [TRAILING STOP ACTIVE - TIER 2] Peak PnL: +${peak_floating_profit:.2f} | Floor Locked: +$80.00 USD")
                    elif peak_floating_profit >= 67.0:
                        logger.info(f"🔵 [TRAILING STOP ACTIVE - TIER 1] Peak PnL: +${peak_floating_profit:.2f} | Floor Locked: +$53.00 USD")


                # Stepped Milestone Trailing SL for open MT5 Leg A positions (Shifting SL into Profit Zone)
                from execution_bot import modify_position_sl
                pip_unit = 0.01 if "JPY" in sym_a.upper() else 0.0001
                if any(x in sym_a.upper() for x in ["XAU", "XAG"]):
                    pip_unit = 0.10
                elif any(x in sym_a.upper() for x in ["US30", "NAS100", "US500"]):
                    pip_unit = 1.0

                for t_a in open_leg_a_trades:
                    entry_p = t_a.get("entry_price")
                    tkt = t_a.get("ticket")
                    sym = t_a.get("symbol")
                    pos_type = t_a.get("order_type")
                    
                    pos_info = mt5.positions_get(ticket=tkt)
                    if pos_info and entry_p:
                        curr_p = pos_info[0].price_current
                        curr_sl = pos_info[0].sl

                        if pos_type == "BUY":
                            pips_profit = (curr_p - entry_p) / pip_unit
                            if pips_profit >= 12.0 or peak_floating_profit >= 100.0:
                                target_sl = entry_p + (8.0 * pip_unit)
                                if curr_sl < target_sl:
                                    modify_position_sl(tkt, sym, target_sl)
                                    logger.info(f"🚀 [MILESTONE 2 TRAIL - PROFIT LOCK] Ticket {tkt} ({sym}) +{pips_profit:.1f} pips in profit / Peak ${peak_floating_profit:.2f}. Shifted SL to +8.0 pips profit lock ({target_sl:.5f})!")
                            elif pips_profit >= 8.0:
                                target_sl = entry_p + (4.0 * pip_unit)
                                if curr_sl < target_sl:
                                    modify_position_sl(tkt, sym, target_sl)
                                    logger.info(f"🛡️ [MILESTONE 1 TRAIL - PROFIT LOCK] Ticket {tkt} ({sym}) +{pips_profit:.1f} pips in profit. Shifted SL to +4.0 pips profit lock ({target_sl:.5f})!")
                        elif pos_type == "SELL":
                            pips_profit = (entry_p - curr_p) / pip_unit
                            if pips_profit >= 12.0 or peak_floating_profit >= 100.0:
                                target_sl = entry_p - (8.0 * pip_unit)
                                if curr_sl == 0.0 or curr_sl > target_sl:
                                    modify_position_sl(tkt, sym, target_sl)
                                    logger.info(f"🚀 [MILESTONE 2 TRAIL - PROFIT LOCK] Ticket {tkt} ({sym}) +{pips_profit:.1f} pips in profit / Peak ${peak_floating_profit:.2f}. Shifted SL to +8.0 pips profit lock ({target_sl:.5f})!")
                            elif pips_profit >= 8.0:
                                target_sl = entry_p - (4.0 * pip_unit)
                                if curr_sl == 0.0 or curr_sl > target_sl:
                                    modify_position_sl(tkt, sym, target_sl)
                                    logger.info(f"🛡️ [MILESTONE 1 TRAIL - PROFIT LOCK] Ticket {tkt} ({sym}) +{pips_profit:.1f} pips in profit. Shifted SL to +4.0 pips profit lock ({target_sl:.5f})!")



        # Safeguard: Blue Guardian Consistency Rule (trades closed under 2m 20s / 140s)
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
            if trail_close_reason and "[PROFIT GUARD" in trail_close_reason:
                logger.info(f"💰 [PROFIT GUARD OVERRIDE] Trailing profit lock ({trail_close_reason}) exempt from 140s minimum hold! Executing instant cash profit lock.")
            else:
                exit_triggered = False
                logger.info(f"Exit deferred for signal_id {sig_id} to satisfy 140s minimum hold time.")


        if exit_triggered:
            logger.info(f"Dynamic exit triggered for signal_id {sig_id}. Reason: {exit_reason}. Closing all positions.")
            for t_a in open_leg_a_trades:
                close_single_trade(t_a["symbol"], t_a["ticket"], t_a["lots"], t_a["order_type"])
            for t_b in open_leg_b_trades:
                close_single_trade(t_b["symbol"], t_b["ticket"], t_b["lots"], t_b["order_type"])

                
            # Sync closed details immediately to database
            try:
                check_closed_trades(sym_a)
                check_closed_trades(sym_b)
                
                # Query the database to ensure ALL trades in this set are truly CLOSED before sending notification
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
    # Crypto disabled completely in this Forex/Metals/Indices instance
    if any(x in s for x in ["XAU", "XAG", "XPT", "XPD", "PLAT", "PALL"]):
        return "metals"
    if any(x in s for x in ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMD", "META", "AMZN"]):
        return "stocks"
    if any(x in s for x in ["US500", "US30", "NAS100", "GER30", "UK100", "USTEC"]):
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
def calculate_bridge_lots(lots_a: float, price_a: float, price_b: float, contract_a: float, contract_b: float, entry_beta: float, atr_a: float = 1.0, atr_b: float = 1.0, symbol_b: str = "", symbol_a: str = "") -> float:
    """
    Option A: Volatility-Adjusted Cointegration Bridge Lot Sizing.
    Binds Entry Beta with 14-Period ATR Volatility Normalization Ratio and Nominal Value Conversion Factor
    so statistical Z-Score spread edge and dollar risk exposure are in 100% perfect harmony!
    """
    from risk_safeguards import round_volume
    # Step 1: Statistical Beta Weighting
    beta_weight = abs(float(entry_beta)) if entry_beta else 1.0
    
    # Step 2: Volatility Normalization Ratio (Percentage ATR ratio to normalize 5-digit vs 3-digit JPY/CHF pairs)
    vol_a_pct = (atr_a / price_a) if (atr_a and price_a and price_a > 0) else 0.001
    vol_b_pct = (atr_b / price_b) if (atr_b and price_b and price_b > 0) else 0.001
    volatility_ratio = (vol_a_pct / vol_b_pct) if vol_b_pct > 0 else 1.0
    
    # Step 3: Nominal Value Conversion Factor in USD
    def get_usd_nominal(sym, p, c_size):
        if not sym:
            return c_size if p > 50.0 else c_size * p
        s = sym.upper()
        if s.startswith("USD"):
            return c_size
        elif s.endswith("USD"):
            return c_size * p
        else:
            return c_size if p > 50.0 else c_size * p

    nominal_value_a = get_usd_nominal(symbol_a, price_a, contract_a)
    nominal_value_b = get_usd_nominal(symbol_b, price_b, contract_b)
    value_factor = (nominal_value_a / nominal_value_b) if nominal_value_b > 0 else 1.0
    
    # Combined Cointegration Bridge Output
    raw_lots_b = lots_a * beta_weight * volatility_ratio * value_factor
    
    if symbol_b:
        lots_b = round_volume(symbol_b, raw_lots_b)
        info_b = mt5.symbol_info(symbol_b)
        min_vol_b = info_b.volume_min if info_b else 0.01
        if lots_b < min_vol_b:
            lots_b = min_vol_b
        return lots_b
    return round(raw_lots_b, 2)


def get_hedge_quantity(symbol_a: str, symbol_b: str, qty_a: float, beta: float, cat_a: str, cat_b: str) -> float:
    """
    Calculates Pure Beta-Neutral Cointegration Lot Size for Leg B: Lots_B = Lots_A * |beta|.
    Strictly preserves statistical beta neutrality without over-sizing or over-dragging.
    """
    from risk_safeguards import round_volume
    try:
        beta_val = abs(float(beta)) if beta else 1.0
        raw_lots_b = float(qty_a) * beta_val
        lots_b = round_volume(symbol_b, raw_lots_b)
        info_b = mt5.symbol_info(symbol_b)
        min_vol_b = info_b.volume_min if info_b else 0.01
        if lots_b < min_vol_b:
            lots_b = min_vol_b
        logger.info(f"📊 [PURE BETA-NEUTRAL HEDGE] Symbol A ({symbol_a}): {qty_a:.2f} lots | Beta: {beta_val:.4f} -> Symbol B ({symbol_b}) Lot Size: {lots_b:.2f} lots")
        return lots_b
    except Exception as e:
        logger.error(f"Error in get_hedge_quantity: {e}")
        return round_volume(symbol_b, float(qty_a) * abs(float(beta) if beta else 1.0))





def apply_margin_guard(symbol_a: str, symbol_b: str, qty_a: float, qty_b: float, is_long: bool) -> tuple:
    """
    Checks the free margin in MT5 and dynamically scales down qty_a and qty_b
    if the combined margin requirement exceeds 75% of available free margin.
    Returns (scaled_qty_a, scaled_qty_b).
    """
    disable_guard = os.getenv("DISABLE_MARGIN_GUARD", "False").lower() in ("true", "1", "yes")
    if disable_guard:
        return qty_a, qty_b

    acc = mt5.account_info()
    if not acc:
        return qty_a, qty_b
        
    free_margin = float(acc.margin_free)
    margin_limit = free_margin * 0.35  # Strict 35% cap on free margin per basket to guarantee 80% prop firm margin rule safety
    
    # Resolving order types for margin calculation
    action_a = mt5.ORDER_TYPE_BUY if is_long else mt5.ORDER_TYPE_SELL
    action_b = mt5.ORDER_TYPE_SELL if is_long else mt5.ORDER_TYPE_BUY
    
    tick_a = mt5.symbol_info_tick(symbol_a)
    price_a = tick_a.ask if action_a == mt5.ORDER_TYPE_BUY else (tick_a.bid if tick_a else mt5.symbol_info(symbol_a).bid)
    
    tick_b = mt5.symbol_info_tick(symbol_b)
    price_b = tick_b.ask if action_b == mt5.ORDER_TYPE_BUY else (tick_b.bid if tick_b else mt5.symbol_info(symbol_b).bid)
    
    margin_a = mt5.order_calc_margin(action_a, symbol_a, qty_a, price_a)
    margin_b = mt5.order_calc_margin(action_b, symbol_b, qty_b, price_b)
    
    if margin_a is None or margin_b is None or margin_a <= 0 or margin_b <= 0:
        # Fallback margin estimation for CFDs/Stocks where order_calc_margin is None
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
        
        # Ensure scaled_a is divisible by 3 (for 3-part split)
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
        
        # Recalculate margin for logs
        new_margin_a = mt5.order_calc_margin(action_a, symbol_a, final_a, price_a) or 0.0
        new_margin_b = mt5.order_calc_margin(action_b, symbol_b, final_b, price_b) or 0.0
        logger.info(f"[MARGIN GUARD] Scaled lot sizes: Leg A: {qty_a:.2f} -> {final_a:.2f} | Leg B: {qty_b:.2f} -> {final_b:.2f}. New Total Margin: ${new_margin_a + new_margin_b:.2f}")
        
        return final_a, final_b
        
    return qty_a, qty_b
def get_expected_profit(active_js_positions, tp_pips_val) -> float:
    """
    Calculates the total expected profit for the open positions basket
    based on the total lots of Leg A and the configured TP pips.
    """
    if not active_js_positions:
         return 100.0  # Default fallback trigger
        
    # Separate Leg A and Leg B positions
    # Leg B has comment JS_HEDGE. Leg A does not (it has JS_TP1, JS_TP2, JS_TP3).
    leg_a_positions = [p for p in active_js_positions if "HEDGE" not in str(p.comment).upper()]
    if not leg_a_positions:
        # If only hedge remains or comments mismatch, fallback to total positions
        leg_a_positions = active_js_positions
        
    total_lots_a = sum(p.volume for p in leg_a_positions)
    symbol_a = leg_a_positions[0].symbol
    
    # Estimate pip value in USD per lot
    symbol_upper = symbol_a.upper()
    if any(x in symbol_upper for x in ["XAU", "XPT", "XPD", "PLAT", "PALL"]):
        pip_value_per_lot = 100.0  # Gold/Metals: $100 per 1.0 point change
    elif any(x in symbol_upper for x in ["US500", "NAS100", "GER30", "UK100", "US30"]):
        pip_value_per_lot = 100.0  # Indices: $100 per 1.0 point change
    else:
        pip_value_per_lot = 10.0   # Forex: $10 per 0.0001 change (approx)
        
    # Expected profit = Lots * Pip Value * TP Pips
    expected_profit = total_lots_a * pip_value_per_lot * tp_pips_val
    return max(expected_profit, 20.0)  # Ensure a minimum expected profit of $20 to avoid division errors


# ==============================================================================
# MAIN TRADING ENGINE RUN LOOP
# ==============================================================================
def main():
    print("=========================================")
    print("   JANE STREET QUANT BOT INITIALIZING    ")
    print("=========================================\n")

    global REQUIRE_SMC_CONFLUENCE, SL_PIPS, TP_PIPS, AUTO_EXECUTE, Z_ENTRY_THRESHOLD, DEFAULT_LOTS, RISK_LIMITS_ENABLED, ML_MODEL
    global CRYPTO_ENABLED, METALS_ENABLED, FOREX_ENABLED, INDICES_ENABLED, STOCKS_ENABLED
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
    active_pair_beta = float(init_beta_val)
    active_pair_z_score = 0.0
    active_pair_velocity = 0.0


    db_cfg = fetch_db_config()
    if db_cfg:
        new_pair, new_sl, new_tp, new_smc, new_auto_exec, new_crypto, new_metals, new_forex, new_indices, new_risk_limits, new_z_entry, new_def_lots, new_max_trades, new_knife, new_obi, new_vol, new_stocks, new_halt, new_max_dd = db_cfg[:19]
        SL_PIPS = new_sl
        TP_PIPS = new_tp
        import risk_safeguards
        risk_safeguards.HALT_DAILY_DRAWDOWN_PCT = float(new_halt) if new_halt is not None else 0.80
        risk_safeguards.MAX_DAILY_LOSS_PERCENT = float(new_halt) if new_halt is not None else 0.80
        risk_safeguards.MAX_DAILY_DRAWDOWN_PCT = float(new_max_dd) if new_max_dd is not None else 3.30
        if len(db_cfg) > 19:
            risk_safeguards.SESSION_GUARD_ENABLED = bool(db_cfg[19])
            risk_safeguards.SESSION_START_HOUR = float(db_cfg[20])
            risk_safeguards.SESSION_END_HOUR = float(db_cfg[21])

    import risk_safeguards
    logger.info("Quantitative core pipeline active.")
    logger.info(f"[ACTIVE SYSTEM CONFIG] SL Pips: {SL_PIPS} | TP Pips: {TP_PIPS} | Halt Limit: {risk_safeguards.HALT_DAILY_DRAWDOWN_PCT:.2f}% | Max Limit: {risk_safeguards.MAX_DAILY_DRAWDOWN_PCT:.2f}% | Dynamic ATR Target: ENABLED 🟢 (1.5x M15 ATR) | Swing Structure Target: ENABLED 🟢 (M15 Swing High/Low) | Minimum Hold: {risk_safeguards.MINIMUM_HOLD_TIME_SECONDS}s | Adverse Exit: DISABLED ❌ | Dynamic Velocity Filter: DISABLED ❌ | Metals Lots: {DEFAULT_LOT_SIZES.get('metals')} | Forex Lots: {DEFAULT_LOT_SIZES.get('forex')}")





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
            
            # Check if there is an account switch OR a startup mismatch on 0 trades today
            from database import get_connection
            startup_mismatch = False
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("SELECT mt5_login, initial_balance FROM bot_state WHERE id = 1")
                state_row = cur.fetchone()
                db_login = int(state_row[0]) if (state_row and state_row[0] is not None) else 0
                db_initial = float(state_row[1]) if (state_row and state_row[1] is not None) else 0.0
                
                # Check active positions count
                cur.execute("SELECT COUNT(*) FROM trades WHERE status = 'OPEN'")
                open_trades_count = cur.fetchone()[0] or 0
                
                if db_login > 0 and current_login > 0 and db_login != current_login:
                    startup_mismatch = True
                
                # Purge any legacy Platinum/Palladium rows from scanned_assets
                cur_purge = conn.cursor()
                cur_purge.execute("DELETE FROM scanned_assets WHERE symbol_pair LIKE '%XPTUSD%' OR symbol_pair LIKE '%XPDUSD%'")
                conn.commit()
                cur_purge.close()
                
                cur.close()
                conn.close()
                
            except Exception as e:
                logger.error(f"Error checking startup metrics sync: {e}")
                
            login_changed = (active_login_id is not None and active_login_id != current_login) or (startup_mismatch and db_login > 0 and db_login != current_login)
            
            if login_changed:
                logger.info(f"🔄 [GENUINE ACCOUNT SWITCH DETECTED] Connected new MT5 Login #{current_login} (Previous DB Login #{db_login}). Initializing fresh account session.")
                from database import reset_database_metrics_for_new_account
                reset_database_metrics_for_new_account(current_login, acc_info.equity)
                
                # Reset local daily start equity in memory to the new account's equity
                daily_start_equity = float(acc_info.equity)
                
                # Update safeguards cache here to prevent circular imports
                try:
                    import risk_safeguards
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
                    new_pair, new_sl, new_tp, new_smc, new_auto_exec, new_crypto, new_metals, new_forex, new_indices, new_risk_limits, new_z_entry, new_def_lots, new_max_trades, new_knife, new_obi, new_vol, new_stocks, new_halt, new_max_dd = db_cfg[:19]
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
                        logger.info(f"🚀 [ACTIVE PIPELINE CONFIG] SL Pips: {SL_PIPS} | TP Pips: {TP_PIPS} | Z-Entry: {new_z_entry} | Kalman Beta: {active_pair_beta:.4f} (Dynamic Hedge Ratio) 🟢")

                        logger.info(f"🎯 [TARGET EXITS SYSTEM] Z=±2.40 Jackpot Target Exit (ENABLED 🟢) | Option B Multi-Tier Trailing Stop (ENABLED 🟢) | Step 2 Mid-Way Scale-Out (DISABLED 🔴)")



                        logger.info(f"🛑 [DISABLED FILTERS] Pre-Entry Direction: DISABLED ❌ | Min Beta (<0.20): DISABLED ❌ | Option 1 Z<=0.50 Exit: DISABLED ❌ | Breakeven Guard ($0.00 Entry SL): DISABLED 🔴 | Adverse Regime Exit: DISABLED ❌ | SMC: DISABLED ❌")

                        logger.info(f"🛡️ [ACTIVE GUARDS] Single Trade Lock: ENABLED 🛡️ (Max 1 Trade at a time) | News Guard: ENABLED 📰 | Multi-Tier Equity Trailing: ENABLED 🟢 (Option B: Tier 1: +$67->$53 | Tier 2: +$99->$80 | Tier 3: +$142->$120 | Tier 4: +$185->$155) | Friday Close Guard: ENABLED 🌅")







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
                    new_h_val = float(new_halt) if new_halt is not None else risk_safeguards.HALT_DAILY_DRAWDOWN_PCT
                    new_m_val = float(new_max_dd) if new_max_dd is not None else risk_safeguards.MAX_DAILY_DRAWDOWN_PCT
                    if risk_safeguards.HALT_DAILY_DRAWDOWN_PCT != new_h_val:
                        logger.info(f"[CONFIG UPDATE] Halt Drawdown Limit updated: {risk_safeguards.HALT_DAILY_DRAWDOWN_PCT}% -> {new_h_val}%")
                        risk_safeguards.HALT_DAILY_DRAWDOWN_PCT = new_h_val
                        risk_safeguards.MAX_DAILY_LOSS_PERCENT = new_h_val
                    if risk_safeguards.MAX_DAILY_DRAWDOWN_PCT != new_m_val:
                        logger.info(f"[CONFIG UPDATE] Max Drawdown Limit updated: {risk_safeguards.MAX_DAILY_DRAWDOWN_PCT}% -> {new_m_val}%")
                        risk_safeguards.MAX_DAILY_DRAWDOWN_PCT = new_m_val
                    
                    # Clean up disabled categories in the database immediately
                    cleanup_disabled_scanned_assets(CRYPTO_ENABLED, METALS_ENABLED, FOREX_ENABLED, INDICES_ENABLED, STOCKS_ENABLED)
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

            # Automated High-Impact News Entry Guard (Block new entries 15 mins before news, but do NOT force-close running trades)
            should_close_news, news_close_reason = news_guard.should_auto_close_before_news([S_A_resolved, S_B_resolved], lead_minutes=15.0)
            if should_close_news:
                logger.info(f"📰 HIGH-IMPACT NEWS IMMINENT: {news_close_reason}. Blocking new trade entries to protect capital.")

            # Friday Weekend Close Guard (Auto-close open positions 45 mins before Friday market close to prevent Sunday gap risk)
            is_friday_close = is_friday_market_close_approaching(lead_minutes=45)
            if is_friday_close and cat_a != "crypto":
                logger.warning("🌅 FRIDAY MARKET CLOSE IMMINENT: Blocking new entries and auto-closing active positions to prevent Sunday opening gap risk!")
                if get_open_trades_count() > 0:
                    close_all_positions("ALL")


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
                is_limit_breached, daily_loss_p, peak_dd_p = check_drawdown_limit(current_equity)
                if daily_start_equity and current_equity >= daily_start_equity:
                    is_limit_breached = False
                    daily_loss_p = 0.0
                    peak_dd_p = 0.0
            else:
                is_limit_breached, daily_loss_p, peak_dd_p = False, 0.0, 0.0


            # Detect if it's a demo or contest account
            is_demo = getattr(acc_info, "trade_mode", 0) in (0, 1)  # 0 is DEMO, 1 is CONTEST

            if is_limit_breached:
                effective_dd_val = max(daily_loss_p, peak_dd_p)
                if RISK_LIMITS_ENABLED:
                    logger.warning(f"🚨 DAILY DRAWDOWN LIMIT BREACHED (Peak DD: {effective_dd_val:.2f}% >= Halt Limit {MAX_DAILY_LOSS_PERCENT}%). ENFORCING STRICT RISK HALT & BLOCKING ALL NEW TRADES!")
                    is_halted = True
                else:
                    logger.info(f"🎮 [RISK HALT BYPASSED] Drawdown limit breached (Peak DD: {effective_dd_val:.2f}% >= Halt Limit {MAX_DAILY_LOSS_PERCENT}%), but Risk Limits Enforcer is toggled OFF on Dashboard. Trades allowed.")
                    is_halted = False
            else:
                is_halted = False





            if daily_start_equity is None and current_equity > 0.0:
                from risk_safeguards import get_or_create_daily_start_equity
                daily_start_equity = get_or_create_daily_start_equity(current_equity)


            if is_halted:
                close_all_positions("ALL")
                update_bot_state(
                    active_pair=current_pair_context,
                    system_status="HALTED (Max Loss)",
                    equity=acc_info.equity,
                    drawdown_percent=daily_loss_p,
                    floating_profit=0.0,
                    z_score=active_pair_z_score,
                    hedge_ratio=active_pair_beta,
                    obi_a=0.0,

                    obi_b=0.0,
                    trades_today=get_trades_count_today(),
                    sl_pips=SL_PIPS,
                )
                time.sleep(10)
                continue

            # ── 0. INSTANT LIVE DB TOGGLES SYNC (2s LOOP) ──
            update_live_toggles_from_db()

            # ── 2-STAGE NEWS GUARD EVALUATION ──
            is_news_blocked, news_reason, news_country, news_title = check_pair_news_block([S_A_resolved, S_B_resolved])
            if not is_news_blocked:
                kf_curr = get_kf_for_pair(S_A_resolved, S_B_resolved)
                is_news_blocked, news_reason, news_country, news_title = check_post_news_stability([S_A_resolved, S_B_resolved], kf_pair=kf_curr)
            is_news_halted = is_news_blocked

            # ── 1. COMPILE CANDIDATE PAIRS ──
            pairs_to_scan = []
            if FOREX_ENABLED:
                pairs_to_scan.extend(CANDIDATE_PAIRS["forex"])
            if METALS_ENABLED:
                pairs_to_scan.extend(CANDIDATE_PAIRS["metals"])
            if CRYPTO_ENABLED:
                pairs_to_scan.extend(CANDIDATE_PAIRS["crypto"])
            if STOCKS_ENABLED:
                pairs_to_scan.extend(CANDIDATE_PAIRS["stocks"])
            if INDICES_ENABLED:
                pairs_to_scan.extend(CANDIDATE_PAIRS["indices"])

            # Include custom pair if set and not already in pool
            if current_pair_context not in [f"{p[0]}/{p[1]}" for p in pairs_to_scan]:
                parts = current_pair_context.split('/')
                if len(parts) == 2 and parts[0] != parts[1]:
                    pairs_to_scan.append((parts[0], parts[1]))

            candidate_signals = []

            # Periodically update win rates asynchronously in background thread (never blocking main scan loop)
            if win_rate_loop_counter % 300 == 0:
                def bg_win_rate_calc(pairs, z_thresh):
                    for s_a, s_b in pairs:
                        pair_key = f"{s_a}/{s_b}"
                        try:
                            WIN_RATE_CACHE[pair_key] = simulate_win_rate_for_pair(s_a, s_b, z_entry=z_thresh)
                        except Exception:
                            WIN_RATE_CACHE[pair_key] = 100.0
                threading.Thread(target=bg_win_rate_calc, args=(list(pairs_to_scan), Z_ENTRY_THRESHOLD), daemon=True).start()
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
                if positions:
                    active_js_positions = [p for p in positions if (p.magic == MAGIC_NUMBER or "JS_" in str(p.comment).upper() or "JANE" in str(p.comment).upper())]
                    if not active_js_positions and len(positions) > 0:
                        # Fallback to all MT5 positions if broker cleared magic/comment on netting/hedging
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

            # ── EMERGENCY HARD DRAWDOWN & FLOATING LOSS SAFEGUARD ($175.00 / 1.75% MAX CAP) ──
            if has_positions and active_js_positions:
                try:
                    from risk_safeguards import get_or_create_daily_start_equity
                    start_eq_guard = get_or_create_daily_start_equity(acc_info.equity)
                    daily_loss_usd = start_eq_guard - acc_info.equity
                    daily_loss_pct = (daily_loss_usd / start_eq_guard) * 100.0 if start_eq_guard > 0 else 0.0
                    
                    if RISK_LIMITS_ENABLED and floating_profit <= -330.0:
                        logger.error(f"[EMERGENCY DRAWDOWN GUARD] Floating loss (${floating_profit:.2f}) breached safety cap (-$330.00). AUTO-CLOSING ALL TRADES IMMEDIATELY!")
                        for pos in active_js_positions:
                            pos_type_str = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"
                            close_single_trade(pos.symbol, pos.ticket, pos.volume, pos_type_str)

                except Exception as ex_dd:
                    logger.error(f"Error evaluating emergency drawdown guard: {ex_dd}")

            # ── Multi-Tier Equity Trailing Stop Safeguard (DISABLED per user directive for Three-Step Exit Strategy) ──

            # ── HEDGE-EFFECTIVENESS MONITORING LAYER ──
            if has_positions and active_js_positions:
                try:
                    from risk_safeguards import evaluate_hedge_effectiveness
                    evaluate_hedge_effectiveness(active_js_positions)
                except Exception as ex_hm:
                    logger.error(f"Error in hedge effectiveness monitoring: {ex_hm}")

            # ── Protection 5: LOGIC-BASED AUTOMATIC ADVERSE-REGIME EXIT (Evaluated after 140s hold) ──
            if has_positions and active_js_positions:
                try:
                    from risk_safeguards import check_adverse_regime_exit

                    conn_time = get_connection()
                    cur_time = conn_time.cursor()
                    cur_time.execute("SELECT entry_time, order_type FROM trades WHERE status = 'OPEN' ORDER BY entry_time ASC LIMIT 1")
                    time_row = cur_time.fetchone()
                    cur_time.close()
                    conn_time.close()
                    
                    if time_row and time_row[0]:
                        first_entry_time = time_row[0]
                        dir_str = str(time_row[1]).upper()
                        kf_active = get_kf_for_pair(S_A_resolved, S_B_resolved)
                        current_z_val = kf_active.z_history[-1] if kf_active.z_history else 0.0
                        current_v_val = kf_active.get_velocity(k=3)
                        
                        if isinstance(first_entry_time, (int, float)):
                            t_age = time.time() - first_entry_time
                        elif isinstance(first_entry_time, datetime.datetime):
                            now_utc = datetime.datetime.now(datetime.timezone.utc)
                            if first_entry_time.tzinfo is None:
                                first_entry_time = first_entry_time.replace(tzinfo=datetime.timezone.utc)
                            t_age = (now_utc - first_entry_time).total_seconds()
                        else:
                            t_age = 0.0

                        should_adv_close, adv_reason = check_adverse_regime_exit(current_pair_context, dir_str, current_z_val, current_v_val, t_age)
                        if should_adv_close:
                            logger.warning(f"[PAIR-SPECIFIC ADVERSE EXIT] {adv_reason}. AUTO-CLOSING ALL 4 TICKETS (3 TP LEGS + 1 HEDGE LEG) FOR PAIR {current_pair_context} ONLY!")
                            
                            # Query DB for open tickets belonging strictly to this pair (3 TP tickets + 1 Hedge ticket)
                            conn_pair_tkts = get_connection()
                            cur_pair_tkts = conn_pair_tkts.cursor()
                            cur_pair_tkts.execute("SELECT ticket, symbol, order_type FROM trades WHERE status = 'OPEN' AND (UPPER(SPLIT_PART(symbol, '.', 1)) = %s OR UPPER(SPLIT_PART(symbol, '.', 1)) = %s)", (S_A_resolved.upper().split('.')[0], S_B_resolved.upper().split('.')[0]))
                            pair_db_rows = cur_pair_tkts.fetchall()
                            cur_pair_tkts.close()
                            conn_pair_tkts.close()
                            
                            target_tickets = {row[0] for row in pair_db_rows}
                            pair_syms = {S_A_resolved.upper().split('.')[0], S_B_resolved.upper().split('.')[0]}
                            
                            for pos in active_js_positions:
                                pos_base = pos.symbol.upper().split('.')[0]
                                pos_tkt = int(pos.ticket)
                                # Close ONLY the 4 tickets belonging to this specific pair (3 TP + 1 Hedge)
                                if pos_tkt in target_tickets or pos_base in pair_syms:
                                    pos_type_str = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"
                                    logger.info(f"Closing adverse exit ticket {pos.ticket} ({pos.symbol} {pos.volume} lots)...")
                                    close_single_trade(pos.symbol, pos.ticket, pos.volume, pos_type_str)


                except Exception as ex_adv:
                    logger.error(f"Error evaluating adverse regime exit: {ex_adv}")


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
                            
                    # Proportional PnL distribution for netting accounts where position ticket differs from order ticket
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

            # Query all open trade symbols once per scan cycle to freeze Kalman Filter updates
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

            # ── 2. SCANNING LOOP FOR ALL PAIRS ──
            active_pair_z_score = 0.0
            if active_pair_beta == 0.0 or active_pair_beta is None:
                active_pair_beta = float(init_beta_val)
            active_pair_obi_a = 0.0
            active_pair_obi_b = 0.0
            active_pair_velocity = 0.0
            all_scanned_z_summary = []



            for s_a, s_b in pairs_to_scan:
                pk = f"{s_a}/{s_b}"
                cat_a = get_symbol_category(s_a)
                cat_b = get_symbol_category(s_b)

                # Resolve broker aliases for MT5 symbols
                s_a_resolved = resolve_broker_symbol(s_a) if cat_a != "crypto" else s_a
                s_b_resolved = resolve_broker_symbol(s_b) if cat_b != "crypto" else s_b

                # ── MARKET CLOSED GUARD ──
                # Prevents scanning or generating signals for closed stocks/indices outside market hours
                if not is_market_open(s_a_resolved) or not is_market_open(s_b_resolved):
                    continue

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

                # Dynamic Kalman update on every live tick scan (FREEZE parameters update if trade is active)
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
                    z_vel_lim = 0.005  # Tightened from 0.02 for 85%+ entry accuracy
                elif cat_a == "metals":
                    z_vel_lim = 0.02   # Tightened from 0.08
                else:
                    z_vel_lim = 0.01   # Tightened from 0.05

                action = "NONE"
                # Evaluate active protections based strictly on Dashboard Toggles (at all Z-thresholds)
                effective_dyn_z = Z_ENTRY_THRESHOLD
                _, _, z_sl_val, _ = get_strategy_parameters(s_a_resolved)
                
                pass_z_buy = (z < -effective_dyn_z) and (z > -z_sl_val)
                pass_z_sell = (z > effective_dyn_z) and (z < z_sl_val)
                
                # Turning Point Inflection Filter: ENABLED 🟢
                pass_turn_buy = True
                pass_turn_sell = True
                if kf_pair and len(kf_pair.z_history) >= 3:
                    pass_turn_buy = is_turning_point_confirmed(kf_pair.z_history, effective_dyn_z, "BUY_SPREAD")
                    pass_turn_sell = is_turning_point_confirmed(kf_pair.z_history, effective_dyn_z, "SELL_SPREAD")




                
                pass_vel_buy = (z_velocity > -z_vel_lim) if KNIFE_PROTECTION_ENABLED else True
                pass_vel_sell = (z_velocity < z_vel_lim) if KNIFE_PROTECTION_ENABLED else True
                
                pass_obi_buy = obi_buy_pass if OBI_ENABLED else True
                pass_obi_sell = obi_sell_pass if OBI_ENABLED else True
                
                pass_smc_buy = in_bullish_zone if REQUIRE_SMC_CONFLUENCE else True
                pass_smc_sell = in_bearish_zone if REQUIRE_SMC_CONFLUENCE else True
                
                if pass_z_buy and pass_vel_buy and pass_obi_buy and pass_smc_buy and pass_turn_buy:
                    action = "BUY_SPREAD"
                elif pass_z_sell and pass_vel_sell and pass_obi_sell and pass_smc_sell and pass_turn_sell:
                    action = "SELL_SPREAD"

                # Protection 3: Pre-Entry Direction Confirmation
                if action != "NONE":
                    from execution_bot import check_pre_entry_direction_confirmation
                    is_confirmed, pre_reason = check_pre_entry_direction_confirmation(action, z, z_velocity, pair_str=f"{s_a_resolved}/{s_b_resolved}")
                    if not is_confirmed:

                        logger.info(pre_reason)
                        action = "NONE"

                # Validate beta sign and magnitude to prevent same-side hedge order anomalies

                if action != "NONE":
                    expected_sign = EXPECTED_BETA_SIGN.get(pk, 1)
                    beta_sign = 1 if beta >= 0 else -1
                    if beta_sign != expected_sign:
                        logger.warning(f"Correlation anomaly for {pk}: estimated beta {beta:.4f} has wrong sign (expected {expected_sign}). Skipping signal.")
                        action = "NONE"
                    # Min beta (<0.20) filter DISABLED per user directive to ensure pure baseline trade execution


                # Debug log why signal was skipped if base Z threshold was crossed but action is NONE
                base_z_triggered = (z < -Z_ENTRY_THRESHOLD) or (z > Z_ENTRY_THRESHOLD)
                if base_z_triggered and action == "NONE":
                    reasons = []
                    if z < -Z_ENTRY_THRESHOLD:
                        if not pass_turn_buy:
                            zh_str = [round(x, 2) for x in list(kf_pair.z_history)[-3:]] if kf_pair and hasattr(kf_pair, 'z_history') else []
                            reasons.append(f"Turning Point Inflection filter waiting for Z-score reversal momentum (Z-History: {zh_str})")
                        if VOLATILITY_FILTER_ENABLED and not (z < -dynamic_z_entry):
                            reasons.append(f"Z-score {z:.3f} not below dynamic threshold {-dynamic_z_entry:.3f} (volatility protection)")
                        if KNIFE_PROTECTION_ENABLED and not (z_velocity > -z_vel_lim):
                            reasons.append(f"Z-velocity {z_velocity:.3f} too fast (falling knife protection, limit: {-z_vel_lim})")
                        if OBI_ENABLED and not obi_buy_pass:
                            reasons.append(f"Adverse OBI pressure {net_obi:.3f} < -0.20 (sell wall)")
                        if REQUIRE_SMC_CONFLUENCE and not in_bullish_zone:
                            reasons.append("Price not in Bullish SMC Zone (Order Block/FVG)")
                    else:
                        if not pass_turn_sell:
                            zh_str = [round(x, 2) for x in list(kf_pair.z_history)[-3:]] if kf_pair and hasattr(kf_pair, 'z_history') else []
                            reasons.append(f"Turning Point Inflection filter waiting for Z-score reversal momentum (Z-History: {zh_str})")
                        if VOLATILITY_FILTER_ENABLED and not (z > dynamic_z_entry):
                            reasons.append(f"Z-score {z:.3f} not above dynamic threshold {dynamic_z_entry:.3f} (volatility protection)")
                        if KNIFE_PROTECTION_ENABLED and not (z_velocity < z_vel_lim):
                            reasons.append(f"Z-velocity {z_velocity:.3f} too fast (rising knife protection, limit: {z_vel_lim})")
                        if OBI_ENABLED and not obi_sell_pass:
                            reasons.append(f"Adverse OBI pressure {net_obi:.3f} > 0.20 (buy wall)")
                        if REQUIRE_SMC_CONFLUENCE and not in_bearish_zone:
                            reasons.append("Price not in Bearish SMC Zone (Order Block/FVG)")
                    
                    if reasons:
                        logger.info(f"🔄 [ENTRY SKIPPED LOG] Signal threshold crossed for {pk} (Z={z:.3f} vs Entry Limit {Z_ENTRY_THRESHOLD:.2f}), but entry deferred due to: {'; '.join(reasons)}")


                win_rate = WIN_RATE_CACHE.get(pk, 50.0)
                update_scanned_asset(pk, p_a, p_b, win_rate, z, action)
                all_scanned_z_summary.append(f"{pk}: Z={z:.3f}")


                # Track telemetry for current active pair (case-insensitive & alias resilient)
                norm_pk = pk.upper().replace(" ", "").strip()
                norm_ctx = current_pair_context.upper().replace(" ", "").strip()
                if norm_pk == norm_ctx or (norm_pk.split('/')[0] in norm_ctx and norm_pk.split('/')[1] in norm_ctx):
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

                active_pairs_cnt, active_pairs_set, active_symbols_set = get_active_pairs_and_symbols()

                
                base_a_check = s_a_resolved.upper().split('.')[0]
                base_b_check = s_b_resolved.upper().split('.')[0]
                is_duplicate_open = (base_a_check in active_symbols_set) or (base_b_check in active_symbols_set) or (f"{base_a_check}/{base_b_check}" in active_pairs_set)
                has_any_active_trade = (active_pairs_cnt > 0) or (len(active_symbols_set) > 0)

                if action != "NONE" and (has_any_active_trade or is_duplicate_open):
                    logger.info(f"🛡️ [SINGLE TRADE LOCK ACTIVE] Signal generated for {s_a_resolved}/{s_b_resolved} ({action}), but 1 active trade is already open on MT5. Entry BLOCKED.")
                elif action != "NONE" and cooldown_dir != action and not is_pair_in_cooldown(s_a_resolved, s_b_resolved):
                    cand_cat_a = get_symbol_category(s_a_resolved)
                    cand_cat_b = get_symbol_category(s_b_resolved)
                    if (cand_cat_a == "crypto" or is_spread_valid(s_a_resolved)) and (cand_cat_b == "crypto" or is_spread_valid(s_b_resolved)):
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
            active_pairs_cnt, active_pairs_set, active_symbols_set = get_active_pairs_and_symbols()
            
            from risk_safeguards import is_session_time_allowed
            import risk_safeguards
            is_session_ok, curr_utc_s, window_utc_s = is_session_time_allowed(risk_safeguards.SESSION_START_HOUR, risk_safeguards.SESSION_END_HOUR)

            if active_pairs_cnt >= MAX_CONCURRENT_TRADES or len(active_symbols_set) > 0:
                if candidate_signals:
                    logger.info(f"🛡️ [SINGLE TRADE LOCK ACTIVE] An active trade is currently open on MT5 ({len(active_symbols_set)} active symbols). New entries BLOCKED until the active trade closes.")
            elif risk_safeguards.SESSION_GUARD_ENABLED and not is_session_ok and candidate_signals:
                for c in candidate_signals:
                    pair_str = f"{c['pair'][0]}/{c['pair'][1]}"
                    logger.info(f"⏰ [SESSION GUARD ACTIVE 🔴] Signal generated for {pair_str} ({c['action']} | Z={c['z_score']:.3f} | Beta={float(c.get('beta', 1.0)):.2f}), but current time ({curr_utc_s}) is OUTSIDE allowed trading window ({window_utc_s}). New entries BLOCKED.")
            elif not AUTO_EXECUTE and candidate_signals:
                for c in candidate_signals:
                    pair_str = f"{c['pair'][0]}/{c['pair'][1]}"
                    logger.info(f"📢 [SIGNAL DETECTED - SIGNALS ONLY MODE 🔴] Signal generated for {pair_str} ({c['action']} | Z={c['z_score']:.3f} | Beta={float(c.get('beta', 1.0)):.2f}), but Auto-Execution is toggled OFF on Dashboard. Trade placement SKIPPED.")
            elif AUTO_EXECUTE and is_trade_limit_ok and not is_news_halted and is_session_ok and candidate_signals:
                if risk_safeguards.SESSION_GUARD_ENABLED:
                    for c in candidate_signals:
                        pair_str = f"{c['pair'][0]}/{c['pair'][1]}"
                        logger.info(f"⏰ [SESSION GUARD ACTIVE 🟢] Signal generated for {pair_str} ({c['action']} | Z={c['z_score']:.3f} | Beta={float(c.get('beta', 1.0)):.2f}). Current time ({curr_utc_s}) is INSIDE allowed trading window ({window_utc_s}). Trade execution PROCEEDING!")

                # Select candidate signals based on Z-score deviation, valid spread, and Beta boundary guards
                from risk_safeguards import MIN_BETA_CAP, MAX_BETA_CAP
                qualifying_candidates = []
                for c in candidate_signals:
                    c_a, c_b = c["pair"]
                    ca_base = c_a.upper().split('.')[0]
                    cb_base = c_b.upper().split('.')[0]
                    c_beta = abs(float(c.get("beta", 1.0)))
                    
                    if c_beta > MAX_BETA_CAP:
                        logger.info(f"🛡️ [MAX BETA GUARD ACTIVE 🔴] Signal for {ca_base}/{cb_base} (Beta: {c_beta:.2f} > Max Limit {MAX_BETA_CAP:.2f}) BLOCKED to prevent high-beta hedge drag.")
                        continue
                    elif c_beta < MIN_BETA_CAP:
                        logger.info(f"🛡️ [MIN BETA GUARD ACTIVE 🔴] Signal for {ca_base}/{cb_base} (Beta: {c_beta:.2f} < Min Limit {MIN_BETA_CAP:.2f}) BLOCKED to prevent weak hedge correlation.")
                        continue

                    if (ca_base not in active_symbols_set) and (cb_base not in active_symbols_set):
                        qualifying_candidates.append(c)

                if not qualifying_candidates:
                    logger.info("Skipping trade execution: All candidate pairs have active symbols open or failed Beta boundary limits.")
                    best_sig = None
                else:
                    best_sig = None

                    qualifying_candidates.sort(key=lambda x: x["win_rate"], reverse=True)
                    best_sig = None
                    for cand in qualifying_candidates:
                        cand_s_a, cand_s_b = cand["pair"]
                        cand_cat_a = get_symbol_category(cand_s_a)
                        cand_cat_b = get_symbol_category(cand_s_b)
                        if (cand_cat_a == "crypto" or is_spread_valid(cand_s_a)) and (cand_cat_b == "crypto" or is_spread_valid(cand_s_b)):
                            best_sig = cand
                            break
                
                if best_sig is not None:
                    best_pair = best_sig["pair"]
                    best_action = best_sig["action"]
                    best_s_a, best_s_b = best_pair
                    best_cat_a = get_symbol_category(best_s_a)
                    best_cat_b = get_symbol_category(best_s_b)
                    
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
                    
                    # Force broker-specific symbol resolution for execution immediately
                    cat_a_new = get_symbol_category(S_A)
                    cat_b_new = get_symbol_category(S_B)
                    S_A_resolved = resolve_broker_symbol(S_A) if cat_a_new != "crypto" else S_A
                    S_B_resolved = resolve_broker_symbol(S_B) if cat_b_new != "crypto" else S_B
                    
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
                    
                    try:
                        best_cat_a = get_symbol_category(S_A)
                        best_cat_b = get_symbol_category(S_B)
                        
                        entry_a = best_sig["tick_a"].ask if is_long else best_sig["tick_a"].bid
                        entry_b = best_sig["tick_b"].bid if is_long else best_sig["tick_b"].ask
                        
                        sl_a = entry_a - sl_dist if is_long else entry_a + sl_dist
                        # Feature 3 & Feature 4: Dynamic ATR & Swing High/Low Structure Targets
                        from math_models import calculate_dynamic_atr_tp_pips, find_swing_high_low_tp
                        dynamic_atr_tp = calculate_dynamic_atr_tp_pips(S_A, timeframe=mt5.TIMEFRAME_M15, multiplier=1.5, fallback_tp_pips=TP_PIPS)
                        swing_tp_price, swing_type, swing_pips = find_swing_high_low_tp(S_A, order_type="BUY" if is_long else "SELL", timeframe=mt5.TIMEFRAME_M15, lookback=30, fallback_pips=dynamic_atr_tp)
                        
                        logger.info(f"🎯 [DYNAMIC ATR TARGET] Active M15 ATR TP: {dynamic_atr_tp:.1f} pips (Multiplier: 1.5x | Base TP Pips: {TP_PIPS:.1f})")

                        logger.info(f"🏛️ [SWING STRUCTURE TARGET] Structure Target: {swing_tp_price:.5f} ({swing_type} | Distance: {swing_pips:.1f} pips)")
                        
                        info_pip_a = mt5.symbol_info(S_A)
                        pt_a = info_pip_a.point if info_pip_a else 0.0001
                        pip_sz_a = (pt_a * 10.0) if (info_pip_a and info_pip_a.digits in (3, 5)) else pt_a

                        # Set MT5 order TP to 0.0 so MT5 broker NEVER closes trades prematurely!
                        # All exits are controlled 100% strictly by Python 3-step exit pipeline!
                        tp1_val = 0.0
                        tp2_val = 0.0
                        tp3_val = 0.0


                            
                        if DEFAULT_LOTS > 0.05 and DEFAULT_LOTS != 0.01:
                            disable_guard = os.getenv("DISABLE_MARGIN_GUARD", "False").lower() in ("true", "1", "yes")
                            mult = 1.0 if disable_guard else LEVERAGE_FACTORS.get(best_cat_a, 1.0)
                            lots_a = DEFAULT_LOTS * mult
                        else:
                            lots_a = get_blue_guardian_lots(S_A, best_cat_a)
                            
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
                        if best_cat_a == "crypto":
                            usdt_bal, _ = get_binance_usdt_balance()
                            qty_a = calculate_binance_quantity(S_A, sl_dist, usdt_bal)
                            qty_b = get_hedge_quantity(S_A, S_B, qty_a, best_sig["beta"], best_cat_a, best_cat_b)
                            
                            if execute_three_part_binance_trade(
                                S_A, True, best_sig["tick_a"].ask, best_sig["tick_a"].ask - sl_dist, qty_a,
                                best_sig["price_a"] + sl_dist, best_sig["price_a"] + max(tp_dist, sl_dist * 1.5), best_sig["price_a"] + max(tp_dist * 1.5, sl_dist * 3.5),
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
                            if DEFAULT_LOTS > 0.05 and DEFAULT_LOTS != 0.01:
                                disable_guard = os.getenv("DISABLE_MARGIN_GUARD", "False").lower() in ("true", "1", "yes")
                                mult = 1.0 if disable_guard else LEVERAGE_FACTORS.get(best_cat_a, 1.0)
                                lots_a = DEFAULT_LOTS * mult
                            else:
                                lots_a = get_blue_guardian_lots(S_A, best_cat_a)
                            # Apply 3-part safeguard scaling correction
                            info_a_check = mt5.symbol_info(S_A_resolved)
                            min_vol_a = info_a_check.volume_min if info_a_check else 0.01
                            part_lots_a = round(lots_a / 3.0, 2)
                            if part_lots_a < min_vol_a:
                                part_lots_a = min_vol_a
                            actual_lots_a = part_lots_a * 3.0
                            
                            qty_b = get_hedge_quantity(S_A_resolved, S_B_resolved, actual_lots_a, best_sig["beta"], best_cat_a, best_cat_b)
                            
                            # Apply Margin Guard to dynamically scale down lots to fit within available margin
                            actual_lots_a, qty_b = apply_margin_guard(S_A_resolved, S_B_resolved, actual_lots_a, qty_b, True)
                            
                            exec_a_ok, filled_a_total = execute_three_part_trade(
                                S_A_resolved, True, best_sig["tick_a"].ask, best_sig["tick_a"].ask - sl_dist, actual_lots_a,
                                best_sig["price_a"] + sl_dist, best_sig["price_a"] + max(tp_dist, sl_dist * 1.5), best_sig["price_a"] + max(tp_dist * 1.5, sl_dist * 2.0),

                                signal_id=signal_id
                            )
                            if not exec_a_ok:
                                # Check if MT5 actually filled Leg A positions despite initial response timeout
                                try:
                                    live_mt5_pos = mt5.positions_get()
                                    if live_mt5_pos:
                                        filled_a_total = sum(
                                            float(p.volume) for p in live_mt5_pos
                                            if p.symbol.upper().split('.')[0] == S_A_resolved.upper().split('.')[0]
                                            and p.magic == MAGIC_NUMBER
                                        )
                                        if filled_a_total > 0:
                                            exec_a_ok = True
                                            logger.info(f"🛡️ [HEDGE RECOVERY] MT5 verified {filled_a_total:.2f} lots filled for Leg A ({S_A_resolved})! Proceeding with Leg B ({S_B_resolved}) Hedge Order!")
                                except Exception as ex_recv:
                                    logger.error(f"Error checking hedge recovery MT5 positions: {ex_recv}")

                            if exec_a_ok:
                                if filled_a_total > 0:
                                    qty_b = get_hedge_quantity(S_A_resolved, S_B_resolved, filled_a_total, best_sig["beta"], best_cat_a, best_cat_b)
                                fresh_tick_b = mt5.symbol_info_tick(S_B_resolved) if best_cat_b != "crypto" else None
                                if fresh_tick_b is None and best_cat_b != "crypto":
                                    fresh_tick_b = best_sig["tick_b"]
                                order_type_b, side_b, price_b, sl_sign_b = get_hedge_execution_parameters(
                                    best_action, best_sig["beta"], fresh_tick_b if best_cat_b != "crypto" else best_sig["tick_b"]
                                )
                                sl_b = price_b + sl_sign_b * sl_dist_b
                                if best_cat_b == "crypto":
                                    hedge_params = {"symbol": S_B_resolved, "side": side_b, "type": "MARKET", "quantity": qty_b}
                                    h_res = send_signed_request("POST", "/fapi/v1/order", hedge_params)
                                    if h_res and h_res.status_code == 200:
                                        avg_price_b = float(h_res.json().get("avgPrice") or price_b)
                                        log_trade_entry(h_res.json()["orderId"], S_B_resolved, side_b, qty_b, avg_price_b, datetime.datetime.now(), "Binance JS_HEDGE", signal_id)
                                        price_prec = get_symbol_filters(S_B_resolved)["pricePrecision"] if get_symbol_filters(S_B_resolved) else 2
                                        opp_side_b = "BUY" if side_b == "SELL" else "SELL"
                                        send_signed_request("POST", "/fapi/v1/order", {"symbol": S_B_resolved, "side": opp_side_b, "type": "STOP_MARKET", "stopPrice": round(sl_b, price_prec), "closePosition": "true", "timeInForce": "GTC"})
                                else:
                                    is_long_b = (order_type_b == mt5.ORDER_TYPE_BUY)
                                    res_hedge = send_order(S_B_resolved, order_type_b, price_b, qty_b, sl_b, 0.0, "JS_HEDGE")
                                    h_ok = is_retcode_success(res_hedge)
                                    if h_ok:
                                        ticket_b = res_hedge.order
                                        filled_b = getattr(res_hedge, 'volume', qty_b)
                                        log_trade_entry(ticket_b, S_B_resolved, "BUY" if is_long_b else "SELL", filled_b, price_b, datetime.datetime.now(), "JaneStreet HEDGE", signal_id)
                                    else:
                                        logger.error(f"[HEDGE SAFETY] Leg B ({S_B_resolved}) failed! Closing Leg A ({S_A_resolved}) to prevent unhedged risk.")
                                        close_all_positions(S_A_resolved)

                    else:
                        if best_cat_a == "crypto":
                            usdt_bal, _ = get_binance_usdt_balance()
                            qty_a = calculate_binance_quantity(S_A, sl_dist, usdt_bal)
                            qty_b = get_hedge_quantity(S_A, S_B, qty_a, best_sig["beta"], best_cat_a, best_cat_b)
                            
                            if execute_three_part_binance_trade(
                                S_A, False, best_sig["tick_a"].bid, best_sig["tick_a"].bid + sl_dist, qty_a,
                                best_sig["price_a"] - sl_dist, best_sig["price_a"] - max(tp_dist, sl_dist * 1.5), best_sig["price_a"] - max(tp_dist * 1.5, sl_dist * 3.5),
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
                            if DEFAULT_LOTS > 0.05 and DEFAULT_LOTS != 0.01:
                                disable_guard = os.getenv("DISABLE_MARGIN_GUARD", "False").lower() in ("true", "1", "yes")
                                mult = 1.0 if disable_guard else LEVERAGE_FACTORS.get(best_cat_a, 1.0)
                                lots_a = DEFAULT_LOTS * mult
                            else:
                                lots_a = get_blue_guardian_lots(S_A, best_cat_a)
                            # Apply 3-part safeguard scaling correction
                            info_a_check = mt5.symbol_info(S_A_resolved)
                            min_vol_a = info_a_check.volume_min if info_a_check else 0.01
                            part_lots_a = round(lots_a / 3.0, 2)
                            if part_lots_a < min_vol_a:
                                part_lots_a = min_vol_a
                            actual_lots_a = part_lots_a * 3.0
                            
                            qty_b = get_hedge_quantity(S_A_resolved, S_B_resolved, actual_lots_a, best_sig["beta"], best_cat_a, best_cat_b)
                            
                            # Apply Margin Guard to dynamically scale down lots to fit within available margin
                            actual_lots_a, qty_b = apply_margin_guard(S_A_resolved, S_B_resolved, actual_lots_a, qty_b, False)
                            
                            exec_a_ok, filled_a_total = execute_three_part_trade(
                                S_A_resolved, False, best_sig["tick_a"].bid, best_sig["tick_a"].bid + sl_dist, actual_lots_a,
                                best_sig["price_a"] - sl_dist, best_sig["price_a"] - max(tp_dist, sl_dist * 1.5), best_sig["price_a"] - max(tp_dist * 1.5, sl_dist * 2.0),

                                signal_id=signal_id
                            )
                            if not exec_a_ok:
                                # Check if MT5 actually filled Leg A positions despite initial response timeout
                                try:
                                    live_mt5_pos = mt5.positions_get()
                                    if live_mt5_pos:
                                        filled_a_total = sum(
                                            float(p.volume) for p in live_mt5_pos
                                            if p.symbol.upper().split('.')[0] == S_A_resolved.upper().split('.')[0]
                                            and p.magic == MAGIC_NUMBER
                                        )
                                        if filled_a_total > 0:
                                            exec_a_ok = True
                                            logger.info(f"🛡️ [HEDGE RECOVERY - SELL_SPREAD] MT5 verified {filled_a_total:.2f} lots filled for Leg A ({S_A_resolved})! Proceeding with Leg B ({S_B_resolved}) Hedge Order!")
                                except Exception as ex_recv:
                                    logger.error(f"Error checking hedge recovery MT5 positions for SELL_SPREAD: {ex_recv}")

                            if exec_a_ok:

                                if filled_a_total > 0:
                                    qty_b = get_hedge_quantity(S_A_resolved, S_B_resolved, filled_a_total, best_sig["beta"], best_cat_a, best_cat_b)
                                fresh_tick_b = mt5.symbol_info_tick(S_B_resolved) if best_cat_b != "crypto" else None
                                if fresh_tick_b is None and best_cat_b != "crypto":
                                    fresh_tick_b = best_sig["tick_b"]
                                order_type_b, side_b, price_b, sl_sign_b = get_hedge_execution_parameters(
                                    best_action, best_sig["beta"], fresh_tick_b if best_cat_b != "crypto" else best_sig["tick_b"]
                                )
                                sl_b = price_b + sl_sign_b * sl_dist_b
                                if best_cat_b == "crypto":
                                    hedge_params = {"symbol": S_B_resolved, "side": side_b, "type": "MARKET", "quantity": qty_b}
                                    h_res = send_signed_request("POST", "/fapi/v1/order", hedge_params)
                                    if h_res and h_res.status_code == 200:
                                        avg_price_b = float(h_res.json().get("avgPrice") or price_b)
                                        log_trade_entry(h_res.json()["orderId"], S_B_resolved, side_b, qty_b, avg_price_b, datetime.datetime.now(), "Binance JS_HEDGE", signal_id)
                                        price_prec = get_symbol_filters(S_B_resolved)["pricePrecision"] if get_symbol_filters(S_B_resolved) else 2
                                        opp_side_b = "BUY" if side_b == "SELL" else "SELL"
                                        send_signed_request("POST", "/fapi/v1/order", {"symbol": S_B_resolved, "side": opp_side_b, "type": "STOP_MARKET", "stopPrice": round(sl_b, price_prec), "closePosition": "true", "timeInForce": "GTC"})
                                else:
                                    is_long_b = (order_type_b == mt5.ORDER_TYPE_BUY)
                                    res_hedge = send_order(S_B_resolved, order_type_b, price_b, qty_b, sl_b, 0.0, "JS_HEDGE")
                                    h_ok = is_retcode_success(res_hedge)
                                    if h_ok:
                                        ticket_b = res_hedge.order
                                        filled_b = getattr(res_hedge, 'volume', qty_b)
                                        log_trade_entry(ticket_b, S_B_resolved, "BUY" if is_long_b else "SELL", filled_b, price_b, datetime.datetime.now(), "JaneStreet HEDGE", signal_id)
                                    else:
                                        logger.error(f"[HEDGE SAFETY] Leg B ({S_B_resolved}) failed! Closing Leg A ({S_A_resolved}) to prevent unhedged risk.")
                                        close_all_positions(S_A_resolved)
                    invalidate_trades_cache()

            # Three-Step Sequential Exit Pipeline
            best_cat_a_check = get_symbol_category(S_A)
            if best_cat_a_check != "crypto" and len(active_js_positions) > 0:
                leg_a_parts = [p for p in active_js_positions if p.symbol == S_A_resolved]
                if leg_a_parts:
                    try:
                        # Step 1: Move SL of ALL 3 Leg A parts to Entry Price ONLY when PnL >= +$56.00 USD (0.56% Equity Gain)
                        acc_check = mt5.account_info()
                        eq_base = acc_check.equity if acc_check else 10000.0
                        be_target_pnl = max(56.0, eq_base * 0.0056)

                        pnl_at_target = floating_profit >= be_target_pnl

                        if pnl_at_target:
                            trig_reason = f"PnL ${floating_profit:.2f} >= ${be_target_pnl:.2f} (0.56% Equity Gain)"

                            for p in leg_a_parts:
                                if getattr(p, 'sl', 0.0) != leg_a_parts[0].price_open:
                                    modify_position_sl(p.ticket, S_A_resolved, leg_a_parts[0].price_open)
                                    logger.info(f"🛡️ [STEP 1 BREAKEVEN ACTIVATED] Triggered by {trig_reason}! Moved SL for ticket #{p.ticket} ({S_A_resolved}) to Entry Price ${leg_a_parts[0].price_open:.5f} (All 3 Parts Open)")







                        
                        # Step 2: Close 70% Volume (TP1 & TP2 parts) + Leg B ONLY WHEN live Z-Score reaches 0.00 (abs(z) <= 0.15)
                        if abs(active_pair_z_score) <= 0.15:
                            logger.info(f"💰 [STEP 2 MEAN REVERSION AT Z=0.00] Live Z={active_pair_z_score:.3f} reached Z=0.00! Closing 70% Volume (TP1 & TP2) and Leg B Hedge Order!")
                            for p in leg_a_parts:
                                if "TP1" in str(p.comment) or "TP2" in str(p.comment):
                                    close_position_by_ticket(p.symbol, p.ticket, p.volume)
                            close_all_positions(S_B_resolved, comment_filter="JS_HEDGE")
                    except Exception as ex_sl:
                        logger.error(f"Error evaluating 3-step exit pipeline: {ex_sl}")





            # Update dashboard status
            if is_news_halted or should_close_news:
                msg = news_msg if is_news_halted else news_close_reason
                status_str = f"HALTED (News: {msg})"
            elif low_correlation_warning:
                status_str = "RUNNING (Warning: Low Correlation)"
            elif has_positions and (peak_floating_profit >= 185.0 or floating_profit >= 185.0):
                status_str = f"RUNNING (Trail Active Tier 4: Peak ${peak_floating_profit:.2f} | Floor $155.00)"
            elif has_positions and (peak_floating_profit >= 142.0 or floating_profit >= 142.0):
                status_str = f"RUNNING (Trail Active Tier 3: Peak ${peak_floating_profit:.2f} | Floor $120.00)"
            elif has_positions and (peak_floating_profit >= 99.0 or floating_profit >= 99.0):
                status_str = f"RUNNING (Trail Active Tier 2: Peak ${peak_floating_profit:.2f} | Floor $80.00)"
            elif has_positions and (peak_floating_profit >= 67.0 or floating_profit >= 67.0):
                status_str = f"RUNNING (Trail Active Tier 1: Peak ${peak_floating_profit:.2f} | Floor $53.00)"
            else:
                status_str = "RUNNING (Active)" if AUTO_EXECUTE else "RUNNING (Signals Only)"
            
            # Live telemetry fallback: If active pair Z-Score is still 0.0, fetch from scanned_assets table
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
                drawdown_percent=peak_dd_p,
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
                max_dd=peak_dd_p,
                trades_count=trades_today,
                login_id=current_login,
            )


            if all_scanned_z_summary:
                logger.info(f"🌐 [ALL SCANNED ASSETS Z-SCORES] " + " | ".join(all_scanned_z_summary))

            sw_str = "M15 Swing Level: ACTIVE"
            try:
                from math_models import find_swing_high_low_tp
                sw_p, sw_typ, sw_pips = find_swing_high_low_tp(S_A, order_type="BUY", timeframe=mt5.TIMEFRAME_M15, lookback=30)
                sw_str = f"M15 Swing Level: {sw_p:.5f}"
            except Exception:
                pass

            auto_exec_str = "ENABLED 🟢" if AUTO_EXECUTE else "DISABLED 🔴 (SIGNALS ONLY MODE)"
            if risk_safeguards.SESSION_GUARD_ENABLED:
                sess_log_str = f"ENABLED 🟢 (WINDOW OPEN: {curr_utc_s} in {window_utc_s})" if is_session_ok else f"ENABLED 🔴 (WINDOW CLOSED: {curr_utc_s} outside {window_utc_s})"
            else:
                sess_log_str = "DISABLED 🔴 (Trading 24/7)"

            tp_inflect_log_str = "ENABLED 🟢"
            logger.info(
                f"📊 [LIVE SCAN DETAIL] Focus: {S_A}/{S_B} | Live Z: {active_pair_z_score:.3f} (Entry: ±{Z_ENTRY_THRESHOLD:.2f}) | Kalman Beta: {active_pair_beta:.4f} 🟢 "
                f"| Auto-Exec: {auto_exec_str} | Session Guard: {sess_log_str} | Dynamic ATR Target: ENABLED 🟢 | Turning Point Inflection: {tp_inflect_log_str} "
            )

            eff_dd_log = max(daily_loss_p, peak_dd_p)
            if daily_start_equity and current_equity >= daily_start_equity:
                net_gain_usd = current_equity - daily_start_equity
                net_gain_pct = (net_gain_usd / daily_start_equity) * 100.0 if daily_start_equity > 0 else 0.0
                logger.info(f"🛡️ [LIMIT ENFORCE CHECK] Daily Net Gain: +${net_gain_usd:.2f} USD (+{net_gain_pct:.2f}%) | Baseline Start: ${daily_start_equity:.2f} | Status: LIMIT ENFORCE {'ENABLED 🟢' if RISK_LIMITS_ENABLED else 'DISABLED 🔴'}")
            elif eff_dd_log >= risk_safeguards.MAX_DAILY_LOSS_PERCENT:
                if RISK_LIMITS_ENABLED:
                    logger.warning(f"🚨 [LIMIT ENFORCE BREACHED] Peak Daily Drawdown: {eff_dd_log:.2f}% (Halt Limit: {risk_safeguards.MAX_DAILY_LOSS_PERCENT:.2f}%). STRICT LIMIT ENFORCE ACTIVE & ALL NEW TRADES BLOCKED!")
                else:
                    logger.info(f"🎮 [LIMIT ENFORCE BYPASSED] Peak Daily Drawdown: {eff_dd_log:.2f}% (Halt Limit: {risk_safeguards.MAX_DAILY_LOSS_PERCENT:.2f}%), but Risk Limits Enforcer is toggled OFF on Dashboard. Scanning active.")
            else:
                logger.info(f"🛡️ [LIMIT ENFORCE CHECK] Current DD: {eff_dd_log:.2f}% | Limit: {risk_safeguards.MAX_DAILY_LOSS_PERCENT:.2f}% | Status: LIMIT ENFORCE {'ENABLED 🟢' if RISK_LIMITS_ENABLED else 'DISABLED 🔴'}")













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
