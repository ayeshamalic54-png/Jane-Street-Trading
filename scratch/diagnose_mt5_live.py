import os
import sys
import MetaTrader5 as mt5
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from main import get_kf_for_pair, resolve_broker_symbol, get_symbol_category, initialize_mt5

if not mt5.initialize():
    print("MT5 initialization failed!")
    sys.exit(1)

print("MT5 initialized successfully.")
terminal_info = mt5.terminal_info()
print("Terminal connected:", terminal_info.connected if terminal_info else "No terminal info")

pairs = [
    ("EURUSD", "GBPUSD"),
    ("EURUSD", "USDJPY"),
    ("GBPUSD", "USDJPY"),
    ("AUDUSD", "NZDUSD"),
    ("EURUSD", "USDCHF"),
    ("GBPUSD", "USDCHF"),
    ("XAUUSD", "XAGUSD")
]

print("\n=== SCANNING FOREX SPREADS LIVE ===")
for s_a, s_b in pairs:
    s_a_res = resolve_broker_symbol(s_a)
    s_b_res = resolve_broker_symbol(s_b)
    
    # Subscribe and fetch tick
    mt5.symbol_select(s_a_res, True)
    mt5.symbol_select(s_b_res, True)
    tick_a = mt5.symbol_info_tick(s_a_res)
    tick_b = mt5.symbol_info_tick(s_b_res)
    
    if not tick_a or not tick_b:
        print(f"Pair {s_a}/{s_b} (resolved: {s_a_res}/{s_b_res}) -> Tick missing! (Leg A: {tick_a is not None}, Leg B: {tick_b is not None})")
        continue
        
    p_a = (tick_a.bid + tick_a.ask) / 2.0
    p_b = (tick_b.bid + tick_b.ask) / 2.0
    
    kf = get_kf_for_pair(s_a_res, s_b_res)
    beta, alpha, spread, z = kf.update(p_b, p_a)
    print(f"Pair {s_a}/{s_b} -> PriceA: {p_a:.5f} | PriceB: {p_b:.5f} | Beta: {beta:.4f} | Spread: {spread:.5f} | Z-score: {z:.4f}")

mt5.shutdown()
