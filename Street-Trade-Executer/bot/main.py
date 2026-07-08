import MetaTrader5 as mt5
import time
import datetime
import os
import logging
import json
import threading
import requests

from math_models import KalmanFilterRegression, calculate_obi
from data_ingestion import initialize_mt5, check_and_subscribe_symbol, get_live_ticks, get_market_book, shutdown_mt5, get_rates_df
from risk_safeguards import check_drawdown_limit, calculate_lots, is_spread_valid, get_trades_count_today, MAX_DAILY_TRADES, invalidate_trades_cache
from execution_bot import execute_three_part_trade, close_all_positions, modify_sl_for_trade, check_closed_trades, MAGIC_NUMBER, send_order
from smc_indicators import detect_smc_zones, is_price_in_zones
from database import log_signal, get_connection, update_bot_state, update_daily_metrics, log_fvg_zones, get_auto_execute

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
        logger.info(f"Saved config: {pair_str}")
    except Exception as e:
        logger.error(f"Error saving config: {e}")

def fetch_db_config():
    """
    Reads active_pair, sl_pips, smc_enabled, and auto_execute from the dashboard DB
    via the /api/config endpoint. Updates shared_config.json if changed.
    Returns (active_pair, sl_pips, smc_enabled, auto_execute) or None on failure.
    """
    try:
        resp = requests.get(f"{DASHBOARD_API_URL}/config", timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            return (
                data.get("activePair", "EURUSD/GBPUSD"),
                float(data.get("slPips", 10)),
                bool(data.get("smcEnabled", True)),
                bool(data.get("autoExecute", True)),
            )
    except Exception as e:
        logger.warning(f"Could not fetch DB config: {e}")
    return None


def poll_manual_commands(tick_a, tick_b, sl_pips: float):
    """
    Checks for pending manual trade commands from the dashboard and executes them via MT5.
    Acks each command as EXECUTED or FAILED.
    Manual commands always execute regardless of the auto_execute flag.
    """
    try:
        resp = requests.get(f"{DASHBOARD_API_URL}/commands/pending", timeout=3)
        if resp.status_code != 200:
            return
        commands = resp.json()
        for cmd in commands:
            cmd_id = cmd["id"]
            symbol = cmd["symbol"]
            direction = cmd["direction"]
            lots = float(cmd["lots"])
            cmd_sl = float(cmd["slPips"]) if cmd.get("slPips") else sl_pips
            cmd_tp = float(cmd["tpPips"]) if cmd.get("tpPips") else cmd_sl * 2
            comment = cmd.get("comment") or f"MANUAL_{direction}"

            try:
                check_and_subscribe_symbol(symbol)
                tick = mt5.symbol_info_tick(symbol)
                if tick is None:
                    raise RuntimeError(f"No tick data for {symbol}")

                pip_size = 0.001 if "JPY" in symbol else 0.0001
                sl_dist = cmd_sl * pip_size
                tp_dist = cmd_tp * pip_size

                if direction == "BUY":
                    price = tick.ask
                    sl_price = price - sl_dist
                    tp_price = price + tp_dist
                    order_type = mt5.ORDER_TYPE_BUY
                else:
                    price = tick.bid
                    sl_price = price + sl_dist
                    tp_price = price - tp_dist
                    order_type = mt5.ORDER_TYPE_SELL

                ok = send_order(symbol, order_type, price, lots, sl_price, tp_price, comment)
                status = "EXECUTED" if ok else "FAILED"
                err_msg = None if ok else "MT5 order rejected"

            except Exception as e:
                status = "FAILED"
                err_msg = str(e)
                logger.error(f"Manual trade error [{cmd_id}]: {e}")

            try:
                requests.post(
                    f"{DASHBOARD_API_URL}/commands/{cmd_id}/ack",
                    json={"status": status, "errorMsg": err_msg},
                    timeout=3,
                )
                logger.info(f"Command {cmd_id} ({direction} {symbol} {lots}lots): {status}")
            except Exception as ack_err:
                logger.error(f"Ack failed for command {cmd_id}: {ack_err}")

    except Exception as e:
        logger.warning(f"poll_manual_commands error: {e}")


Z_ENTRY_THRESHOLD = 2.0
Z_EXIT_MEAN = 0.0
REQUIRE_SMC_CONFLUENCE = True
AUTO_EXECUTE = True          # toggled from dashboard via DB
SMC_TIMEFRAME = mt5.TIMEFRAME_M5
LOOP_INTERVAL = 2

# BUG FIX 2: Fixed SL in pips instead of 3x bid-ask spread
SL_PIPS = 10.0
SL_PIPS_JPY = 0.10

def get_sl_distance(symbol: str, sl_pips_override: float = None) -> float:
    """
    Returns SL distance in price units. Uses dashboard-configured sl_pips value.
    BUG FIX: Replaces original sl_dist = 3.0 * spread (~0.6 pips, broker-rejected).
    """
    pips = sl_pips_override if sl_pips_override else SL_PIPS
    pip_size = 0.001 if "JPY" in symbol else 0.0001
    return pips * pip_size


# ==============================================================================
# MAIN TRADING ENGINE RUN LOOP
# ==============================================================================
def main():
    print("=========================================")
    print("   JANE STREET QUANT BOT INITIALIZING    ")
    print("=========================================\n")

    global REQUIRE_SMC_CONFLUENCE, SL_PIPS, AUTO_EXECUTE

    load_config()

    acc_info = initialize_mt5()
    kf = KalmanFilterRegression(transition_covariance=1e-5, observation_covariance=1e-3)

    is_halted = False
    smc_update_counter = 0
    active_zones = None
    last_processed_pair = ""
    daily_start_equity = None
    db_config_counter = 0

    logger.info("Quantitative core pipeline active.")

    while True:
        try:
            if not mt5.initialize():
                time.sleep(5)
                continue

            acc_info = mt5.account_info()
            if acc_info is None:
                time.sleep(5)
                continue

            # ── DB CONFIG SYNC (every ~10s) ─────────────────────────────────
            if db_config_counter % 5 == 0:
                db_cfg = fetch_db_config()
                if db_cfg:
                    new_pair, new_sl, new_smc, new_auto_exec = db_cfg
                    parts = new_pair.split("/")
                    if len(parts) == 2 and parts[0] != parts[1]:
                        if GLOBAL_CONFIG["SYMBOL_A"] != parts[0] or GLOBAL_CONFIG["SYMBOL_B"] != parts[1]:
                            logger.info(f"DB config update — switching to {new_pair}")
                            GLOBAL_CONFIG["SYMBOL_A"] = parts[0]
                            GLOBAL_CONFIG["SYMBOL_B"] = parts[1]
                            save_config(new_pair)
                    SL_PIPS = new_sl
                    REQUIRE_SMC_CONFLUENCE = new_smc
                    if AUTO_EXECUTE != new_auto_exec:
                        AUTO_EXECUTE = new_auto_exec
                        logger.info(f"Auto-execute: {'ENABLED' if AUTO_EXECUTE else 'DISABLED (signals only)'}")
            db_config_counter += 1

            S_A = GLOBAL_CONFIG["SYMBOL_A"]
            S_B = GLOBAL_CONFIG["SYMBOL_B"]
            current_pair_context = f"{S_A}/{S_B}"

            if current_pair_context != last_processed_pair:
                logger.info(f"Switching to: Leg A={S_A} | Leg B={S_B}")
                check_and_subscribe_symbol(S_A)
                check_and_subscribe_symbol(S_B)
                kf = KalmanFilterRegression(transition_covariance=1e-5, observation_covariance=1e-3)
                active_zones = None
                last_processed_pair = current_pair_context

            is_halted, daily_loss_p = check_drawdown_limit(acc_info)

            if daily_start_equity is None:
                daily_start_equity = acc_info.equity

            if is_halted:
                close_all_positions(S_A)
                close_all_positions(S_B)
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

            check_closed_trades(S_A)
            check_closed_trades(S_B)

            # ── SMC / FVG ZONE SCAN (every 10 loops ≈ 20s) ──────────────────
            if active_zones is None or smc_update_counter >= 10:
                try:
                    rates_df = get_rates_df(S_A, SMC_TIMEFRAME, count=100)
                    if rates_df is not None and not rates_df.empty:
                        active_zones = detect_smc_zones(rates_df)
                        # Write live FVG/OB/Breaker/iFVG zones to DB for dashboard display
                        log_fvg_zones(S_A, active_zones)
                    smc_update_counter = 0
                except Exception as e:
                    logger.error(f"SMC scan error: {e}")
            else:
                smc_update_counter += 1

            tick_a = get_live_ticks(S_A)
            tick_b = get_live_ticks(S_B)
            bids_a, asks_a = get_market_book(S_A)
            bids_b, asks_b = get_market_book(S_B)

            if tick_a is None or tick_b is None:
                time.sleep(LOOP_INTERVAL)
                continue

            price_a = (tick_a.bid + tick_a.ask) / 2.0
            price_b = (tick_b.bid + tick_b.ask) / 2.0

            beta, alpha, spread, z_score = kf.update(price_b, price_a)
            obi_a = calculate_obi(bids_a, asks_a, depth=5)
            obi_b = calculate_obi(bids_b, asks_b, depth=5)
            net_obi = obi_a - obi_b

            action = "NONE"
            if z_score < -Z_ENTRY_THRESHOLD:
                action = "BUY_SPREAD"
            elif z_score > Z_ENTRY_THRESHOLD:
                action = "SELL_SPREAD"

            if action != "NONE":
                log_signal(S_A, S_B, price_a, price_b, beta, alpha, z_score, net_obi, action)

            trades_today = get_trades_count_today()
            positions = mt5.positions_get()
            active_js_positions = [p for p in positions if p.magic == MAGIC_NUMBER] if positions else []
            floating_profit = sum(p.profit for p in active_js_positions)

            # ── MANUAL TRADE COMMANDS (always active) ───────────────────────
            poll_manual_commands(tick_a, tick_b, SL_PIPS)

            # ── ALGO TRADING (only when AUTO_EXECUTE is ON) ──────────────────
            if AUTO_EXECUTE and len(active_js_positions) == 0 and trades_today < MAX_DAILY_TRADES:
                if is_spread_valid(S_A) and is_spread_valid(S_B):
                    in_bullish_zone = True
                    in_bearish_zone = True

                    if REQUIRE_SMC_CONFLUENCE and active_zones is not None:
                        in_bullish_zone = any(
                            is_price_in_zones(price_a, active_zones.get(k, []))
                            for k in ['bullish_ob', 'bullish_breaker', 'bullish_fvg', 'bullish_ifvg']
                        )
                        in_bearish_zone = any(
                            is_price_in_zones(price_a, active_zones.get(k, []))
                            for k in ['bearish_ob', 'bearish_breaker', 'bearish_fvg', 'bearish_ifvg']
                        )
                    elif REQUIRE_SMC_CONFLUENCE and active_zones is None:
                        in_bullish_zone = False
                        in_bearish_zone = False

                    # BUG FIX 2: use get_sl_distance() — fixed pips, not 3x spread
                    sl_dist = get_sl_distance(S_A, SL_PIPS)

                    if z_score < -Z_ENTRY_THRESHOLD and net_obi > 0.15 and in_bullish_zone:
                        lots_a = calculate_lots(S_A, sl_dist, acc_info)
                        lots_b = round(lots_a * abs(beta) * (price_a / price_b), 2)
                        if execute_three_part_trade(
                            S_A, True, tick_a.ask, tick_a.ask - sl_dist, lots_a,
                            price_a + sl_dist, price_a + sl_dist * 2, price_a + sl_dist * 3.5
                        ):
                            send_order(S_B, mt5.ORDER_TYPE_SELL, tick_b.bid, lots_b, 0.0, 0.0, "JS_HEDGE")
                            invalidate_trades_cache()

                    elif z_score > Z_ENTRY_THRESHOLD and net_obi < -0.15 and in_bearish_zone:
                        lots_a = calculate_lots(S_A, sl_dist, acc_info)
                        lots_b = round(lots_a * abs(beta) * (price_a / price_b), 2)
                        if execute_three_part_trade(
                            S_A, False, tick_a.bid, tick_a.bid + sl_dist, lots_a,
                            price_a - sl_dist, price_a - sl_dist * 2, price_a - sl_dist * 3.5
                        ):
                            send_order(S_B, mt5.ORDER_TYPE_BUY, tick_b.ask, lots_b, 0.0, 0.0, "JS_HEDGE")
                            invalidate_trades_cache()

            elif len(active_js_positions) > 0:
                leg_a_parts = [p for p in active_js_positions if p.symbol == S_A]
                comments = [p.comment for p in leg_a_parts]
                if not any("JS_TP1" in c for c in comments) and leg_a_parts:
                    modify_sl_for_trade(S_A, leg_a_parts[0].price_open)

            # ── DASHBOARD HEARTBEAT ──────────────────────────────────────────
            status_str = "RUNNING (Active)" if AUTO_EXECUTE else "RUNNING (Signals Only)"
            update_bot_state(
                active_pair=current_pair_context,
                system_status=status_str,
                equity=acc_info.equity,
                drawdown_percent=daily_loss_p,
                floating_profit=floating_profit,
                z_score=z_score,
                hedge_ratio=beta,
                obi_a=obi_a,
                obi_b=obi_b,
                trades_today=trades_today,
                sl_pips=SL_PIPS,
            )

            update_daily_metrics(
                datetime.date.today(),
                start_equity=daily_start_equity,
                current_equity=acc_info.equity,
                max_dd=daily_loss_p,
                trades_count=trades_today,
            )

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
