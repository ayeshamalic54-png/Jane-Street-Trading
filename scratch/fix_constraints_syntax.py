import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """        # Enforce VPS-specific category constraints (Hybrid support)
        is_crypto_only = (os.getenv("OVERRIDE_CRYPTO_ENABLED") == "True") and (os.getenv("OVERRIDE_FOREX_ENABLED", "False").lower() != "true")
        if is_crypto_only:
            CRYPTO_ENABLED = startup_crypto
            METALS_ENABLED = False
            FOREX_ENABLED = False
            INDICES_ENABLED = False
        else:
            CRYPTO_ENABLED = startup_crypto
            METALS_ENABLED = startup_metals
            FOREX_ENABLED = startup_forex
            INDICES_ENABLED = startup_indices
            
            # Fetch balance and generate dynamic crypto candidate pairs!
            try:
                bal, _ = get_binance_usdt_balance()
                if bal > 0:
                    dyn_pairs = get_dynamic_crypto_candidate_pairs(bal)
                    if dyn_pairs:
                        CANDIDATE_PAIRS["crypto"] = dyn_pairs
            except Exception as e:
                logger.error(f"Error fetching balance for dynamic pairs generator: {e}")
        else:
            CRYPTO_ENABLED = False
            METALS_ENABLED = startup_metals
            FOREX_ENABLED = startup_forex
            INDICES_ENABLED = startup_indices"""

replacement = """        # Enforce VPS-specific category constraints (Hybrid support)
        is_crypto_only = (os.getenv("OVERRIDE_CRYPTO_ENABLED") == "True") and (os.getenv("OVERRIDE_FOREX_ENABLED", "False").lower() != "true")
        if is_crypto_only:
            CRYPTO_ENABLED = startup_crypto
            METALS_ENABLED = False
            FOREX_ENABLED = False
            INDICES_ENABLED = False
        else:
            CRYPTO_ENABLED = startup_crypto
            METALS_ENABLED = startup_metals
            FOREX_ENABLED = startup_forex
            INDICES_ENABLED = startup_indices
            
        if CRYPTO_ENABLED:
            # Fetch balance and generate dynamic crypto candidate pairs!
            try:
                bal, _ = get_binance_usdt_balance()
                if bal > 0:
                    dyn_pairs = get_dynamic_crypto_candidate_pairs(bal)
                    if dyn_pairs:
                        CANDIDATE_PAIRS["crypto"] = dyn_pairs
            except Exception as e:
                logger.error(f"Error fetching balance for dynamic pairs generator: {e}")"""

if target in content:
    content = content.replace(target, replacement)
    print("Startup category constraints syntax error fixed.")
else:
    print("Target not found!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
