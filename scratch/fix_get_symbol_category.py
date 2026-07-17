import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """def get_symbol_category(symbol: str) -> str:
    s = symbol.upper()
    if s.endswith("USDT") or any(x in s for x in ["BTC", "ETH", "SOL", "BNB", "AVAX", "XRP", "ADA", "DOGE", "MATIC", "LTC", "LINK", "DOT", "UNI", "SHIB"]):
        return "crypto"
    if any(x in s for x in ["XAU", "XAG"]):
        return "metals"
    if any(x in s for x in ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMD", "META", "AMZN", "US500", "US30", "NAS100", "GER30", "UK100"]):
        return "indices"
    return "forex\""""

replacement = """def get_symbol_category(symbol: str) -> str:
    s = symbol.upper()
    # Crypto disabled completely in this Forex/Metals/Indices instance
    if any(x in s for x in ["XAU", "XAG"]):
        return "metals"
    if any(x in s for x in ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMD", "META", "AMZN", "US500", "US30", "NAS100", "GER30", "UK100"]):
        return "indices"
    return "forex\""""

if target in content:
    content = content.replace(target, replacement)
    print("get_symbol_category replaced successfully.")
else:
    # Let's do a substring replace
    start = content.find("def get_symbol_category")
    if start != -1:
        end = content.find("return \"forex\"", start)
        if end != -1:
            end += len("return \"forex\"")
            content = content[:start] + replacement + content[end:]
            print("get_symbol_category replaced via manual substring search.")
        else:
            print("Could not find end of get_symbol_category!")
    else:
        print("Could not find start of get_symbol_category!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
