import json
import os

backup_path = r"G:\google antigravity\jane_street_trading_system\trading\jane_street_backup (1).json"
lattest_path = r"G:\google antigravity\jane_street_trading_system\trading\lattest .json"

print("Inspect Backup Files:")
for p in [backup_path, lattest_path]:
    if os.path.exists(p):
        print(f"\nFile: {os.path.basename(p)} (Size: {os.path.getsize(p)} bytes)")
        try:
            with open(p, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    print("Keys:", list(data.keys()))
                elif isinstance(data, list):
                    print(f"List length: {len(data)}")
                    if len(data) > 0:
                        print("First element keys:", list(data[0].keys()) if isinstance(data[0], dict) else type(data[0]))
        except Exception as e:
            print("Error loading:", e)
