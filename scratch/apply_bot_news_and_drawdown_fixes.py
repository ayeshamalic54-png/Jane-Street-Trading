import os

bot_dir = os.path.dirname(__file__)
main_path = os.path.join(bot_dir, "..", "main.py")
safeguards_path = os.path.join(bot_dir, "..", "risk_safeguards.py")

# 1. Update risk_safeguards.py Max Daily Loss to 2.8%
with open(safeguards_path, "r", encoding="utf-8") as f:
    content_sg = f.read()

content_sg = content_sg.replace("MAX_DAILY_LOSS_PERCENT = 4.2", "MAX_DAILY_LOSS_PERCENT = 2.8")

with open(safeguards_path, "w", encoding="utf-8") as f:
    f.write(content_sg)
print("Updated risk_safeguards.py daily drawdown loss percent to 2.8%.")

# 2. Update main.py
with open(main_path, "r", encoding="utf-8") as f:
    content_main = f.read()

# Modify fetch_db_config query to select max_trades
old_query = """        SELECT active_pair, sl_pips, tp_pips, smc_enabled, auto_execute,
               crypto_enabled, metals_enabled, forex_enabled, indices_enabled,
               risk_limits_enabled, z_entry_threshold, default_lots
        FROM bot_state
        WHERE id = 1"""

new_query = """        SELECT active_pair, sl_pips, tp_pips, smc_enabled, auto_execute,
               crypto_enabled, metals_enabled, forex_enabled, indices_enabled,
               risk_limits_enabled, z_entry_threshold, default_lots, max_trades
        FROM bot_state
        WHERE id = 1"""

content_main = content_main.replace(old_query, new_query)

# Modify return statement of fetch_db_config
old_return = """                float(row[10] or 2.0),
                float(row[11] or 0.01),
            )"""

new_return = """                float(row[10] or 2.0),
                float(row[11] or 0.01),
                int(row[12] or 3),
            )"""

content_main = content_main.replace(old_return, new_return)

# Modify configuration sync unpacking
old_unpack = "new_pair, new_sl, new_tp, new_smc, new_auto_exec, new_crypto, new_metals, new_forex, new_indices, new_risk_limits, new_z_entry, new_def_lots = db_cfg"
new_unpack = "new_pair, new_sl, new_tp, new_smc, new_auto_exec, new_crypto, new_metals, new_forex, new_indices, new_risk_limits, new_z_entry, new_def_lots, new_max_trades = db_cfg"

content_main = content_main.replace(old_unpack, new_unpack)

# Insert max_trades configuration logic
old_lots_config = """                    if DEFAULT_LOTS != new_def_lots:
                        logger.info(f"[CONFIG UPDATE] Default Lots updated: {DEFAULT_LOTS} -> {new_def_lots}")
                        DEFAULT_LOTS = new_def_lots"""

new_lots_config = """                    if DEFAULT_LOTS != new_def_lots:
                        logger.info(f"[CONFIG UPDATE] Default Lots updated: {DEFAULT_LOTS} -> {new_def_lots}")
                        DEFAULT_LOTS = new_def_lots
                    import risk_safeguards
                    if risk_safeguards.MAX_DAILY_TRADES != new_max_trades:
                        logger.info(f"[CONFIG UPDATE] Max Daily Trades updated: {risk_safeguards.MAX_DAILY_TRADES} -> {new_max_trades}")
                        risk_safeguards.MAX_DAILY_TRADES = new_max_trades"""

content_main = content_main.replace(old_lots_config, new_lots_config)

# Insert News Guard check right after symbol resolution
old_resolutions = """            # Resolve broker aliases for active pair
            S_A_resolved = resolve_broker_symbol(S_A) if cat_a != "crypto" else S_A
            S_B_resolved = resolve_broker_symbol(S_B) if cat_b != "crypto" else S_B"""

new_resolutions = """            # Resolve broker aliases for active pair
            S_A_resolved = resolve_broker_symbol(S_A) if cat_a != "crypto" else S_A
            S_B_resolved = resolve_broker_symbol(S_B) if cat_b != "crypto" else S_B

            # News Guard check
            import news_guard
            is_news_halted, news_msg = news_guard.get_news_halt_status([S_A_resolved, S_B_resolved])"""

content_main = content_main.replace(old_resolutions, new_resolutions)

# Block new entries under AUTO_EXECUTE if news is halted
old_auto_exec = "if AUTO_EXECUTE and not has_positions and is_trade_limit_ok and candidate_signals:"
new_auto_exec = "if AUTO_EXECUTE and not has_positions and is_trade_limit_ok and not is_news_halted and candidate_signals:"

content_main = content_main.replace(old_auto_exec, new_auto_exec)

# Update system status on dashboard if news is active
old_status = """            # Update dashboard status
            if low_correlation_warning:
                status_str = "RUNNING (Warning: Low Correlation)"
            else:
                status_str = "RUNNING (Active)" if AUTO_EXECUTE else "RUNNING (Signals Only)\""""

new_status = """            # Update dashboard status
            if is_news_halted:
                status_str = f"HALTED ({news_msg})"
            elif low_correlation_warning:
                status_str = "RUNNING (Warning: Low Correlation)"
            else:
                status_str = "RUNNING (Active)" if AUTO_EXECUTE else "RUNNING (Signals Only)\""""

content_main = content_main.replace(old_status, new_status)

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content_main)
print("Updated main.py with news guard integration and dynamic max trades limit config.")
