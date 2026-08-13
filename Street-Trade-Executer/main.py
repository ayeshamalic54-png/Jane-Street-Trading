import MetaTrader5 as mt5
import time
import datetime
import os
import logging
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from math_models import KalmanFilterRegression, calculate_obi
from data_ingestion import initialize_mt5, check_and_subscribe_symbol, get_live_ticks, get_market_book, shutdown_mt5, get_rates_df
from risk_safeguards import check_drawdown_limit, calculate_lots, is_spread_valid, get_trades_count_today, MAX_DAILY_TRADES, invalidate_trades_cache
from execution_bot import execute_three_part_trade, close_all_positions, modify_sl_for_trade, check_closed_trades, MAGIC_NUMBER, send_order
from smc_indicators import detect_smc_zones, is_price_in_zones
from database import log_signal, get_connection

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
# GLOBAL STATE (DYNAMIC COIN SELECTION) & PERSISTENCE
# ==============================================================================
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shared_config.json")

# default pairs jo boot hote hi chalenge
GLOBAL_CONFIG = {
    "SYMBOL_A": "EURUSD",
    "SYMBOL_B": "GBPUSD"
}

def load_config():
    global GLOBAL_CONFIG
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                active_pair = data.get("active_pair", "EURUSD/GBPUSD")
                parts = active_pair.split('/')
                if len(parts) == 2:
                    GLOBAL_CONFIG["SYMBOL_A"] = parts[0].strip()
                    GLOBAL_CONFIG["SYMBOL_B"] = parts[1].strip()
                    logger.info(f"Loaded persistent coin selection: Leg A={GLOBAL_CONFIG['SYMBOL_A']} | Leg B={GLOBAL_CONFIG['SYMBOL_B']}")
        except Exception as e:
            logger.error(f"Error loading persistent config: {e}")

def save_config(pair_str):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"active_pair": pair_str}, f)
        logger.info(f"Saved persistent coin selection: {pair_str}")
    except Exception as e:
        logger.error(f"Error saving persistent config: {e}")

Z_ENTRY_THRESHOLD = 2.0
Z_EXIT_MEAN = 0.0
REQUIRE_SMC_CONFLUENCE = True
SMC_TIMEFRAME = mt5.TIMEFRAME_M5
LOOP_INTERVAL = 2
DASHBOARD_FILE = "dashboard.html"

# Thread-safe data storage dashboard sharing ke liye
live_dashboard_data = {
    "current_coin": "EURUSD",
    "last_update": "-",
    "system_status": "STARTING...",
    "z_score": 0.0,
    "hedge_ratio": 0.0,
    "obi_bid": "0.00",
    "obi_ask": "0.00",
    "equity": 0.0,
    "drawdown": 0.0,
    "trades_today": 0,
    "max_trades": MAX_DAILY_TRADES,
    "floating_profit": 0.0,
    "zones": [],
    "positions": [],
    "history": []
}

# Caching variables for DB recent trade history to prevent connection abuse
last_db_history = []
last_db_history_time = 0

# ==============================================================================
# LIGHTWEIGHT API SERVER FOR DASHBOARD
# ==============================================================================
class DashboardAPIHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return # Terminal logs saaf rakhne ke liye default requests suppress ki hain
        
    def do_OPTIONS(self):
        # CORS permissions taake browser block na kare
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path == '/api/data':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(live_dashboard_data).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path == '/api/change_coin':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                params = json.loads(post_data.decode('utf-8'))
                coin_pair = params.get('pair', 'EURUSD/GBPUSD')
                
                # Pair split karke configuration dynamically update karein
                parts = coin_pair.split('/')
                if len(parts) == 2:
                    GLOBAL_CONFIG["SYMBOL_A"] = parts[0].strip()
                    GLOBAL_CONFIG["SYMBOL_B"] = parts[1].strip()
                    save_config(coin_pair)
                    logger.info(f"DASHBOARD TRIGGER: Switched target assets to Leg A: {GLOBAL_CONFIG['SYMBOL_A']} | Leg B: {GLOBAL_CONFIG['SYMBOL_B']}")
                    
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "success", "msg": f"Switched to {coin_pair}"}).encode('utf-8'))
                    return
            except Exception as e:
                logger.error(f"Failed to parse change_coin post request: {e}")
            
            self.send_response(400)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b"Bad Request")

def run_api_server():
    server = ThreadingHTTPServer(('localhost', 8081), DashboardAPIHandler) # API runs on 8081
    print("-> Background API Server listening on http://localhost:8081")
    server.serve_forever()

