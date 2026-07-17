import os
import sys
import datetime
import MetaTrader5 as mt5

if not mt5.initialize():
    print(f"MT5 initialize failed: {mt5.last_error()}")
    sys.exit(1)

# Fetch history from 7 days ago
from_date = datetime.datetime.now() - datetime.timedelta(days=7)
to_date = datetime.datetime.now() + datetime.timedelta(days=1) # add 1 day buffer for timezone differences

deals = mt5.history_deals_get(from_date, to_date)
print("=== MT5 DEALS (LAST 7 DAYS) ===")
if deals:
    # Sort deals by time descending
    sorted_deals = sorted(deals, key=lambda x: x.time, reverse=True)
    for d in sorted_deals[:30]: # print top 30 recent deals
        symbol = d.symbol
        entry = "IN" if d.entry == 0 else "OUT"
        profit = d.profit
        price = d.price
        volume = d.volume
        time_str = datetime.datetime.fromtimestamp(d.time).strftime('%Y-%m-%d %H:%M:%S')
        comment = d.comment
        print(f"Time: {time_str} | Symbol: {symbol} | Type: {entry} | Vol: {volume} | Price: {price} | Profit: {profit} | Comment: {comment}")
else:
    print("No deals found in the last 7 days.")

mt5.shutdown()
