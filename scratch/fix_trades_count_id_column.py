import os

safeguards_path = os.path.join(os.path.dirname(__file__), "..", "risk_safeguards.py")

with open(safeguards_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """        # Group by signal_id so all parts of a spread count as 1 single trade, while manual trades count individually
        cur.execute(
            "SELECT COUNT(DISTINCT COALESCE(signal_id::text, id::text)) FROM trades WHERE CAST(entry_time AS DATE) = %s",
            (today,)
        )"""

replacement = """        # Group by signal_id so all parts of a spread count as 1 single trade, while manual trades count individually (using ticket as fallback key)
        cur.execute(
            "SELECT COUNT(DISTINCT COALESCE(signal_id::text, ticket::text)) FROM trades WHERE CAST(entry_time AS DATE) = %s",
            (today,)
        )"""

if target in content:
    content = content.replace(target, replacement)
    print("trades count query column fixed from id to ticket.")
else:
    print("Target not found!")

with open(safeguards_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
