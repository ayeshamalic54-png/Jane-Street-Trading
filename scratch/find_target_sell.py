import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

for idx in range(2045, 2065):
    print(f"Line {idx+1}: {repr(lines[idx])}")
