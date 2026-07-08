import os
import time
import hmac
import hashlib
import requests
import urllib.parse
import logging
import datetime
from database import log_trade_entry, log_trade_exit, get_connection

logger = logging.getLogger("SMC_Forex_Bot")
BASE_URL = "https://fapi.binance.com"
MAGIC_NUMBER = 992026

# Cache for Binance symbol precision and filter details
exchange_info_cache = {}

def get_symbol_filters(symbol):
    """Fetches precision and step filters for a symbol from Binance Futures exchangeInfo."""
    global exchange_info_cache
    s_upper = symbol.upper()
    if s_upper in exchange_info_cache:
        return exchange_info_cache[s_upper]
    try:
        r = requests.get(f"{BASE_URL}/fapi/v1/exchangeInfo", timeout=10)
        if r.status_code == 200:
            data = r.json()
            for s in data.get("symbols", []):
                sym_name = s["symbol"]
                lot_size_filter = [f for f in s["filters"] if f["filterType"] == "LOT_SIZE"]
                price_filter = [f for f in s["filters"] if f["filterType"] == "PRICE_FILTER"]
                
                step_size = float(lot_size_filter[0]["stepSize"]) if lot_size_filter else 0.001
                tick_size = float(price_filter[0]["tickSize"]) if price_filter else 0.01
                
                exchange_info_cache[sym_name] = {
                    "quantityPrecision": int(s["quantityPrecision"]),
                    "pricePrecision": int(s["pricePrecision"]),
                    "stepSize": step_size,
                    "tickSize": tick_size
                }
            return exchange_info_cache.get(s_upper)
    except Exception as e:
        logger.error(f"Error fetching Binance exchangeInfo: {e}")
    return None

