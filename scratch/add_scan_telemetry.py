import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Initialization
target_init = """            active_pair_beta = 0.0
            active_pair_obi_a = 0.0
            active_pair_obi_b = 0.0

            for s_a, s_b in pairs_to_scan:"""

replacement_init = """            active_pair_beta = 0.0
            active_pair_obi_a = 0.0
            active_pair_obi_b = 0.0
            scanned_z_scores = []

            for s_a, s_b in pairs_to_scan:"""

if target_init in content:
    content = content.replace(target_init, replacement_init)
    print("Init replacement successful.")
else:
    print("Init target not found!")

# 2. Append inside loop
target_append = """                win_rate = WIN_RATE_CACHE.get(pk, 50.0)
                update_scanned_asset(pk, p_a, p_b, win_rate, z, action)"""

replacement_append = """                win_rate = WIN_RATE_CACHE.get(pk, 50.0)
                update_scanned_asset(pk, p_a, p_b, win_rate, z, action)
                scanned_z_scores.append((pk, z))"""

if target_append in content:
    content = content.replace(target_append, replacement_append)
    print("Append replacement successful.")
else:
    print("Append target not found!")

# 3. Print telemetry
target_print = """            # ── 3. MANAGE ACTIVE POSITION EXITS ──"""

replacement_print = """            # Print periodic Z-score scan telemetry to show that the bot is active and scanning
            if scanned_z_scores:
                top_deviations = sorted(scanned_z_scores, key=lambda x: abs(x[1]), reverse=True)[:3]
                dev_str = ", ".join([f"{pk}: Z={z:.3f}" for pk, z in top_deviations])
                logger.info(f"Scan Telemetry - Top Spreads: {dev_str}")

            # ── 3. MANAGE ACTIVE POSITION EXITS ──"""

if target_print in content:
    content = content.replace(target_print, replacement_print)
    print("Print replacement successful.")
else:
    print("Print target not found!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
