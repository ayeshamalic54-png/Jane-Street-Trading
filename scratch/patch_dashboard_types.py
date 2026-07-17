import os

schemas_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "lib", "api-client-react", "src", "generated", "api.schemas.ts")
zod_types_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "lib", "api-zod", "src", "generated", "types", "dashboardData.ts")
ws_hooks_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "trading-dashboard", "src", "hooks", "use-ws.ts")

# 1. Update api.schemas.ts
with open(schemas_path, "r", encoding="utf-8") as f:
    schemas_content = f.read()

old_schemas_block = """  metalsEnabled?: boolean;
  forexEnabled?: boolean;
  indicesEnabled?: boolean;
}"""

new_schemas_block = """  metalsEnabled?: boolean;
  forexEnabled?: boolean;
  indicesEnabled?: boolean;
  initialBalance?: number;
  overallDrawdown?: number;
  maxEquityPeak?: number;
  mt5Login?: number;
}"""

if old_schemas_block in schemas_content:
    schemas_content = schemas_content.replace(old_schemas_block, new_schemas_block)
    print("api.schemas.ts updated.")
else:
    print("old_schemas_block not found in api.schemas.ts!")

with open(schemas_path, "w", encoding="utf-8") as f:
    f.write(schemas_content)


# 2. Update dashboardData.ts
with open(zod_types_path, "r", encoding="utf-8") as f:
    zod_content = f.read()

old_zod_block = """  metalsEnabled?: boolean;
  forexEnabled?: boolean;
  indicesEnabled?: boolean;
}"""

new_zod_block = """  metalsEnabled?: boolean;
  forexEnabled?: boolean;
  indicesEnabled?: boolean;
  initialBalance?: number;
  overallDrawdown?: number;
  maxEquityPeak?: number;
  mt5Login?: number;
}"""

if old_zod_block in zod_content:
    zod_content = zod_content.replace(old_zod_block, new_zod_block)
    print("dashboardData.ts updated.")
else:
    print("old_zod_block not found in dashboardData.ts!")

with open(zod_types_path, "w", encoding="utf-8") as f:
    f.write(zod_content)


# 3. Update use-ws.ts
with open(ws_hooks_path, "r", encoding="utf-8") as f:
    ws_content = f.read()

old_ws_block = """  metalsEnabled?: boolean;
  forexEnabled?: boolean;
  indicesEnabled?: boolean;
}"""

new_ws_block = """  metalsEnabled?: boolean;
  forexEnabled?: boolean;
  indicesEnabled?: boolean;
  initialBalance?: number;
  overallDrawdown?: number;
  maxEquityPeak?: number;
  mt5Login?: number;
}"""

if old_ws_block in ws_content:
    ws_content = ws_content.replace(old_ws_block, new_ws_block)
    print("use-ws.ts updated.")
else:
    print("old_ws_block not found in use-ws.ts!")

with open(ws_hooks_path, "w", encoding="utf-8") as f:
    f.write(ws_content)

print("TypeScript type files updated successfully.")
