import os

config_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "trading-dashboard", "src", "pages", "config.tsx")

with open(config_path, "r", encoding="utf-8") as f:
    content = f.read()

# Fix the incorrect closing order around line 617-619
incorrect_block = """          </Card>
        </form>
          </fieldset>"""

correct_block = """          </Card>
        </fieldset>"""

if incorrect_block in content:
    content = content.replace(incorrect_block, correct_block)
    print("Mismatched closing tags fixed in config.tsx.")
else:
    print("Target block not found in config.tsx!")

with open(config_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
