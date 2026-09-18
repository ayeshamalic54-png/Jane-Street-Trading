import MetaTrader5 as mt5
import pandas as pd
import datetime

if not mt5.initialize():
    print("MT5 Initialization Failed!")
    exit()

positions = mt5.positions_get()
if not positions:
    print("NO_ACTIVE_POSITIONS_ON_MT5")
else:
    df_pos = pd.DataFrame(list(positions), columns=positions[0]._asdict().keys())
    print("================================================================================")
    print("CURRENT LIVE ACTIVE POSITIONS ON MT5:")
    print("================================================================================")
    for p in positions:
        pos_type = "BUY 🟢" if p.type == mt5.ORDER_TYPE_BUY else "SELL 🔴"
        open_time = datetime.datetime.fromtimestamp(p.time).strftime("%Y-%m-%d %H:%M:%S")
        print(f"Ticket: {p.ticket} | Symbol: {p.symbol} | Type: {pos_type} | Volume: {p.volume}")
        print(f"Entry Price: {p.price_open} | Current Price: {p.price_current} | Profit: {p.profit} USD")
        print(f"Stop Loss (SL): {p.sl} | Take Profit (TP): {p.tp}")

print("\n================================================================================")
print("RECENT CLOSED/EXECUTED ORDERS TODAY:")
history_orders = mt5.history_deals_get(datetime.datetime.now() - datetime.timedelta(days=1), datetime.datetime.now())
if history_orders:
    for d in history_orders[-5:]:
        d_type = "BUY" if d.type == mt5.DEAL_TYPE_BUY else "SELL"
        d_time = datetime.datetime.fromtimestamp(d.time).strftime("%H:%M:%S")
        print(f"Time: {d_time} | Ticket: {d.ticket} | Symbol: {d.symbol} | Type: {d_type} | Volume: {d.volume} | Price: {d.price} | Profit: {d.profit}")
mt5.shutdown()
