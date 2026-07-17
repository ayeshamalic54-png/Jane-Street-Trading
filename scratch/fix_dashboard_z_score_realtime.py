import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

# Target: instant dashboard update before scan loop
target_hb = """            # ── 1.5. INSTANT DASHBOARD STATE UPDATE (PNL & EQUITY) ──
            try:
                status_str = f"RUNNING ({news_msg})" if is_news_halted else ("RUNNING (Warning: Low Correlation)" if low_correlation_warning else ("RUNNING (Active)" if AUTO_EXECUTE else "RUNNING (Signals Only)"))
                update_bot_state(
                    active_pair=current_pair_context,
                    system_status=status_str,
                    equity=current_equity,
                    drawdown_percent=daily_loss_p,
                    floating_profit=floating_profit,
                    z_score=0.0,
                    hedge_ratio=0.0,
                    obi_a=0.0,
                    obi_b=0.0,
                    trades_today=get_trades_count_today(),
                    sl_pips=SL_PIPS,
                )
            except Exception as update_err:
                logger.error(f"Error executing instant dashboard update: {update_err}")"""

replacement_hb = """            # ── 1.5. INSTANT DASHBOARD STATE UPDATE (PNL & EQUITY) ──
            try:
                status_str = f"RUNNING ({news_msg})" if is_news_halted else ("RUNNING (Warning: Low Correlation)" if low_correlation_warning else ("RUNNING (Active)" if AUTO_EXECUTE else "RUNNING (Signals Only)"))
                
                # Fetch active pair's current live Z-score to keep dashboard z_score updated before scan loop
                hb_z = 0.0
                hb_beta = 0.0
                hb_obi_a = 0.0
                hb_obi_b = 0.0
                parts_hb = current_pair_context.split('/')
                if len(parts_hb) == 2:
                    s_a_hb = resolve_broker_symbol(parts_hb[0]) if get_symbol_category(parts_hb[0]) != "crypto" else parts_hb[0]
                    s_b_hb = resolve_broker_symbol(parts_hb[1]) if get_symbol_category(parts_hb[1]) != "crypto" else parts_hb[1]
                    tick_a_hb = get_binance_live_tick(s_a_hb) if get_symbol_category(s_a_hb) == "crypto" else (mt5.symbol_info_tick(s_a_hb) if not is_crypto_vps else None)
                    tick_b_hb = get_binance_live_tick(s_b_hb) if get_symbol_category(s_b_hb) == "crypto" else (mt5.symbol_info_tick(s_b_hb) if not is_crypto_vps else None)
                    if tick_a_hb and tick_b_hb:
                        p_a_hb = (tick_a_hb.bid + tick_a_hb.ask) / 2.0
                        p_b_hb = (tick_b_hb.bid + tick_b_hb.ask) / 2.0
                        kf_hb = get_kf_for_pair(s_a_hb, s_b_hb)
                        hb_beta, _, _, hb_z = kf_hb.update(p_b_hb, p_a_hb)
                        
                        bids_a_hb, asks_a_hb = get_binance_market_book(s_a_hb) if get_symbol_category(s_a_hb) == "crypto" else (get_market_book(s_a_hb) if not is_crypto_vps else ([], []))
                        bids_b_hb, asks_b_hb = get_binance_market_book(s_b_hb) if get_symbol_category(s_b_hb) == "crypto" else (get_market_book(s_b_hb) if not is_crypto_vps else ([], []))
                        hb_obi_a = calculate_obi(bids_a_hb, asks_a_hb, depth=5)
                        hb_obi_b = calculate_obi(bids_b_hb, asks_b_hb, depth=5)
                
                update_bot_state(
                    active_pair=current_pair_context,
                    system_status=status_str,
                    equity=current_equity,
                    drawdown_percent=daily_loss_p,
                    floating_profit=floating_profit,
                    z_score=hb_z,
                    hedge_ratio=hb_beta,
                    obi_a=hb_obi_a,
                    obi_b=hb_obi_b,
                    trades_today=get_trades_count_today(),
                    sl_pips=SL_PIPS,
                )
            except Exception as update_err:
                logger.error(f"Error executing instant dashboard update: {update_err}")"""

if target_hb in content:
    content = content.replace(target_hb, replacement_hb)
    print("Dashboard replacement successful.")
else:
    print("Dashboard target not found!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
