import sys
import MetaTrader5 as mt5

if not mt5.initialize():
    print("Failed to initialize MetaTrader 5")
    sys.exit(1)

from execution_bot import send_order

symbol = "EURUSD"
tick = mt5.symbol_info_tick(symbol)
if not tick:
    print(f"Failed to get live tick for {symbol}")
    mt5.shutdown()
    sys.exit(1)

price = tick.ask
sl_price = round(price - 0.0020, 5)   # 20 pips SL
tp_price = round(price + 0.0050, 5)   # 50 pips TP (1:2.5 RRR)

print(f"Firing test order via execution_bot: Symbol={symbol}, Price={price:.5f}, SL={sl_price:.5f}, TP={tp_price:.5f}")

res = send_order(symbol, mt5.ORDER_TYPE_BUY, price, 0.01, sl_price, tp_price, "TEST_ORDER_1_2.5_RRR")

if res and res.retcode == mt5.TRADE_RETCODE_DONE:
    print("================================================================================")
    print(f"SUCCESS! TEST TRADE EXECUTED ON METATRADER 5!")
    print(f"Ticket      : #{res.order}")
    print(f"Symbol      : {symbol}")
    print(f"Action      : BUY")
    print(f"Volume      : {res.volume} Lots")
    print(f"Entry Price : {res.price:.5f}")
    print(f"Stop Loss   : {sl_price:.5f}")
    print(f"Take Profit : {tp_price:.5f} (1:2.5 RRR)")
    print("================================================================================")
else:
    ret_code = res.retcode if res else "None"
    comment = res.comment if res else "None"
    print(f"Order failed with retcode {ret_code}: {comment}")

mt5.shutdown()
