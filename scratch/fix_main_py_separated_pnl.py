import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

# First target: open trades query in startup/loop pre-check (around lines 1494-1502)
target_first = """            else:
                try:
                    conn_fp = get_connection()
                    cur_fp = conn_fp.cursor()
                    cur_fp.execute("SELECT COALESCE(SUM(profit), 0.0), COUNT(*) FROM trades WHERE status = 'OPEN'")
                    row_fp = cur_fp.fetchone()
                    floating_profit = float(row_fp[0])
                    has_positions = int(row_fp[1]) > 0
                    cur_fp.close()
                    conn_fp.close()
                except Exception:
                    pass"""

replacement_first = """            else:
                try:
                    conn_fp = get_connection()
                    cur_fp = conn_fp.cursor()
                    cur_fp.execute("SELECT symbol, profit FROM trades WHERE status = 'OPEN'")
                    all_open = cur_fp.fetchall()
                    cur_fp.close()
                    conn_fp.close()
                    
                    floating_profit = 0.0
                    open_count = 0
                    for sym, prof in all_open:
                        cat = get_symbol_category(sym)
                        is_crypto = (cat == "crypto")
                        if (is_crypto and is_crypto_vps) or (not is_crypto and not is_crypto_vps):
                            floating_profit += float(prof)
                            open_count += 1
                    has_positions = (open_count > 0)
                except Exception as e_fp:
                    logger.error(f"Error calculating separated floating profit in pre-check: {e_fp}")"""

# Second target: open trades query in post-sync calculation (around lines 1606-1617)
target_second = """            # Calculate combined floating profit from database (supports both Forex and Crypto)
            try:
                conn_fp = get_connection()
                cur_fp = conn_fp.cursor()
                cur_fp.execute("SELECT COALESCE(SUM(profit), 0.0) FROM trades WHERE status = 'OPEN'")
                floating_profit = float(cur_fp.fetchone()[0])
                cur_fp.close()
                conn_fp.close()
                if floating_profit != 0.0:
                    has_positions = True
            except Exception as e:
                logger.error(f"Error calculating combined floating profit: {e}")"""

replacement_second = """            # Calculate separated floating profit from database based on bot category (Forex vs Crypto)
            try:
                conn_fp = get_connection()
                cur_fp = conn_fp.cursor()
                cur_fp.execute("SELECT symbol, profit FROM trades WHERE status = 'OPEN'")
                all_open = cur_fp.fetchall()
                cur_fp.close()
                conn_fp.close()
                
                floating_profit = 0.0
                open_count = 0
                for sym, prof in all_open:
                    cat = get_symbol_category(sym)
                    is_crypto = (cat == "crypto")
                    if (is_crypto and is_crypto_vps) or (not is_crypto and not is_crypto_vps):
                        floating_profit += float(prof)
                        open_count += 1
                if open_count > 0:
                    has_positions = True
            except Exception as e:
                logger.error(f"Error calculating separated floating profit: {e}")"""

if target_first in content:
    content = content.replace(target_first, replacement_first)
    print("Pre-check PNL replacement successful.")
else:
    print("Pre-check PNL target not found!")

if target_second in content:
    content = content.replace(target_second, replacement_second)
    print("Post-sync PNL replacement successful.")
else:
    print("Post-sync PNL target not found!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
