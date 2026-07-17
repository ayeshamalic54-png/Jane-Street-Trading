import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update save_config logger line to show Z-Entry
old_save_config = """def save_config(pair_str):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"active_pair": pair_str}, f)
        logger.info(f"Saved config: {pair_str}")"""

new_save_config = """def save_config(pair_str):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"active_pair": pair_str}, f)
        logger.info(f"Saved config: {pair_str} | Z-Entry: {Z_ENTRY_THRESHOLD}")"""

if old_save_config in content:
    content = content.replace(old_save_config, new_save_config)
    print("save_config logger updated with Z-Entry.")
else:
    print("old_save_config block not found!")

# 2. Update overriding logger message to remove the word "crypto"
old_override = 'logger.info("Overriding database crypto active_pair config to EURUSD/GBPUSD")'
new_override = 'logger.info("Overriding database invalid active_pair config to EURUSD/GBPUSD")'

if old_override in content:
    content = content.replace(old_override, new_override)
    print("Overriding log updated.")
else:
    print("old_override log not found!")

# 3. Remove Crypto Enabled configuration change logging
old_crypto_log = """                    if CRYPTO_ENABLED != new_crypto:
                        logger.info(f"[CONFIG UPDATE] Crypto Enabled updated: {CRYPTO_ENABLED} -> {new_crypto}")
                        CRYPTO_ENABLED = new_crypto"""

new_crypto_log = """                    if CRYPTO_ENABLED != new_crypto:
                        CRYPTO_ENABLED = False"""

if old_crypto_log in content:
    content = content.replace(old_crypto_log, new_crypto_log)
    print("Crypto config update log removed.")
else:
    # Try alternate indentation
    content = content.replace(
        "                    if CRYPTO_ENABLED != new_crypto:\n                        logger.info(f\"[CONFIG UPDATE] Crypto Enabled updated: {CRYPTO_ENABLED} -> {new_crypto}\")\n                        CRYPTO_ENABLED = new_crypto",
        "                    if CRYPTO_ENABLED != new_crypto:\n                        CRYPTO_ENABLED = False"
    )
    print("Crypto config update log removed (fallback).")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("main.py updated.")