# ==============================================================================
# DATA ENGINE COMPILER (PREVENTS OVERWRITING HTML RADICALLY)
# ==============================================================================
def update_dashboard_state(acc_info, daily_loss_p, z_score, beta, alpha, spread, obi_a, obi_b, trades_today, is_halted, active_zones=None):
    """Saves telemetry variables directly to memory state for immediate JSON API sync."""
    global live_dashboard_data, last_db_history, last_db_history_time
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 1. Base Variables
    live_dashboard_data["current_coin"] = f"{GLOBAL_CONFIG['SYMBOL_A']} vs {GLOBAL_CONFIG['SYMBOL_B']}"
    live_dashboard_data["last_update"] = now_str
    live_dashboard_data["system_status"] = "HALTED (Max Loss)" if is_halted else "RUNNING (Active)"
    live_dashboard_data["z_score"] = z_score
    live_dashboard_data["hedge_ratio"] = beta
    live_dashboard_data["obi_bid"] = f"{obi_a:.2f}"
    live_dashboard_data["obi_ask"] = f"{obi_b:.2f}"
    live_dashboard_data["equity"] = acc_info.equity if acc_info else 0.0
    live_dashboard_data["drawdown"] = daily_loss_p
    live_dashboard_data["trades_today"] = trades_today

    # 2. Extract Active Positions
    positions = mt5.positions_get()
    pos_list = []
    total_profit = 0.0
    if positions:
        for p in positions:
            if p.magic == MAGIC_NUMBER:
                total_profit += p.profit
                pos_list.append({
                    "ticket": p.ticket,
                    "symbol": p.symbol,
                    "type": "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
                    "lots": round(p.volume, 2),
                    "entry": round(p.price_open, 5),
                    "current": round(p.price_current, 5),
                    "profit": round(p.profit, 2),
                    "comment": p.comment
                })
    live_dashboard_data["floating_profit"] = total_profit
    live_dashboard_data["positions"] = pos_list

    # 3. DB Recent History (Throttled to once every 15 seconds)
    now_ts = time.time()
    if not last_db_history or now_ts - last_db_history_time >= 15.0:
        hist_list = []
        conn = None
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT ticket, symbol, order_type, lots, entry_price, close_price, profit, comment FROM trades ORDER BY entry_time DESC LIMIT 5")
            for r in cur.fetchall():
                hist_list.append({
                    "ticket": r[0], "symbol": r[1], "type": r[2], "lots": float(r[3]),
                    "entry": float(r[4]), "close": float(r[5]) if r[5] else 0.0,
                    "profit": float(r[6]) if r[6] else 0.0, "comment": r[7]
                })
            cur.close()
            last_db_history = hist_list
            last_db_history_time = now_ts
        except Exception as e:
            pass
        finally:
            if conn: conn.close()
    live_dashboard_data["history"] = last_db_history

    # 4. Active SMC Zones Parsing
    zone_list = []
    if active_zones:
        for low, high in active_zones.get('bullish_ob', []): zone_list.append({"type": "OB", "label": "ðŸŸ¢ OB", "range": f"{low:.5f}-{high:.5f}"})
        for low, high in active_zones.get('bullish_fvg', []): zone_list.append({"type": "FVG", "label": "ðŸŸ¢ FVG", "range": f"{low:.5f}-{high:.5f}"})
        for low, high in active_zones.get('bearish_ob', []): zone_list.append({"type": "OB", "label": "ðŸ”´ OB", "range": f"{low:.5f}-{high:.5f}"})
        for low, high in active_zones.get('bearish_fvg', []): zone_list.append({"type": "FVG", "label": "ðŸ”´ FVG", "range": f"{low:.5f}-{high:.5f}"})
    live_dashboard_data["zones"] = zone_list

