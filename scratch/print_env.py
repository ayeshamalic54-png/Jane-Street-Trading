import os

for k, v in os.environ.items():
    if "MT5" in k or "DB" in k or "LOGIN" in k or "PASS" in k:
        print(f"Env: {k} = {v}")
