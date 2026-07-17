import os

safeguards_path = os.path.join(os.path.dirname(__file__), "..", "risk_safeguards.py")

with open(safeguards_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """def get_trades_count_today():
    \"\"\"Returns the number of trades taken today with caching.\"\"\"
    global _cached_trades_count, _cached_trades_count_date
    today = datetime.date.today()
    
    if _cached_trades_count is not None and _cached_trades_count_date == today:
        return _cached_trades_count
        
    conn = None
    count = 0
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM trades WHERE CAST(entry_time AS DATE) = %s AND (comment LIKE '%%TP1%%' OR comment LIKE '%%Manual%%' OR comment LIKE '%%MANUAL%%')",
            (today,)
        )
        count = cur.fetchone()[0]
        cur.close()"""

replacement = """def get_trades_count_today():
    \"\"\"Returns the number of trades taken today with caching, grouping spread parts together.\"\"\"
    global _cached_trades_count, _cached_trades_count_date
    today = datetime.date.today()
    
    if _cached_trades_count is not None and _cached_trades_count_date == today:
        return _cached_trades_count
        
    conn = None
    count = 0
    try:
        conn = get_connection()
        cur = conn.cursor()
        # Group by signal_id so all parts of a spread count as 1 single trade, while manual trades count individually
        cur.execute(
            "SELECT COUNT(DISTINCT COALESCE(signal_id::text, id::text)) FROM trades WHERE CAST(entry_time AS DATE) = %s",
            (today,)
        )
        count = cur.fetchone()[0]
        cur.close()"""

if target in content:
    content = content.replace(target, replacement)
    print("get_trades_count_today updated to group spread trades.")
else:
    print("Target not found!")

with open(safeguards_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
