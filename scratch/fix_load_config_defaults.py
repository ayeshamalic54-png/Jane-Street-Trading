import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """def load_config():
    global GLOBAL_CONFIG
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                active_pair = data.get("active_pair", "EURUSD/GBPUSD")
                parts = active_pair.split('/')
                if len(parts) == 2 and parts[0].strip() != parts[1].strip():
                    GLOBAL_CONFIG["SYMBOL_A"] = parts[0].strip()
                    GLOBAL_CONFIG["SYMBOL_B"] = parts[1].strip()
                    logger.info(f"Loaded config: Leg A={GLOBAL_CONFIG['SYMBOL_A']} | Leg B={GLOBAL_CONFIG['SYMBOL_B']}")
                else:
                    logger.warning(f"shared_config.json has identical or invalid symbols — defaulting to EURUSD/GBPUSD")
                    GLOBAL_CONFIG["SYMBOL_A"] = "EURUSD"
                    GLOBAL_CONFIG["SYMBOL_B"] = "GBPUSD"
                    save_config("EURUSD/GBPUSD")"""

replacement = """def load_config():
    global GLOBAL_CONFIG
    is_crypto_only = (os.getenv("OVERRIDE_CRYPTO_ENABLED") == "True") and (os.getenv("OVERRIDE_FOREX_ENABLED", "False").lower() != "true")
    default_pair = "BTCUSDT/ETHUSDT" if is_crypto_only else "EURUSD/GBPUSD"
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                active_pair = data.get("active_pair", default_pair)
                parts = active_pair.split('/')
                
                if is_crypto_only:
                    s_a = parts[0].upper() if len(parts) > 0 else ""
                    is_crypto = s_a.endswith("USDT") or "USDT" in s_a or any(x in s_a for x in ["BTC", "ETH", "SOL", "BNB", "AVAX", "XRP", "ADA", "DOGE", "MATIC", "POL", "LTC", "LINK", "DOT", "UNI", "SHIB"])
                    if not is_crypto:
                        logger.warning(f"Loaded config contains non-crypto pair {active_pair} on Crypto-only VPS. Defaulting to {default_pair}.")
                        active_pair = default_pair
                        parts = active_pair.split('/')
                        
                if len(parts) == 2 and parts[0].strip() != parts[1].strip():
                    GLOBAL_CONFIG["SYMBOL_A"] = parts[0].strip()
                    GLOBAL_CONFIG["SYMBOL_B"] = parts[1].strip()
                    logger.info(f"Loaded config: Leg A={GLOBAL_CONFIG['SYMBOL_A']} | Leg B={GLOBAL_CONFIG['SYMBOL_B']}")
                else:
                    logger.warning(f"shared_config.json has identical or invalid symbols — defaulting to {default_pair}")
                    p_a, p_b = default_pair.split('/')
                    GLOBAL_CONFIG["SYMBOL_A"] = p_a
                    GLOBAL_CONFIG["SYMBOL_B"] = p_b
                    save_config(default_pair)"""

if target in content:
    content = content.replace(target, replacement)
    print("load_config defaults updated successfully.")
else:
    print("Target not found!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
