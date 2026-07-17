import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

old_cleanup = """        if not crypto_on:
            for s_a, s_b in CANDIDATE_PAIRS["crypto"]:
                cur.execute("DELETE FROM scanned_assets WHERE symbol_pair = %s", (f"{s_a}/{s_b}",))"""

new_cleanup = """        if not crypto_on:
            cur.execute("DELETE FROM scanned_assets WHERE symbol_pair LIKE '%USDT%'")"""

if old_cleanup in content:
    content = content.replace(old_cleanup, new_cleanup)
    print("cleanup_disabled_scanned_assets updated in main.py.")
else:
    # Try alternate formatting
    content = content.replace(
        '        if not crypto_on:\n            for s_a, s_b in CANDIDATE_PAIRS["crypto"]:\n                cur.execute("DELETE FROM scanned_assets WHERE symbol_pair = %s", (f"{s_a}/{s_b}",))',
        '        if not crypto_on:\n            cur.execute("DELETE FROM scanned_assets WHERE symbol_pair LIKE \'%USDT%\'")'
    )
    print("cleanup_disabled_scanned_assets updated (fallback) in main.py.")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
