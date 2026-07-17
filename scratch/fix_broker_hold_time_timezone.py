import os

exec_bot_path = os.path.join(os.path.dirname(__file__), "..", "execution_bot.py")

with open(exec_bot_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """    pos = positions[0]
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

replacement = """    pos = positions[0]
    # Enforce 31-second minimum hold time safeguard for Forex accounts to prevent broker block
    import time
    # Fetch tick for correct broker-side timezone time comparison
    tick = mt5.symbol_info_tick(resolved_symbol)
    broker_now = getattr(tick, "time_msc", 0) / 1000.0 if getattr(tick, "time_msc", 0) > 0 else (getattr(tick, "time", 0) if tick else 0.0)
    open_time = getattr(pos, "time_msc", 0) / 1000.0 if getattr(pos, "time_msc", 0) > 0 else getattr(pos, "time", 0)
    
    if open_time > 0 and broker_now > 0:
        elapsed = broker_now - open_time
        # Bypass if elapsed is negative (due to timezone mismatches or tick lag) to prevent long blocks
        if elapsed < 0:
            elapsed = 32.0
        if elapsed < 32.0:
            wait_time = 32.0 - elapsed
            logger.info(f"Safeguard: Position ticket {pos.ticket} was opened only {elapsed:.1f}s ago. Waiting {wait_time:.1f}s to satisfy the 31-second broker minimum hold time rule...")
            time.sleep(wait_time)

    order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY"""

if target in content:
    content = content.replace(target, replacement)
    print("Hold time timezone safeguard updated successfully.")
else:
    print("Target not found!")

with open(exec_bot_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