def send_signed_request(method, endpoint, params=None):
    """Sends a signed HMAC-SHA256 request to the Binance Futures API."""
    if params is None:
        params = {}
    
    api_key = os.getenv("BINANCE_API_KEY")
    secret_key = os.getenv("BINANCE_API_SECRET")
    if not api_key or not secret_key:
        logger.error("Binance API credentials not set in environment.")
        return None
        
    # Standard security protocol parameters
    params["timestamp"] = int(time.time() * 1000)
    params["recvWindow"] = 5000
    
    query_string = urllib.parse.urlencode(params)
    signature = hmac.new(
        secret_key.encode("utf-8"),
        query_string.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    
    headers = {
        "X-MBX-APIKEY": api_key
    }
    
    url = f"{BASE_URL}{endpoint}?{query_string}&signature={signature}"
    
    try:
        if method.upper() == "GET":
            r = requests.get(url, headers=headers, timeout=10)
        elif method.upper() == "POST":
            r = requests.post(url, headers=headers, timeout=10)
        elif method.upper() == "DELETE":
            r = requests.delete(url, headers=headers, timeout=10)
        else:
            return None
        return r
    except Exception as e:
        logger.error(f"Binance connection error on {endpoint}: {e}")
        return None

def get_binance_usdt_balance():
    """Fetches total and available USDT balance on Binance Futures."""
    res = send_signed_request("GET", "/fapi/v2/balance")
    if res is not None and res.status_code == 200:
        data = res.json()
        for asset in data:
            if asset.get("asset") == "USDT":
                total = float(asset.get("balance", 0.0))
                available = float(asset.get("availableBalance", 0.0))
                return total, available
    else:
        err_msg = res.text if res is not None else "No response"
        logger.error(f"Failed to fetch Binance Futures balance (status {res.status_code if res is not None else 'None'}): {err_msg}")
    return 0.0, 0.0

def calculate_binance_quantity(symbol, sl_distance_price, usdt_balance, risk_pct=1.0):
    """Calculates risk-based lot sizing for Binance Futures trading."""
    if sl_distance_price <= 0:
        return 0.0
        
    filters = get_symbol_filters(symbol)
    if not filters:
        logger.warning(f"Could not load filters for {symbol}, defaulting to standard rounding.")
        return round((usdt_balance * (risk_pct / 100.0)) / sl_distance_price, 3)
        
    risk_amount = usdt_balance * (risk_pct / 100.0)
    raw_qty = risk_amount / sl_distance_price
    
    step_size = filters["stepSize"]
    rounded_qty = round(round(raw_qty / step_size) * step_size, filters["quantityPrecision"])
    
    if rounded_qty < step_size:
        rounded_qty = step_size
        
    return rounded_qty

def execute_three_part_binance_trade(symbol, is_long, entry_price, sl_price, total_qty, tp1, tp2, tp3, signal_id=None):
    """
    Executes a 3-part trade on Binance Futures:
    1. Places a Market Order for the entry.
    2. Places a Stop Loss STOP_MARKET order.
    3. Places 3 separate Take Profit LIMIT orders to scale out.
    """
    side = "BUY" if is_long else "SELL"
    reverse_side = "SELL" if is_long else "BUY"
    
    filters = get_symbol_filters(symbol)
    price_prec = filters["pricePrecision"] if filters else 2
    qty_prec = filters["quantityPrecision"] if filters else 3
    
    # 1. Market Entry Order
    params = {
        "symbol": symbol,
        "side": side,
        "type": "MARKET",
        "quantity": round(total_qty, qty_prec)
    }
    
    logger.info(f"Sending Market Entry order to Binance Futures: {side} {total_qty} {symbol}")
    res = send_signed_request("POST", "/fapi/v1/order", params)
    
    if res is None or res.status_code != 200:
        err_msg = res.text if res is not None else "No response"
        logger.error(f"Binance Market order failed: {err_msg}")
        return False
        
    order_data = res.json()
    entry_order_id = order_data["orderId"]
    avg_price = float(order_data.get("avgPrice") or entry_price)
    
    logger.info(f"Binance Market entry filled at {avg_price:.5f}. Order ID: {entry_order_id}")
    
    # 2. Place Stop Loss Order (STOP_MARKET with closePosition=True)
    sl_params = {
        "symbol": symbol,
        "side": reverse_side,
        "type": "STOP_MARKET",
        "stopPrice": round(sl_price, price_prec),
        "closePosition": "true",
        "timeInForce": "GTC"
    }
    sl_res = send_signed_request("POST", "/fapi/v1/order", sl_params)
    if sl_res is not None and sl_res.status_code == 200:
        logger.info(f"Binance Stop Loss placed at stop price: {sl_price:.5f}")
    else:
        err_msg = sl_res.text if sl_res is not None else "No response"
        logger.error(f"Binance Stop Loss placement failed: {err_msg}")
    
    # 3. Scale out Take Profit LIMIT orders
    part_qty = round(total_qty / 3.0, qty_prec)
    if part_qty < (filters["stepSize"] if filters else 0.001):
        part_qty = filters["stepSize"] if filters else 0.001
        
    parts = [("TP1", tp1), ("TP2", tp2), ("TP3", tp3)]
    for part_name, tp_val in parts:
        tp_params = {
            "symbol": symbol,
            "side": reverse_side,
            "type": "LIMIT",
            "quantity": part_qty,
            "price": round(tp_val, price_prec),
            "timeInForce": "GTC",
            "reduceOnly": "true"
        }
        tp_res = send_signed_request("POST", "/fapi/v1/order", tp_params)
        if tp_res is not None and tp_res.status_code == 200:
            tp_order_id = tp_res.json()["orderId"]
            logger.info(f"Binance {part_name} Limit order placed at {tp_val:.5f}. ID: {tp_order_id}")
            
            # Log each part as a separate open position in database to match MT5 logs
            log_trade_entry(
                ticket=tp_order_id,
                symbol=symbol,
                order_type="BUY" if is_long else "SELL",
                lots=part_qty,
                entry_price=avg_price,
                entry_time=datetime.datetime.now(),
                comment=f"Binance {part_name}",
                signal_id=signal_id
            )
        else:
            err_msg = tp_res.text if tp_res is not None else "No response"
            logger.error(f"Binance {part_name} placement failed: {err_msg}")
            
    return True

def close_all_binance_positions(symbol):
    """Closes any active position for the symbol by checking active positions and placing market counter-orders."""
    # 1. Fetch current position risk
    res = send_signed_request("GET", "/fapi/v2/positionRisk", {"symbol": symbol})
    if res is None or res.status_code != 200:
        logger.error("Could not fetch Binance position details.")
        return
        
    positions = res.json()
    for pos in positions:
        pos_amt = float(pos.get("positionAmt", 0.0))
        if pos_amt != 0.0:
            side = "SELL" if pos_amt > 0.0 else "BUY"
            qty = abs(pos_amt)
            
            # Place market order to close position
            params = {
                "symbol": symbol,
                "side": side,
                "type": "MARKET",
                "quantity": qty,
                "reduceOnly": "true"
            }
            logger.info(f"Binance Emergency Exit: Closing position of {pos_amt} {symbol}")
            close_res = send_signed_request("POST", "/fapi/v1/order", params)
            if close_res is not None and close_res.status_code == 200:
                logger.info(f"Successfully closed position for {symbol}")
            else:
                logger.error(f"Failed to close position: {close_res.text if close_res is not None else 'No response'}")
                
    # 2. Cancel all open orders for symbol
    cancel_res = send_signed_request("DELETE", "/fapi/v1/allOpenOrders", {"symbol": symbol})
    if cancel_res is not None and cancel_res.status_code == 200:
        logger.info(f"Cancelled all open orders for {symbol}")

def check_closed_binance_trades(symbol):
    """
    Checks if active trades in database have been closed on Binance.
    If position amt is 0, we close all database trades and cancel outstanding TP/SL orders.
    If position is still open, we check if individual TP orders have been filled.
    """
    conn = None
    open_trades = []
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT ticket, entry_price, lots, order_type FROM trades WHERE status = 'OPEN' AND symbol = %s", (symbol,))
        open_trades = cur.fetchall()
        cur.close()
    except Exception as e:
        logger.error(f"Database error checking open tickets: {e}")
    finally:
        if conn:
            conn.close()
            
    if not open_trades:
        return
        
    # Check current position size from Binance
    res = send_signed_request("GET", "/fapi/v2/positionRisk", {"symbol": symbol})
    if res is not None and res.status_code == 200:
        data = res.json()
        pos_amt = 0.0
        for pos in data:
            if pos.get("symbol") == symbol:
                pos_amt = float(pos.get("positionAmt", 0.0))
                break
            
        if pos_amt == 0.0:
            logger.info(f"Binance position for {symbol} is closed. Syncing database records...")
            # Position is closed. Fetch recent user trade history to find exit price/profit
            history_res = send_signed_request("GET", "/fapi/v1/userTrades", {"symbol": symbol, "limit": 10})
            close_price = 0.0
            profit = 0.0
            close_time = datetime.datetime.now()
            
            if history_res is not None and history_res.status_code == 200:
                trades_history = history_res.json()
                if trades_history:
                    # Find exit price and sum total realized profit
                    close_price = float(trades_history[0].get("price", 0.0))
                    profit = sum(float(t.get("realizedProfit", 0.0)) for t in trades_history)
                    close_time = datetime.datetime.fromtimestamp(int(trades_history[0].get("time")) / 1000.0)
                    
            # Mark all open tickets in database as CLOSED
            for ticket, entry_price, lots, order_type in open_trades:
                part_profit = profit / len(open_trades) if profit != 0.0 else 0.0
                if part_profit == 0.0 and close_price != 0.0:
                    mult = 1.0 if order_type.upper() == "BUY" else -1.0
                    part_profit = (close_price - float(entry_price)) * float(lots) * mult
                log_trade_exit(ticket, close_price, part_profit, close_time)
                
            # Cancel all remaining limit TP orders
            send_signed_request("DELETE", "/fapi/v1/allOpenOrders", {"symbol": symbol})
            logger.info(f"Successfully closed database records and cleaned up open orders for {symbol}")
        else:
            # Position is still active. Check if any TP limit orders have filled.
            open_orders_res = send_signed_request("GET", "/fapi/v1/openOrders", {"symbol": symbol})
            if open_orders_res is not None and open_orders_res.status_code == 200:
                open_orders = open_orders_res.json()
                open_order_ids = {order["orderId"] for order in open_orders}
                
                for ticket, entry_price, lots, order_type in open_trades:
                    # The ticket is the tp_order_id. If it's no longer in open orders, check if it was FILLED.
                    if ticket not in open_order_ids:
                        order_res = send_signed_request("GET", "/fapi/v1/order", {"symbol": symbol, "orderId": ticket})
                        if order_res is not None and order_res.status_code == 200:
                            order_info = order_res.json()
                            status = order_info.get("status")
                            if status == "FILLED":
                                close_price = float(order_info.get("avgPrice") or order_info.get("price"))
                                close_time = datetime.datetime.fromtimestamp(int(order_info.get("updateTime")) / 1000.0)
                                mult = 1.0 if order_type.upper() == "BUY" else -1.0
                                part_profit = (close_price - float(entry_price)) * float(lots) * mult
                                log_trade_exit(ticket, close_price, part_profit, close_time)
                                logger.info(f"Binance TP order {ticket} filled. Logged trade exit. Close Price: {close_price}, Profit: {part_profit}")
                            elif status in ["CANCELED", "EXPIRED", "REJECTED"]:
                                close_time = datetime.datetime.fromtimestamp(int(order_info.get("updateTime")) / 1000.0)
                                log_trade_exit(ticket, entry_price, 0.0, close_time)
                                logger.info(f"Binance TP order {ticket} was {status}. Closed in DB.")

def get_binance_live_tick(symbol):
    """Fetches the latest tick (bid, ask) for a symbol from Binance Futures."""
    try:
        r = requests.get(f"{BASE_URL}/fapi/v1/ticker/bookTicker", params={"symbol": symbol.upper()}, timeout=5)
        if r.status_code == 200:
            data = r.json()
            class BinanceTick:
                def __init__(self, bid, ask):
                    self.bid = bid
                    self.ask = ask
            return BinanceTick(float(data["bidPrice"]), float(data["askPrice"]))
    except Exception as e:
        logger.error(f"Error fetching Binance tick for {symbol}: {e}")
    return None

def get_binance_market_book(symbol):
    """Fetches order book depth (bids, asks) for a symbol from Binance Futures."""
    try:
        r = requests.get(f"{BASE_URL}/fapi/v1/depth", params={"symbol": symbol.upper(), "limit": 5}, timeout=5)
        if r.status_code == 200:
            data = r.json()
            bids = [(float(b[0]), float(b[1])) for b in data.get("bids", [])]
            asks = [(float(a[0]), float(a[1])) for a in data.get("asks", [])]
            return bids, asks
    except Exception as e:
        logger.error(f"Error fetching Binance depth for {symbol}: {e}")
    return [], []

def get_binance_rates_df(symbol, timeframe_minutes=5, count=100):
    """Fetches historical price candles from Binance Futures and returns a pandas DataFrame."""
    interval_map = {
        1: "1m",
        3: "3m",
        5: "5m",
        15: "15m",
        30: "30m",
        60: "1h",
        240: "4h",
        1440: "1d"
    }
    interval = interval_map.get(timeframe_minutes, "5m")
    
    try:
        params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": count
        }
        r = requests.get(f"{BASE_URL}/fapi/v1/klines", params=params, timeout=5)
        if r.status_code == 200:
            klines = r.json()
            import pandas as pd
            data = []
            for k in klines:
                data.append({
                    "time": datetime.datetime.fromtimestamp(int(k[0]) / 1000.0),
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "tick_volume": int(float(k[5])),
                    "spread": 0,
                    "real_volume": 0
                })
            df = pd.DataFrame(data)
            return df
    except Exception as e:
        logger.error(f"Error fetching Binance klines for {symbol}: {e}")
    return None

def close_binance_partial(symbol, qty, is_long):
    """Closes a partial quantity of a Binance position."""
    side = "SELL" if is_long else "BUY"
    
    filters = get_symbol_filters(symbol)
    qty_prec = filters["quantityPrecision"] if filters else 3
    rounded_qty = round(qty, qty_prec)
    
    params = {
        "symbol": symbol,
        "side": side,
        "type": "MARKET",
        "quantity": rounded_qty,
        "reduceOnly": "true"
    }
    
    logger.info(f"Binance Partial Close: {side} {rounded_qty} {symbol}")
    res = send_signed_request("POST", "/fapi/v1/order", params)
    if res and res.status_code == 200:
        logger.info(f"Successfully placed Binance close order for {symbol}")
        return True
    else:
        err_msg = res.text if res else "No response"
        logger.error(f"Binance close order failed: {err_msg}")
        return False

