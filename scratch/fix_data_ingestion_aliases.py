import os

ingest_path = os.path.join(os.path.dirname(__file__), "..", "data_ingestion.py")

with open(ingest_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """    # Check common index aliases
    aliases = {
        "NAS100": ["USTEC", "US100", "NDX", ".US100", "NAS100.cash", "USTEC.cash", "US100.cash"],
        "US500": ["SPX", "SPX500", "US500.cash", "SPX500.cash", ".US500"],
        "US30": ["DJI", "US30.cash", "DJI.cash", ".US30"],
        "GER30": ["DE30", "DAX30", "GER30.cash", "DE30.cash"],
    }"""

replacement = """    # Check common index aliases
    aliases = {
        "NAS100": [
            "USTEC", "US100", "NDX", ".US100", "NAS100.cash", "USTEC.cash", "US100.cash",
            "USTECH", "NDX100", ".NDX100", "USTECH100", "NAS100.pro", "NDX100.pro", 
            "USTECH.pro", "US100.pro", "NAS100.raw", "NDX100.raw", "USTECH.raw", "US100.raw",
            "NAS100.fundednext", "NDX100.fundednext", "USTEC.fundednext"
        ],
        "US500": ["SPX", "SPX500", "US500.cash", "SPX500.cash", ".US500", "US500.pro", "US500.raw", "SPX500.pro"],
        "US30": ["DJI", "US30.cash", "DJI.cash", ".US30", "US30.pro", "US30.raw"],
        "GER30": ["DE30", "DAX30", "GER30.cash", "DE30.cash", "GER30.pro", "GER30.raw", "DE30.pro"],
    }"""

if target in content:
    content = content.replace(target, replacement)
    print("Replacement successful.")
else:
    print("Target not found!")

with open(ingest_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
