import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """                        # Machine Learning Filter evaluation
                        if ML_MODEL is not None:"""

replacement = """                        # Machine Learning Filter evaluation (bypassed for extreme Z-scores >= 3.0 where reversion is highly probable)
                        if ML_MODEL is not None and abs(best_sig["z_score"]) < 3.0:"""

if target in content:
    content = content.replace(target, replacement)
    print("Replacement successful.")
else:
    print("Target not found!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
