import os

search_paths = [
    "D:\\google antigravity\\jane_street_trading_system",
    "C:\\Users\\wasee\\.gemini\\antigravity"
]

for base in search_paths:
    print(f"Searching in: {base}")
    for root, dirs, files in os.walk(base):
        for f in files:
            if "news_guard" in f or "news" in f:
                print(f"Found: {os.path.join(root, f)}")
