import MetaTrader5 as mt5
import datetime
import logging
from database import log_trade_entry, log_trade_exit, get_connection

logger = logging.getLogger("SMC_Forex_Bot")
MAGIC_NUMBER = 992026           # Unique magic number for Jane Street system trades

def send_order(symbol, order_type, price, volume, sl, tp, comment):
    """Submits order to MT5. Automatically handles FOK vs IOC filling modes."""
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 10,
        "magic": MAGIC_NUMBER,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }
    
    result = mt5.order_send(request)
    if result is None:
        logger.error(f"MT5 order_send returned None. Error: {mt5.last_error()}")
        return None
        
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        # Fallback to IOC filling if FOK is not supported by broker
        logger.warning(f"FOK order rejected ({result.comment}). Retrying with IOC...")
        request["type_filling"] = mt5.ORDER_FILLING_IOC
        result = mt5.order_send(request)
        
    return result

def execute_three_part_trade(symbol, is_long, entry_price, sl_price, total_lots, tp1, tp2, tp3):
    """
    Executes a trade split into three parts (TP1, TP2, TP3) for scaling out.
    Also logs the trade entry to the PostgreSQL database.
    """
    order_type = mt5.ORDER_TYPE_BUY if is_long else mt5.ORDER_TYPE_SELL
    part_lots = round(total_lots / 3.0, 2)
    
    # Ensure lot size satisfies broker minimums
    info = mt5.symbol_info(symbol)
    min_vol = info.volume_min if info else 0.01
    if part_lots < min_vol:
        part_lots = min_vol

    logger.info(f"Executing 3-part quantitative trade | Total Lots: {total_lots} | Part Lots: {part_lots}")
    logger.info(f"Entry: {entry_price:.5f} | SL: {sl_price:.5f}")
    logger.info(f"TP1: {tp1:.5f} | TP2: {tp2:.5f} | TP3: {tp3:.5f}")

    parts = [("TP1", tp1), ("TP2", tp2), ("TP3", tp3)]
    success = False

    for part_name, tp_val in parts:
        res = send_order(symbol, order_type, entry_price, part_lots, sl_price, tp_val, f"JS_{part_name}")
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            ticket = res.order
            log_trade_entry(
                ticket=ticket,
                symbol=symbol,
                order_type="BUY" if is_long else "SELL",
                lots=part_lots,
                entry_price=entry_price,
                entry_time=datetime.datetime.now(),
                comment=f"JaneStreet {part_name}"
            )
            logger.info(f"Successfully executed {part_name} order. Ticket: {ticket}")
            success = True
        else:
            err_msg = res.comment if res else "No response"
            logger.error(f"Failed to execute {part_name} order: {err_msg}")
            
    return success

def close_all_positions(symbol, comment_filter="JS_"):
    """Closes all active positions matching the magic number and symbol."""
    positions = mt5.positions_get(symbol=symbol)
    if not positions:
        return
        
    for pos in positions:
        if pos.magic == MAGIC_NUMBER and comment_filter in pos.comment:
            order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            
            # Fetch latest price
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                continue
            price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": pos.volume,
                "type": order_type,
                "position": pos.ticket,
                "price": price,
                "deviation": 10,
                "magic": MAGIC_NUMBER,
                "comment": "JS Drawdown Emergency Exit",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            res = mt5.order_send(request)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"Emergency closed position ticket: {pos.ticket}")
                # Immediately check closed deal details to log to database
                check_closed_trades(symbol)
            else:
                err_msg = res.comment if res else "No response"
                logger.error(f"Failed to close position ticket {pos.ticket}: {err_msg}")

def modify_sl_for_trade(symbol, new_sl):
    """Modifies the Stop Loss of all active trade parts to the new_sl price."""
    positions = mt5.positions_get(symbol=symbol)
    if not positions:
        return
        
    for pos in positions:
        if pos.magic == MAGIC_NUMBER:
            # Check if SL change is significant
            if abs(pos.sl - new_sl) > 0.00001:
                request = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "position": pos.ticket,
                    "sl": new_sl,
                    "tp": pos.tp
                }
                res = mt5.order_send(request)
                if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                    logger.info(f"Modified SL to {new_sl:.5f} for position ticket: {pos.ticket}")
                else:
                    err_msg = res.comment if res else "No response"
                    logger.error(f"Failed to modify SL for position ticket {pos.ticket}: {err_msg}")

def check_closed_trades(symbol):
    """
    Checks if any open trades in the database have been closed in MT5.
    Queries the MT5 history deals to log close price and profit to the database.
    """
    conn = None
    open_tickets = []
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT ticket FROM trades WHERE status = 'OPEN' AND symbol = %s", (symbol,))
        open_tickets = [row[0] for row in cur.fetchall()]
        cur.close()
    except Exception as e:
        logger.error(f"Database error checking open tickets: {e}")
    finally:
        if conn:
            conn.close()

    if not open_tickets:
        return

    # Get active positions from MT5
    positions = mt5.positions_get(symbol=symbol)
    active_tickets = [p.ticket for p in positions] if positions else []

    for ticket in open_tickets:
        if ticket not in active_tickets:
            # Trade is closed. Let's find exit deal details in MT5 history
            logger.info(f"Detected closed trade ticket: {ticket}. Fetching details from MT5 history...")
            
            # Fetch history for past 2 days
            from_date = datetime.datetime.now() - datetime.timedelta(days=2)
            to_date = datetime.datetime.now() + datetime.timedelta(days=1)
            
            history_deals = mt5.history_deals_get(from_date, to_date)
            if history_deals:
                close_price = None
                profit = 0.0
                close_time = datetime.datetime.now()
                
                # Exit deals have entry Out (mt5.DEAL_ENTRY_OUT = 1)
                exit_deals = [d for d in history_deals if d.position_id == ticket and d.entry == mt5.DEAL_ENTRY_OUT]
                
                if exit_deals:
                    deal = exit_deals[0]
                    close_price = deal.price
                    
                    # Sum profit/commission/swaps for all deals associated with this ticket
                    all_deals_for_pos = [d for d in history_deals if d.position_id == ticket]
                    profit = sum(d.profit + d.commission + d.storage for d in all_deals_for_pos if d.entry == mt5.DEAL_ENTRY_OUT)
                    close_time = datetime.datetime.fromtimestamp(deal.time)
                    
                    log_trade_exit(ticket, close_price, profit, close_time)
                    logger.info(f"Logged closed trade ticket {ticket} | Exit: {close_price:.5f} | Profit: ${profit:.2f}")
                else:
                    # Fallback close
                    log_trade_exit(ticket, 0.0, 0.0, close_time)
            else:
                log_trade_exit(ticket, 0.0, 0.0, datetime.datetime.now())
