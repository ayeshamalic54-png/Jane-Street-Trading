import os

env_path = ".env"

if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    if "DISABLE_MARGIN_GUARD" not in content:
        # Append DISABLE_MARGIN_GUARD to .env
        with open(env_path, "a", encoding="utf-8") as f:
            f.write("\nDISABLE_MARGIN_GUARD=False\n")
        print("Success: DISABLE_MARGIN_GUARD=False has been successfully added to your .env file!")
    else:
        print("DISABLE_MARGIN_GUARD is already present in your .env file.")
else:
    print("Error: .env file not found in the current directory.")
