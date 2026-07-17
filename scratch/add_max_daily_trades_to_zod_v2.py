import os

api_zod_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "lib", "api-zod", "src", "generated", "api.ts")

with open(api_zod_path, "r", encoding="utf-8") as f:
    content = f.read()

target = '"defaultLots": zod.number().optional()'
replacement = '"defaultLots": zod.number().optional(),\n  "maxDailyTrades": zod.number().optional()'

start_body = content.find('export const UpdateConfigBody = zod.object({')
if start_body != -1:
    target_idx = content.find(target, start_body)
    if target_idx != -1:
        # Check if maxDailyTrades is already in the UpdateConfigBody block
        end_body = content.find('})', start_body)
        if 'maxDailyTrades' not in content[start_body:end_body]:
            prefix = content[:target_idx]
            suffix = content[target_idx:]
            suffix = suffix.replace(target, replacement, 1)
            content = prefix + suffix
            print("Successfully added maxDailyTrades to UpdateConfigBody zod schema.")
        else:
            print("maxDailyTrades already in UpdateConfigBody.")
    else:
        print("defaultLots target not found inside UpdateConfigBody!")
else:
    print("UpdateConfigBody not found!")

with open(api_zod_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
