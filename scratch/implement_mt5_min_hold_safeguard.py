import os

eb_path = os.path.join(os.path.dirname(__file__), "..", "execution_bot.py")

with open(eb_path, "r", encoding="utf-8") as f:
    content = f.read()

# Target 1: inside close_all_positions
target_close_all = """    for pos in positions:
        if pos.magic == MAGIC_NUMBER and comment_filter in pos.comment:
            order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY"""

replacement_close_all = """    for pos in positions:
        if pos.magic == MAGIC_NUMBER and comment_filter in pos.comment:
            # Enforce 31-second minimum hold time safeguard for Forex accounts to prevent broker block
            import time
            open_time = getattr(pos, "time_msc", 0) / 1000.0 if getattr(pos, "time_msc", 0) > 0 else getattr(pos, "time", 0)
            if open_time > 0:
                elapsed = time.time() - open_time
                if elapsed < 32.0:
                    wait_time = 32.0 - elapsed
                    logger.info(f"Safeguard: Position ticket {pos.ticket} was opened only {elapsed:.1f}s ago. Waiting {wait_time:.1f}s to satisfy the 31-second broker minimum hold time rule...")
                    time.sleep(wait_time)

            order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY"""

# Target 2: inside close_position_by_ticket
target_close_ticket = """    pos = positions[0]
    order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY"""

replacement_close_ticket = """    pos = positions[0]
    # Enforce 31-second minimum hold time safeguard for Forex accounts to prevent broker block
    import time
    open_time = getattr(pos, "time_msc", 0) / 1000.0 if getattr(pos, "time_msc", 0) > 0 else getattr(pos, "time", 0)
    if open_time > 0:
        elapsed = time.time() - open_time
        if elapsed < 32.0:
            wait_time = 32.0 - elapsed
            logger.info(f"Safeguard: Position ticket {pos.ticket} was opened only {elapsed:.1f}s ago. Waiting {wait_time:.1f}s to satisfy the 31-second broker minimum hold time rule...")
            time.sleep(wait_time)

    order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY"""

if target_close_all in content:
    content = content.replace(target_close_all, replacement_close_all)
    print("close_all_positions safeguard inserted.")
else:
    print("close_all_positions target not found!")

if target_close_ticket in content:
    content = content.replace(target_close_ticket, replacement_close_ticket)
    print("close_position_by_ticket safeguard inserted.")
else:
    print("close_position_by_ticket target not found!")

with open(eb_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
