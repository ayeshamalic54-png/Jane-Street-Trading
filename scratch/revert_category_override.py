import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """def get_symbol_category(symbol: str) -> str:
    is_crypto_only = (os.getenv("OVERRIDE_CRYPTO_ENABLED") == "True") and (os.getenv("OVERRIDE_FOREX_ENABLED", "False").lower() != "true")
    if is_crypto_only:
        return "crypto"
    s = symbol.upper()
    if s.endswith("USDT") or any(x in s for x in ["BTC", "ETH", "SOL", "BNB", "AVAX", "XRP", "ADA", "DOGE", "MATIC", "POL", "LTC", "LINK", "DOT", "UNI", "SHIB"]):
        return "crypto"
    if any(x in s for x in ["XAU", "XAG"]):
        return "metals"
    if any(x in s for x in ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMD", "META", "AMZN", "US500", "US30", "NAS100", "GER30", "UK100"]):
        return "indices"
    return "forex\""""

replacement = """def get_symbol_category(symbol: str) -> str:
    s = symbol.upper()
    if s.endswith("USDT") or "USDT" in s or any(x in s for x in ["BTC", "ETH", "SOL", "BNB", "AVAX", "XRP", "ADA", "DOGE", "MATIC", "POL", "LTC", "LINK", "DOT", "UNI", "SHIB"]):
        return "crypto"
    if any(x in s for x in ["XAU", "XAG"]):
        return "metals"
    if any(x in s for x in ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMD", "META", "AMZN", "US500", "US30", "NAS100", "GER30", "UK100"]):
        return "indices"
    return "forex\""""

if target in content:
    content = content.replace(target, replacement)
    print("get_symbol_category reverted successfully.")
else:
    # Let's try matching with different indentation or string quotes
    # The last return statement in get_symbol_category was return "forex" (with double quotes)
    # Let's do a direct find and replace for the exact block from lines 997 to 1008
    print("Exact target string not matched, trying block match.")
    
    block_target = """def get_symbol_category(symbol: str) -> str:
    is_crypto_only = (os.getenv("OVERRIDE_CRYPTO_ENABLED") == "True") and (os.getenv("OVERRIDE_FOREX_ENABLED", "False").lower() != "true")
    if is_crypto_only:
        return "crypto"
    s = symbol.upper()
    if s.endswith("USDT") or any(x in s for x in ["BTC", "ETH", "SOL", "BNB", "AVAX", "XRP", "ADA", "DOGE", "MATIC", "POL", "LTC", "LINK", "DOT", "UNI", "SHIB"]):
        return "crypto"
    if any(x in s for x in ["XAU", "XAG"]):
        return "metals"
    if any(x in s for x in ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMD", "META", "AMZN", "US500", "US30", "NAS100", "GER30", "UK100"]):
        return "indices"
    return "forex\""""
    
    # Wait, the quote at the end of return "forex" in the target is double quote: return "forex"
    # Let's fix that in our script target.
    
    target_clean = """def get_symbol_category(symbol: str) -> str:
    is_crypto_only = (os.getenv("OVERRIDE_CRYPTO_ENABLED") == "True") and (os.getenv("OVERRIDE_FOREX_ENABLED", "False").lower() != "true")
    if is_crypto_only:
        return "crypto"
    s = symbol.upper()
    if s.endswith("USDT") or any(x in s for x in ["BTC", "ETH", "SOL", "BNB", "AVAX", "XRP", "ADA", "DOGE", "MATIC", "POL", "LTC", "LINK", "DOT", "UNI", "SHIB"]):
        return "crypto"
    if any(x in s for x in ["XAU", "XAG"]):
        return "metals"
    if any(x in s for x in ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMD", "META", "AMZN", "US500", "US30", "NAS100", "GER30", "UK100"]):
        return "indices"
    return "forex\""""
    
    # Actually, in the file view, line 1008 is: return "forex"
    # So the double quote is return "forex"
    # Let's write the exact block replacement directly using simple splits or finding the def get_symbol_category.
    
    start_idx = content.find("def get_symbol_category")
    end_idx = content.find("def close_orphan_spread_legs")
    if start_idx != -1 and end_idx != -1:
        old_block = content[start_idx:end_idx]
        new_block = """def get_symbol_category(symbol: str) -> str:
    s = symbol.upper()
    if s.endswith("USDT") or "USDT" in s or any(x in s for x in ["BTC", "ETH", "SOL", "BNB", "AVAX", "XRP", "ADA", "DOGE", "MATIC", "POL", "LTC", "LINK", "DOT", "UNI", "SHIB"]):
        return "crypto"
    if any(x in s for x in ["XAU", "XAG"]):
        return "metals"
    if any(x in s for x in ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMD", "META", "AMZN", "US500", "US30", "NAS100", "GER30", "UK100"]):
        return "indices"
    return "forex"

"""
        content = content.replace(old_block, new_block)
        print("Block replaced successfully.")
    else:
        print("Indices not found!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
