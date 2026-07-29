import os
import sys
import time
import datetime
import logging
import MetaTrader5 as mt5
import numpy as np

# Ensure root directory is on the path to import main bot files
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Reconfigure stdout/stderr to UTF-8 to support terminal emojis on Windows console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from database import get_connection
from math_models import KalmanFilterRegression
from data_ingestion import initialize_mt5
from main import (
    get_symbol_category, get_pip_size, get_kf_parameters, 
    get_sl_distance, get_tp_distance, detect_smc_zones, 
    is_price_in_zones, calculate_obi, get_symbol_filters,
    EXPECTED_BETA_SIGN
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("scratch/mock_simulator.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("MockSimulator")

class MockTradeTracker:
    def __init__(self):
        self.active_trade = None
        self.trade_history = []
        
    def start_trade(self, trade_type, symbol_a, symbol_b, price_a, price_b, lots_a, lots_b, sl_a, tp1_a, tp2_a, tp3_a, entry_z, beta):
        self.active_trade = {
            "entry_time": datetime.datetime.now(),
            "type": trade_type,
            "symbol_a": symbol_a,
            "symbol_b": symbol_b,
            "entry_a": price_a,
            "entry_b": price_b,
            "lots_a": lots_a,
            "lots_b": lots_b,
            "sl_a": sl_a,
            "tp1_a": tp1_a,
            "tp2_a": tp2_a,
            "tp3_a": tp3_a,
            "tp1_hit": False,
            "tp2_hit": False,
            "tp3_hit": False,
            "sl_hit": False,
            "entry_z": entry_z,
            "beta": beta,
            "current_sl": sl_a
        }
        logger.info(f"🟢 [MOCK ENTRY] {trade_type} {symbol_a}/{symbol_b} entered at Z={entry_z:.3f} | Beta: {beta:.4f}")
        logger.info(f"    Leg A Price: {price_a:.5f} | SL: {sl_a:.5f} | TP1: {tp1_a:.5f} | TP2: {tp2_a:.5f} | TP3: {tp3_a:.5f}")
        logger.info(f"    Leg B Price: {price_b:.5f} | Lots A: {lots_a:.2f} | Lots B: {lots_b:.2f}")

    def update_live_trade(self, price_a, price_b, z_score, tp_exit_val):
        if not self.active_trade:
            return None

        t = self.active_trade
        # Calculate contract sizes
        cat_a = get_symbol_category(t["symbol_a"])
        cat_b = get_symbol_category(t["symbol_b"])
        
        info_a = mt5.symbol_info(t["symbol_a"])
        contract_a = info_a.trade_contract_size if info_a else 100000.0
        info_b = mt5.symbol_info(t["symbol_b"])
        contract_b = info_b.trade_contract_size if info_b else 100000.0

        # Calculate floating P&L
        mult_a = 1.0 if t["type"] == "BUY_SPREAD" else -1.0
        mult_b = -1.0 if t["type"] == "BUY_SPREAD" else 1.0 # opposite hedge direction

        pnl_a = (price_a - t["entry_a"]) * float(t["lots_a"]) * mult_a * contract_a
        pnl_b = (price_b - t["entry_b"]) * float(t["lots_b"]) * mult_b * contract_b
        total_pnl = pnl_a + pnl_b

        # Check exits
        exit_triggered = False
        exit_reason = ""
        close_price_a = price_a
        close_price_b = price_b

        # 1. Check Stop Loss (Leg A price action hits current SL)
        if t["type"] == "BUY_SPREAD" and price_a <= t["current_sl"]:
            exit_triggered = True
            exit_reason = f"STOP_LOSS_HIT (Price {price_a:.5f} <= SL {t['current_sl']:.5f})"
        elif t["type"] == "SELL_SPREAD" and price_a >= t["current_sl"]:
            exit_triggered = True
            exit_reason = f"STOP_LOSS_HIT (Price {price_a:.5f} >= SL {t['current_sl']:.5f})"

        # 2. Check Take Profits (scale-out trailing behaviour)
        if not exit_triggered:
            if t["type"] == "BUY_SPREAD":
                if not t["tp1_hit"] and price_a >= t["tp1_a"]:
                    t["tp1_hit"] = True
                    t["current_sl"] = t["entry_a"]  # Trailing to breakeven
                    logger.info(f"🎯 [MOCK TP1 HIT] Leg A price reached {price_a:.5f}. Trailing SL to entry: {t['entry_a']:.5f}")
                if not t["tp2_hit"] and price_a >= t["tp2_a"]:
                    t["tp2_hit"] = True
                    logger.info(f"🎯 [MOCK TP2 HIT] Leg A price reached {price_a:.5f}")
                if price_a >= t["tp3_a"]:
                    exit_triggered = True
                    exit_reason = f"TAKE_PROFIT_3_HIT (Price {price_a:.5f} >= TP3 {t['tp3_a']:.5f})"
            else: # SELL_SPREAD
                if not t["tp1_hit"] and price_a <= t["tp1_a"]:
                    t["tp1_hit"] = True
                    t["current_sl"] = t["entry_a"]  # Trailing to breakeven
                    logger.info(f"🎯 [MOCK TP1 HIT] Leg A price reached {price_a:.5f}. Trailing SL to entry: {t['entry_a']:.5f}")
                if not t["tp2_hit"] and price_a <= t["tp2_a"]:
                    t["tp2_hit"] = True
                    logger.info(f"🎯 [MOCK TP2 HIT] Leg A price reached {price_a:.5f}")
                if price_a <= t["tp3_a"]:
                    exit_triggered = True
                    exit_reason = f"TAKE_PROFIT_3_HIT (Price {price_a:.5f} <= TP3 {t['tp3_a']:.5f})"

        # 3. Check Z-Score Reversion Exit
        if not exit_triggered:
            if t["type"] == "BUY_SPREAD" and z_score >= tp_exit_val:
                exit_triggered = True
                exit_reason = f"Z_REVERSION_EXIT (Z={z_score:.3f} >= Exit threshold {tp_exit_val})"
            elif t["type"] == "SELL_SPREAD" and z_score <= -tp_exit_val:
                exit_triggered = True
                exit_reason = f"Z_REVERSION_EXIT (Z={z_score:.3f} <= Exit threshold {-tp_exit_val})"

        if exit_triggered:
            t["close_time"] = datetime.datetime.now()
            t["close_a"] = close_price_a
            t["close_b"] = close_price_b
            t["profit"] = total_pnl
            t["exit_reason"] = exit_reason
            
            logger.info(f"⏹ [MOCK EXIT] {t['type']} closed due to {exit_reason} | Profit: ${total_pnl:.2f}")
            self.trade_history.append(t)
            self.active_trade = None
            return t

        # Return live floating stats
        return {
            "pnl_a": pnl_a,
            "pnl_b": pnl_b,
            "total_pnl": total_pnl,
            "tp1_hit": t["tp1_hit"],
            "tp2_hit": t["tp2_hit"],
            "current_sl": t["current_sl"]
        }

def get_live_db_config():
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT active_pair, z_entry_threshold, sl_pips, tp_pips, 
                   smc_enabled, auto_execute, volatility_filter_enabled, 
                   knife_protection_enabled, obi_enabled, default_lots
            FROM bot_state 
            WHERE id = 1
        """)
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return {
                "active_pair": row[0],
                "z_entry_threshold": float(row[1]),
                "sl_pips": float(row[2]),
                "tp_pips": float(row[3]),
                "smc_enabled": bool(row[4]),
                "auto_execute": bool(row[5]),
                "volatility_filter_enabled": bool(row[6]),
                "knife_protection_enabled": bool(row[7]),
                "obi_enabled": bool(row[8]),
                "default_lots": float(row[9])
            }
    except Exception as e:
        logger.error(f"Error reading bot_state DB config: {e}")
    return None

def main_loop():
    logger.info("Initializing MetaTrader 5...")
    initialize_mt5()

    # Initialize tracker
    tracker = MockTradeTracker()
    
    # Warm-up Kalman Filter for current pair
    current_pair = ""
    kf = None
    
    logger.info("Mock Simulator started. Listening to market ticks...")
    
    while True:
        try:
            config = get_live_db_config()
            if not config:
                time.sleep(5)
                continue
                
            active_pair = config["active_pair"]
            sym_a, sym_b = active_pair.split('/')
            
            # Resolve brokers/suffixes
            # Look up symbols in MT5
            sym_a_resolved = sym_a
            sym_b_resolved = sym_b
            for s in mt5.symbols_get():
                if s.name.upper().startswith(sym_a.upper()):
                    sym_a_resolved = s.name
                if s.name.upper().startswith(sym_b.upper()):
                    sym_b_resolved = s.name

            # Re-initialize Kalman filter if pair changed
            if active_pair != current_pair or kf is None:
                logger.info(f"Switching pair to {active_pair}. Resolving as {sym_a_resolved}/{sym_b_resolved} in MT5.")
                current_pair = active_pair
                q_val, r_val = get_kf_parameters(sym_a_resolved)
                kf = KalmanFilterRegression(transition_covariance=q_val, observation_covariance=r_val)
                
                # Fetch 200 bars of historical close prices to warm up the filter
                rates_a = mt5.copy_rates_from_pos(sym_a_resolved, mt5.TIMEFRAME_M5, 0, 200)
                rates_b = mt5.copy_rates_from_pos(sym_b_resolved, mt5.TIMEFRAME_M5, 0, 200)
                
                if rates_a is not None and rates_b is not None:
                    # Align timestamps
                    df_a = pd.DataFrame(rates_a)
                    df_b = pd.DataFrame(rates_b)
                    df_merged = pd.merge(df_a, df_b, on='time', suffixes=('_a', '_b'))
                    logger.info(f"Warming up Kalman Filter with {len(df_merged)} synchronized 5M bars...")
                    for idx, row_m in df_merged.iterrows():
                        kf.update(float(row_m['close_b']), float(row_m['close_a']))
                else:
                    logger.warning("Failed to warm up Kalman Filter. Initialization might be unstable.")
            
            # Fetch live ticks
            tick_a = mt5.symbol_info_tick(sym_a_resolved)
            tick_b = mt5.symbol_info_tick(sym_b_resolved)
            
            if not tick_a or not tick_b:
                logger.warning(f"Ticks not received for {sym_a_resolved} or {sym_b_resolved}")
                time.sleep(2)
                continue

            p_a = (tick_a.bid + tick_a.ask) / 2.0
            p_b = (tick_b.bid + tick_b.ask) / 2.0
            
            # Run Kalman update step
            beta, alpha, spread, z = kf.update(p_b, p_a)
            z_velocity = kf.get_velocity(k=3)
            dynamic_z_entry = kf.get_dynamic_z_entry(config["z_entry_threshold"])
            
            # Process exits or floating stats
            live_status = None
            if tracker.active_trade:
                # Retrieve strategies exit threshold (default is 0.0)
                live_status = tracker.update_live_trade(p_a, p_b, z, tp_exit_val=0.0)
            
            # Check entry signal if no active trade
            if not tracker.active_trade:
                cat_a = get_symbol_category(sym_a_resolved)
                z_vel_lim = 0.02 if cat_a == "forex" else 0.08 if cat_a == "metals" else 0.05
                
                # Check thresholds
                effective_dyn_z = dynamic_z_entry if config["volatility_filter_enabled"] else config["z_entry_threshold"]
                
                pass_z_buy = z < -effective_dyn_z
                pass_z_sell = z > effective_dyn_z
                
                pass_vel_buy = (z_velocity > -z_vel_lim) if config["knife_protection_enabled"] else True
                pass_vel_sell = (z_velocity < z_vel_lim) if config["knife_protection_enabled"] else True
                
                # Mock OBI & SMC (default True for simulator simplicity)
                pass_obi_buy = True
                pass_obi_sell = True
                pass_smc_buy = True
                pass_smc_sell = True

                # Check beta sign
                expected_sign = EXPECTED_BETA_SIGN.get(current_pair, 1)
                beta_sign = 1 if beta >= 0 else -1
                
                if beta_sign == expected_sign and abs(beta) >= 0.05:
                    if pass_z_buy and pass_vel_buy and pass_obi_buy and pass_smc_buy:
                        # Simulated BUY Spread Entry
                        lots_a = config["default_lots"] if config["default_lots"] > 0 else 0.15
                        # Calculate hedge lots
                        info_a_check = mt5.symbol_info(sym_a_resolved)
                        contract_size_a = info_a_check.trade_contract_size if info_a_check else 100000.0
                        info_b_check = mt5.symbol_info(sym_b_resolved)
                        contract_size_b = info_b_check.trade_contract_size if info_b_check else 100000.0
                        lots_b = round(lots_a * abs(beta) * (contract_size_a / contract_size_b), 2)
                        
                        # SL & TP calculations
                        sl_dist = get_sl_distance(sym_a_resolved, p_a, config["sl_pips"])
                        tp_dist = get_tp_distance(sym_a_resolved, p_a, config["tp_pips"])
                        
                        sl_a = p_a - sl_dist
                        tp1_a = p_a + tp_dist
                        tp2_a = p_a + tp_dist * 1.5
                        tp3_a = p_a + tp_dist * 3.5
                        
                        tracker.start_trade(
                            "BUY_SPREAD", sym_a_resolved, sym_b_resolved, 
                            tick_a.ask, tick_b.bid, lots_a, lots_b, 
                            sl_a, tp1_a, tp2_a, tp3_a, z, beta
                        )
                        
                    elif pass_z_sell and pass_vel_sell and pass_obi_sell and pass_smc_sell:
                        # Simulated SELL Spread Entry
                        lots_a = config["default_lots"] if config["default_lots"] > 0 else 0.15
                        # Calculate hedge lots
                        info_a_check = mt5.symbol_info(sym_a_resolved)
                        contract_size_a = info_a_check.trade_contract_size if info_a_check else 100000.0
                        info_b_check = mt5.symbol_info(sym_b_resolved)
                        contract_size_b = info_b_check.trade_contract_size if info_b_check else 100000.0
                        lots_b = round(lots_a * abs(beta) * (contract_size_a / contract_size_b), 2)
                        
                        # SL & TP calculations
                        sl_dist = get_sl_distance(sym_a_resolved, p_a, config["sl_pips"])
                        tp_dist = get_tp_distance(sym_a_resolved, p_a, config["tp_pips"])
                        
                        sl_a = p_a + sl_dist
                        tp1_a = p_a - tp_dist
                        tp2_a = p_a - tp_dist * 1.5
                        tp3_a = p_a - tp_dist * 3.5
                        
                        tracker.start_trade(
                            "SELL_SPREAD", sym_a_resolved, sym_b_resolved, 
                            tick_a.bid, tick_b.ask, lots_a, lots_b, 
                            sl_a, tp1_a, tp2_a, tp3_a, z, beta
                        )

            # --- RENDER MOCK TELEMETRY TERMINAL DASHBOARD ---
            os.system('cls' if os.name == 'nt' else 'clear')
            print("=========================================================================")
            print(f"        JANE STREET TRADING SYSTEM - MOCK SIMULATION PORTAL")
            print("=========================================================================")
            print(f"  Live Local Time : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"  Selected Pair   : {active_pair} ({sym_a_resolved}/{sym_b_resolved})")
            print(f"  Live Z-Score    : {z:+.4f} | Beta: {beta:.4f} | Z-Velocity: {z_velocity:+.4f}")
            print(f"  Entry Threshold : {config['z_entry_threshold']:.2f} (Dynamic Threshold: {effective_dyn_z:.2f})")
            print(f"  SMC Confluence  : {'ENABLED' if config['smc_enabled'] else 'DISABLED'}")
            print(f"  Knife / OBI Prot: {'ENABLED' if config['knife_protection_enabled'] else 'DISABLED'} / {'ENABLED' if config['obi_enabled'] else 'DISABLED'}")
            print("=========================================================================")
            
            if tracker.active_trade:
                t = tracker.active_trade
                print(f"  🔥 ACTIVE SIMULATED TRADE")
                print(f"  Type          : {t['type']} (Z={t['entry_z']:+.3f})")
                print(f"  Entry Time    : {t['entry_time'].strftime('%H:%M:%S')}")
                print(f"  Current PNL   : ${live_status['total_pnl']:+.2f} (Leg A: ${live_status['pnl_a']:+.2f} | Leg B: ${live_status['pnl_b']:+.2f})")
                print(f"  Leg A Price   : {p_a:.5f} (Entry: {t['entry_a']:.5f} | Current SL: {live_status['current_sl']:.5f})")
                print(f"  Leg B Price   : {p_b:.5f} (Entry: {t['entry_b']:.5f})")
                print(f"  TP Targets    : TP1 (Hit: {live_status['tp1_hit']}) | TP2 (Hit: {live_status['tp2_hit']}) | TP3 (Target: {t['tp3_a']:.5f})")
            else:
                print("  📭 NO ACTIVE SIMULATED TRADES (Searching for signals...)")
                
            print("=========================================================================")
            print("  📊 SIMULATED HISTORICAL LOGS (Last 5 Closed Mock Trades)")
            print("=========================================================================")
            if not tracker.trade_history:
                print("  No closed mock trades logged yet.")
            else:
                for h in tracker.trade_history[-5:]:
                    print(f"  [{h['close_time'].strftime('%H:%M:%S')}] {h['type']} | P&L: ${h['profit']:+.2f} | Reason: {h['exit_reason']}")
            print("=========================================================================")
            
            time.sleep(1)

        except KeyboardInterrupt:
            logger.info("Mock simulator stopped by user.")
            break
        except Exception as loop_ex:
            logger.error(f"Error in mock simulator loop: {loop_ex}")
            time.sleep(2)
            
    mt5.shutdown()

if __name__ == "__main__":
    # Ensure pandas is imported locally inside the setup
    import pandas as pd
    main_loop()
