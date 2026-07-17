import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """            if AUTO_EXECUTE and is_trade_limit_ok and candidate_signals:
                # Sort candidate signals by win rate descending, and absolute Z-score deviation second"""

replacement = """            # Check if this VPS instance already has an open trade in its category to prevent overlaps
            has_active_trade = False
            try:
                conn_check = get_connection()
                cur_check = conn_check.cursor()
                cur_check.execute("SELECT DISTINCT symbol FROM trades WHERE status = 'OPEN'")
                open_syms = [r[0] for r in cur_check.fetchall()]
                cur_check.close()
                conn_check.close()
                
                is_crypto_only_vps = CRYPTO_ENABLED and not (FOREX_ENABLED or METALS_ENABLED or INDICES_ENABLED)
                if is_crypto_only_vps:
                    has_active_trade = any(get_symbol_category(s) == "crypto" for s in open_syms)
                else:
                    has_active_trade = any(get_symbol_category(s) != "crypto" for s in open_syms)
            except Exception as e:
                logger.error(f"Error checking active trades count: {e}")

            if has_active_trade and candidate_signals:
                logger.info("An active trade is already open in our category. Skipping new trade entries to prevent overlapping positions.")

            if AUTO_EXECUTE and is_trade_limit_ok and candidate_signals and not has_active_trade:
                # Sort candidate signals by win rate descending, and absolute Z-score deviation second"""

if target in content:
    content = content.replace(target, replacement)
    print("Single active trade restriction implemented successfully.")
else:
    print("Target not found!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
