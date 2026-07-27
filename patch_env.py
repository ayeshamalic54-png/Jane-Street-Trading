import os

def main():
    env_path = ".env"
    
    # We comment out MT5 credentials so the bot automatically connects to the currently running MT5 terminal instance.
    # This allows you to trade on any account (like your MetaQuotes-Demo 5053167592) by just keeping it open in the MT5 GUI.
    
    mt5_login = "34220059"
    mt5_password = "gftUE95##"
    mt5_server = "FundedNext-Server 3"
    discord_channel_id = "1531095378454118530"

    # Read existing MT5 credentials if .env exists
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("=", 1)
                if len(parts) == 2:
                    k = parts[0].strip()
                    v = parts[1].strip()
                    if v.startswith('"') or v.startswith("'"):
                        v = v[1:-1]
                    if k == "MT5_LOGIN":
                        mt5_login = v
                    elif k == "MT5_PASSWORD":
                        mt5_password = v
                    elif k == "MT5_SERVER":
                        mt5_server = v
                    elif k == "DISCORD_CHANNEL_ID":
                        discord_channel_id = v

    new_env_content = f"""# ==============================================================================
# MetaTrader 5 (MT5) Login Credentials
# ==============================================================================
# (Commented out to automatically connect to your currently active terminal account, e.g. Demo 5053167592)
# To force login to a specific account, uncomment these lines and update details:
# MT5_LOGIN={mt5_login}
# MT5_PASSWORD={mt5_password}
# MT5_SERVER={mt5_server}

# ==============================================================================
# Quantitative Database Configuration (Neon PostgreSQL)
# ==============================================================================
DATABASE_URL=postgresql://neondb_owner:npg_fh3GJr2iTRCW@ep-bitter-mode-aoi5d1e5-pooler.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require

# ==============================================================================
# Dashboard & API Settings
# ==============================================================================
DASHBOARD_API_URL=https://jane-street-arbitrage.onrender.com/api

# ==============================================================================
# Binance API Credentials
# ==============================================================================
BINANCE_API_KEY=X1bxykrXM19JK3k7d0PtzXKQFSlnqeveXqvav7gd27h8S6ElHHe5Z59FretFQzoF
BINANCE_API_SECRET=3DfRAyJBCkXXBsrby1OuDrhzim2jfOmxA2jjwpK7cVqHN7kt3cnH42mt3XbVgdp6

# Local overrides to run only Binance Crypto scanning on this America VPS
OVERRIDE_CRYPTO_ENABLED=False
OVERRIDE_FOREX_ENABLED=True
OVERRIDE_METALS_ENABLED=True
OVERRIDE_INDICES_ENABLED=True

# ==============================================================================
# Discord Webhook Notification Settings
# ==============================================================================
DISCORD_CHANNEL_ID={discord_channel_id}
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/1531099383565783070/USKQReqpW61BIaCRPgYwaOQ65isEXn4X214XEUH2vL_PFqrPThOahTwSpV5cKUgvPHCG
"""

    with open(env_path, "w", encoding="utf-8") as f:
        f.write(new_env_content)
        
    print("=====================================================================")
    print(" SUCCESS: .env file has been automatically patched on VPS!")
    print(" MT5 credentials commented out so it connects to active MT5 GUI.")
    print("=====================================================================")

if __name__ == "__main__":
    main()
