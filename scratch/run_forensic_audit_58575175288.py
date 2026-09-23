import sys
import os
import datetime
import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.append(r"G:\google antigravity\jane_street_trading_system")
from database import get_connection

print("=========================================================================")
print("🔍 PURE SMC — 7-CONDITION INDEPENDENT FORENSIC VERIFICATION AUDIT")
print("=========================================================================")
print("Audit Ticket: #58575175288 | Symbol: XAUUSD | Action: BUY 0.07 Lots")
print("Entry Price:  4340.11000   | SL Price: 4328.50000 | Loss: -$81.27 USD")
print("Entry Time:   22 September 2026, 20:10:05 PKT (15:10:05 UTC)")
print("=========================================================================\n")

# Fetch ticket details from Postgres DB
conn = get_connection()
cur = conn.cursor(cursor_factory=RealDictCursor)

cur.execute("SELECT * FROM trades WHERE ticket = 58575175288 OR comment LIKE '%58575175288%' OR entry_price = 4340.11;")
t_rows = cur.fetchall()

if not t_rows:
    cur.execute("SELECT * FROM trades WHERE entry_time >= '2026-09-22 14:50:00' ORDER BY entry_time DESC LIMIT 5;")
    t_rows = cur.fetchall()

print(f"Postgres DB Records Found ({len(t_rows)}):")
for r in t_rows:
    print(dict(r))

cur.close()
conn.close()
