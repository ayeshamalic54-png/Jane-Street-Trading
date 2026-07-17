import requests
import json
import sys
import os

# Add the parent directory to the path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_connection

def test_save():
    print("Testing config save via API server...")
    
    # 1. Fetch current config from DB directly
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT max_trades FROM bot_state WHERE id=1")
    old_max = cur.fetchone()[0]
    print(f"Current max_trades in DB: {old_max}")
    cur.close()
    conn.close()
    
    # 2. Call local API server to save config with maxTrades = 6
    url = "http://localhost:3000/api/config"
    payload = {
        "activePair": "BTCUSDT/ETHUSDT",
        "slPips": 30.0,
        "tpPips": 20.0,
        "zEntryThreshold": 1.5,
        "smcEnabled": False,
        "autoExecute": True,
        "cryptoEnabled": True,
        "metalsEnabled": False,
        "forexEnabled": False,
        "indicesEnabled": False,
        "riskLimitsEnabled": True,
        "defaultLots": 0.401,
        "maxTrades": 6
    }
    
    try:
        r = requests.post(url, json=payload, timeout=5)
        print(f"API Server Response: {r.status_code} | {r.text}")
        if r.status_code == 200:
            print("Successfully called API server config save endpoint!")
        else:
            print("Failed to save config via API server!")
    except Exception as e:
        print(f"Error calling API server: {e}. (Make sure the API server is running on port 3000!)")
        
    # 3. Verify if DB was updated
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT max_trades FROM bot_state WHERE id=1")
    new_max = cur.fetchone()[0]
    print(f"New max_trades in DB: {new_max}")
    cur.close()
    conn.close()
    
    if new_max == 6:
        print("Success! Config save works perfectly.")
    else:
        print("Verification failed! Database was not updated.")

if __name__ == "__main__":
    test_save()
