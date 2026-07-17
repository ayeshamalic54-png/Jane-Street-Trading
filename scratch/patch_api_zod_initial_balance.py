import os

api_zod_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "lib", "api-zod", "src", "generated", "api.ts")

with open(api_zod_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update UpdateConfigBody
old_body = """  "defaultLots": zod.number().optional(),
  "maxDailyTrades": zod.number().optional()
})"""

new_body = """  "defaultLots": zod.number().optional(),
  "maxDailyTrades": zod.number().optional(),
  "initialBalance": zod.number().optional()
})"""

content = content.replace(old_body, new_body)

# 2. Update UpdateConfigResponse
old_resp = """  "riskLimitsEnabled": zod.boolean(),
  "defaultLots": zod.number().optional()
})"""

new_resp = """  "riskLimitsEnabled": zod.boolean(),
  "defaultLots": zod.number().optional(),
  "initialBalance": zod.number().optional()
})"""

content = content.replace(old_resp, new_resp)

with open(api_zod_path, "w", encoding="utf-8") as f:
    f.write(content)
print("generated/api.ts updated with initialBalance in schemas.")
