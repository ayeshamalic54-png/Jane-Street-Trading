# Binance execution mocks - completely disabled to enforce pure Forex/Metals/Indices mode
import logging
logger = logging.getLogger("SMC_Forex_Bot")

def get_symbol_filters(symbol):
    return {"quantityPrecision": 3, "pricePrecision": 2, "stepSize": 0.001, "tickSize": 0.01}

def get_binance_usdt_balance():
    return 0.0, 0.0

def calculate_binance_quantity(symbol, sl_dist, usdt_bal, risk_pct=2.0):
    return 0.0

def execute_three_part_binance_trade(symbol, is_buy, entry_price, sl, qty, tp1, tp2, tp3, signal_id=None):
    return False

def close_all_binance_positions():
    pass

def check_closed_binance_trades(symbol):
    pass

def send_signed_request(method, endpoint, params=None):
    return None

class MockTick:
    def __init__(self):
        self.bid = 0.0
        self.ask = 0.0
        self.time = 0

def get_binance_live_tick(symbol):
    return MockTick()

def get_binance_market_book(symbol):
    return [], []

def get_binance_rates_df(symbol, timeframe_minutes=5, count=200):
    return None

def close_binance_partial(symbol, volume, is_long):
    return False
