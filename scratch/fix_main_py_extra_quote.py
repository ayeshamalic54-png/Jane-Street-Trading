import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

target = 'logger.error(f"Error recovering active symbols: {rec_err}")"'
replacement = 'logger.error(f"Error recovering active symbols: {rec_err}")'

if target in content:
    content = content.replace(target, replacement)
    print("Extra quote removed successfully.")
else:
    print("Target not found!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
