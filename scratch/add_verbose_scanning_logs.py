import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """                z_velocity = kf_pair.get_velocity(k=3)
                dynamic_z_entry = kf_pair.get_dynamic_z_entry(Z_ENTRY_THRESHOLD)"""

replacement = """                z_velocity = kf_pair.get_velocity(k=3)
                dynamic_z_entry = kf_pair.get_dynamic_z_entry(Z_ENTRY_THRESHOLD)
                
                # Verbose logging of Z-score and velocity for every single scanned pair as requested by the user
                logger.info(f"Scanning {pk} | Z-Score: {z:.3f} | Velocity: {z_velocity:.3f} | Dynamic Entry: {dynamic_z_entry:.3f}")"""

if target in content:
    content = content.replace(target, replacement)
    print("Verbose scanning logs added.")
else:
    print("Target not found!")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
