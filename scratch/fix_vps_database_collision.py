import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Fix the crashed close_position_by_ticket call in main.py line 1056
target_orphan = """                    else:
                        if FOREX_ENABLED or METALS_ENABLED or INDICES_ENABLED:
                            logger.info(f"[ORPHAN CLOSER] Closing MT5 leg {orphan_symbol} (ticket: {ticket})...")
                            close_position_by_ticket(ticket)"""

replacement_orphan = """                    else:
                        if FOREX_ENABLED or METALS_ENABLED or INDICES_ENABLED:
                            logger.info(f"[ORPHAN CLOSER] Closing MT5 leg {orphan_symbol} (ticket: {ticket})...")
                            close_position_by_ticket(orphan_symbol, ticket, float(lots))"""

if target_orphan in content:
    content = content.replace(target_orphan, replacement_orphan)
    print("Orphan closer MT5 close call fixed.")
else:
    print("Orphan closer MT5 close call target not found!")

# 2. Fix the check closed trades database collision in main.py line 1512
target_closed = """                for osym in open_symbols:
                    cat = get_symbol_category(osym)
                    if cat == "crypto":
                        check_closed_binance_trades(osym)
                    else:
                        check_closed_trades(osym)"""

replacement_closed = """                for osym in open_symbols:
                    cat = get_symbol_category(osym)
                    if cat == "crypto":
                        if CRYPTO_ENABLED:
                            check_closed_binance_trades(osym)
                    else:
                        if FOREX_ENABLED or METALS_ENABLED or INDICES_ENABLED:
                            check_closed_trades(osym)"""

if target_closed in content:
    content = content.replace(target_closed, replacement_closed)
    print("Check closed trades database collision fixed.")
else:
    print("Check closed trades target not found!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