# ==============================================================================
# MAIN TRADING ENGINE RUN LOOP
# ==============================================================================
def main():
    print("=========================================")
    print("   JANE STREET QUANT BOT INITIALIZING    ")
    print("=========================================\n")
    
    # Load saved coin pair configuration
    load_config()
    
    # Run server API in background thread
    api_thread = threading.Thread(target=run_api_server, daemon=True)
    api_thread.start()
    
    acc_info = initialize_mt5()
    kf = KalmanFilterRegression(transition_covariance=1e-5, observation_covariance=1e-3)
    
    is_halted = False
    smc_update_counter = 0
    active_zones = None
    
    # dynamic checks ke liye track rakhenge kon sa coin chal raha hai filhal
    last_processed_pair = ""
    
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
                
            # Dynamic Assets local parameters block main assign hote hain variables se
            S_A = GLOBAL_CONFIG["SYMBOL_A"]
            S_B = GLOBAL_CONFIG["SYMBOL_B"]
            current_pair_context = f"{S_A}/{S_B}"
            
            # Agar dashboard se coin badla hai to runtime par subscribe karein naye symbols ko
            if current_pair_context != last_processed_pair:
                logger.info(f"Switching engine focus to market targets: Leg A={S_A} | Leg B={S_B}")
                check_and_subscribe_symbol(S_A)
                check_and_subscribe_symbol(S_B)
                kf = KalmanFilterRegression(transition_covariance=1e-5, observation_covariance=1e-3) # reset filter for stability
                active_zones = None
                last_processed_pair = current_pair_context
            
            is_halted, daily_loss_p = check_drawdown_limit(acc_info)
            if is_halted:
                close_all_positions(S_A)
                close_all_positions(S_B)
                update_dashboard_state(acc_info, daily_loss_p, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, get_trades_count_today(), True, None)
                time.sleep(10)
                continue
                
            check_closed_trades(S_A)
            check_closed_trades(S_B)
            
            if active_zones is None or smc_update_counter >= 10:
                try:
                    rates_df = get_rates_df(S_A, SMC_TIMEFRAME, count=100)
                    if rates_df is not None and not rates_df.empty:
                        active_zones = detect_smc_zones(rates_df)
                    smc_update_counter = 0
                except Exception as e:
                    logger.error(f"SMC Scan execution breakdown: {e}")
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
            if z_score < -Z_ENTRY_THRESHOLD: action = "BUY_SPREAD"
            elif z_score > Z_ENTRY_THRESHOLD: action = "SELL_SPREAD"
            
            if action != "NONE":
                log_signal(S_A, S_B, price_a, price_b, beta, alpha, z_score, net_obi, action)
            
            trades_today = get_trades_count_today()
            positions = mt5.positions_get()
            active_js_positions = [p for p in positions if p.magic == MAGIC_NUMBER] if positions else []
            
            if len(active_js_positions) == 0 and trades_today < MAX_DAILY_TRADES:
                if is_spread_valid(S_A) and is_spread_valid(S_B):
                    in_bullish_zone = True
                    in_bearish_zone = True
                    
                    if REQUIRE_SMC_CONFLUENCE and active_zones is not None:
                        in_bullish_zone = any(is_price_in_zones(price_a, active_zones.get(k, [])) for k in ['bullish_ob', 'bullish_breaker', 'bullish_fvg', 'bullish_ifvg'])
                        in_bearish_zone = any(is_price_in_zones(price_a, active_zones.get(k, [])) for k in ['bearish_ob', 'bearish_breaker', 'bearish_fvg', 'bearish_ifvg'])
                        
                    if z_score < -Z_ENTRY_THRESHOLD and net_obi > 0.15 and in_bullish_zone:
                        sl_dist = 3.0 * (tick_a.ask - tick_a.bid)
                        lots_a = calculate_lots(S_A, sl_dist, acc_info)
                        lots_b = round(lots_a * abs(beta) * (price_a / price_b), 2)
                        if execute_three_part_trade(S_A, True, tick_a.ask, tick_a.ask - sl_dist, lots_a, price_a + sl_dist, price_a + sl_dist*2, price_a + sl_dist*3.5):
                            send_order(S_B, mt5.ORDER_TYPE_SELL, tick_b.bid, lots_b, 0.0, 0.0, "JS_HEDGE")
                            invalidate_trades_cache()
                            
                    elif z_score > Z_ENTRY_THRESHOLD and net_obi < -0.15 and in_bearish_zone:
                        sl_dist = 3.0 * (tick_a.ask - tick_a.bid)
                        lots_a = calculate_lots(S_A, sl_dist, acc_info)
                        lots_b = round(lots_a * abs(beta) * (price_a / price_b), 2)
                        if execute_three_part_trade(S_A, False, tick_a.bid, tick_a.bid + sl_dist, lots_a, price_a - sl_dist, price_a - sl_dist*2, price_a - sl_dist*3.5):
                            send_order(S_B, mt5.ORDER_TYPE_BUY, tick_b.ask, lots_b, 0.0, 0.0, "JS_HEDGE")
                            invalidate_trades_cache()
            
            elif len(active_js_positions) > 0:
                leg_a_parts = [p for p in active_js_positions if p.symbol == S_A]
                comments = [p.comment for p in leg_a_parts]
                if not any("JS_TP1" in c for c in comments) and leg_a_parts:
                    modify_sl_for_trade(S_A, leg_a_parts[0].price_open)
                    
            # API State dynamically update hogi
            update_dashboard_state(acc_info, daily_loss_p, z_score, beta, alpha, spread, obi_a, obi_b, trades_today, False, active_zones)
            
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