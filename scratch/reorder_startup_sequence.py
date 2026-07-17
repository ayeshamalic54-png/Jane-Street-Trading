import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

# Target block of code to move
db_config_block = """    # Load startup database config & overrides to determine if MT5 is needed
    db_cfg = fetch_db_config()
    if db_cfg:
        _, _, _, _, _, startup_crypto, startup_metals, startup_forex, startup_indices, _, _, _, _ = db_cfg
        
        # Apply local overrides
        if os.getenv("OVERRIDE_CRYPTO_ENABLED") is not None:
            startup_crypto = os.getenv("OVERRIDE_CRYPTO_ENABLED").lower() == "true"
        if os.getenv("OVERRIDE_METALS_ENABLED") is not None:
            startup_metals = os.getenv("OVERRIDE_METALS_ENABLED").lower() == "true"
        if os.getenv("OVERRIDE_FOREX_ENABLED") is not None:
            startup_forex = os.getenv("OVERRIDE_FOREX_ENABLED").lower() == "true"
        if os.getenv("OVERRIDE_INDICES_ENABLED") is not None:
            startup_indices = os.getenv("OVERRIDE_INDICES_ENABLED").lower() == "true"
            
        # Enforce VPS-specific category constraints (Hybrid support)
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

# First, remove it from the original location
if db_config_block in content:
    content = content.replace(db_config_block, "")
    print("db_config_block removed from original location.")
else:
    print("db_config_block target not found at original location!")

# Second, insert it right before load_config() inside def main():
target_insert = """    global REQUIRE_SMC_CONFLUENCE, SL_PIPS, TP_PIPS, AUTO_EXECUTE, Z_ENTRY_THRESHOLD, DEFAULT_LOTS, RISK_LIMITS_ENABLED, ML_MODEL
    global CRYPTO_ENABLED, METALS_ENABLED, FOREX_ENABLED, INDICES_ENABLED

    load_config()"""

replacement_insert = """    global REQUIRE_SMC_CONFLUENCE, SL_PIPS, TP_PIPS, AUTO_EXECUTE, Z_ENTRY_THRESHOLD, DEFAULT_LOTS, RISK_LIMITS_ENABLED, ML_MODEL
    global CRYPTO_ENABLED, METALS_ENABLED, FOREX_ENABLED, INDICES_ENABLED

    # Load startup database config & overrides to determine if MT5 is needed
    db_cfg = fetch_db_config()
    if db_cfg:
        _, _, _, _, _, startup_crypto, startup_metals, startup_forex, startup_indices, _, _, _, _ = db_cfg
        
        # Apply local overrides
        if os.getenv("OVERRIDE_CRYPTO_ENABLED") is not None:
            startup_crypto = os.getenv("OVERRIDE_CRYPTO_ENABLED").lower() == "true"
        if os.getenv("OVERRIDE_METALS_ENABLED") is not None:
            startup_metals = os.getenv("OVERRIDE_METALS_ENABLED").lower() == "true"
        if os.getenv("OVERRIDE_FOREX_ENABLED") is not None:
            startup_forex = os.getenv("OVERRIDE_FOREX_ENABLED").lower() == "true"
        if os.getenv("OVERRIDE_INDICES_ENABLED") is not None:
            startup_indices = os.getenv("OVERRIDE_INDICES_ENABLED").lower() == "true"
            
        # Enforce VPS-specific category constraints (Hybrid support)
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
                logger.error(f"Error fetching balance for dynamic pairs generator: {e}")
    else:
        # Default fallbacks
        CRYPTO_ENABLED = True
        METALS_ENABLED = False
        FOREX_ENABLED = False
        INDICES_ENABLED = False

    load_config()"""

if target_insert in content:
    content = content.replace(target_insert, replacement_insert)
    print("db_config_block inserted before load_config().")
else:
    print("target_insert not found!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
