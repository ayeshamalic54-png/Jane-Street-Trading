import os

api_zod_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "lib", "api-zod", "src", "generated", "api.ts")

with open(api_zod_path, "r", encoding="utf-8") as f:
    content = f.read()

target = '"defaultLots": zod.number().optional()'
replacement = '"defaultLots": zod.number().optional(),\n  "maxDailyTrades": zod.number().optional()'

if target in content and 'maxDailyTrades' not in content:
    # Wait, we need to make sure we replace it only inside UpdateConfigBody
    # Let's find the UpdateConfigBody start
    start_body = content.find('export const UpdateConfigBody = zod.object({')
    if start_body != -1:
        target_idx = content.find(target, start_body)
        if target_idx != -1:
            prefix = content[:target_idx]
            suffix = content[target_idx:]
            suffix = suffix.replace(target, replacement, 1)
            content = prefix + suffix
            print("maxDailyTrades added to UpdateConfigBody zod schema.")
        else:
            print("Target not found inside UpdateConfigBody!")
    else:
        print("UpdateConfigBody not found!")
else:
    print("Already exists or target not found.")

with open(api_zod_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
