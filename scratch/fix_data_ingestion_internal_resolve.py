import os

ingestion_path = os.path.join(os.path.dirname(__file__), "..", "data_ingestion.py")

with open(ingestion_path, "r", encoding="utf-8") as f:
    content = f.read()

# Locate get_rates_df to end of file to replace it cleanly
start_idx = content.find("def get_rates_df")
if start_idx != -1:
    old_block = content[start_idx:]
    new_block = """def get_rates_df(symbol, timeframe, count=200):
    \"\"\"Fetches historical price candles and returns them as a pandas DataFrame.\"\"\"
    resolved = resolve_broker_symbol(symbol)
    rates = mt5.copy_rates_from_pos(resolved, timeframe, 0, count)
    if rates is None:
        logger.error(f"Failed to fetch rates for {resolved} (requested: {symbol}). Error: {mt5.last_error()}")
        return None
        
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

def get_live_ticks(symbol):
    \"\"\"Fetches the latest tick (bid, ask, time) for a symbol.\"\"\"
    resolved = resolve_broker_symbol(symbol)
    tick = mt5.symbol_info_tick(resolved)
    if tick is None:
        logger.warning(f"Failed to get live tick for {resolved} (requested: {symbol})")
        return None
    return tick

def get_market_book(symbol):
    \"\"\"
    Fetches the Level-2 order book depth from MT5.
    Returns: (bids, asks) where each is a list of (price, volume) tuples.
    \"\"\"
    resolved = resolve_broker_symbol(symbol)
    book = mt5.market_book_get(resolved)
    if book is None:
        # If market depth is unavailable, return empty lists
        return [], []
        
    bids = []
    asks = []
    
    for level in book:
        price = level.price
        # volume_real is available in newer MT5 versions, fallback to volume
        volume = level.volume_real if hasattr(level, 'volume_real') else level.volume
        
        # level.type values:
        # mt5.BOOK_TYPE_BUY: Bid (Buy Order)
        # mt5.BOOK_TYPE_SELL: Ask (Sell Order)
        if level.type == mt5.BOOK_TYPE_BUY:
            bids.append((price, volume))
        elif level.type == mt5.BOOK_TYPE_SELL:
            asks.append((price, volume))
            
    # Sort bids descending (highest buy price first) and asks ascending (lowest sell price first)
    bids.sort(key=lambda x: x[0], reverse=True)
    asks.sort(key=lambda x: x[0])
    
    return bids, asks

def shutdown_mt5(symbol=None):
    \"\"\"Cleans up subscriptions and shuts down MT5 connection.\"\"\"
    if symbol:
        try:
            resolved = resolve_broker_symbol(symbol)
            mt5.market_book_release(resolved)
        except Exception:
            pass
    mt5.shutdown()
    logger.info("MT5 connection closed.")
"""
    content = content[:start_idx] + new_block
    print("get_rates_df, get_live_ticks, get_market_book, and shutdown_mt5 updated in data_ingestion.py.")
else:
    print("Target block not found!")

with open(ingestion_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
