import os

path1 = os.path.join(os.path.dirname(__file__), "..", "data_ingestion.py")
path2 = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "bot", "data_ingestion.py")

patch_code = """def initialize_mt5():
    \"\"\"Initializes MetaTrader 5 terminal and connection, performing login if credentials exist.\"\"\"
    load_env()
    terminal_path = os.getenv("MT5_TERMINAL_PATH")
    
    login = os.getenv("MT5_LOGIN")
    password = os.getenv("MT5_PASSWORD")
    server = os.getenv("MT5_SERVER")
    
    if login and password and server:
        logger.info(f"Attempting programmatic login to Server: {server} Account: {login}...")
        try:
            login_int = int(login)
            init_args = {"login": login_int, "password": password, "server": server, "timeout": 60000}
            if terminal_path:
                init_args["path"] = terminal_path
            if not mt5.initialize(**init_args):
                logger.error(f"MT5 initialization and login failed. Error code: {mt5.last_error()}")
                sys.exit(1)
            logger.info("Programmatic login successful!")
        except ValueError:
            logger.error("MT5_LOGIN in .env must be an integer account number.")
            sys.exit(1)
    else:
        init_args = {"timeout": 60000}
        if terminal_path:
            init_args["path"] = terminal_path
            logger.info(f"Initializing MT5 using path: {terminal_path} (no credentials provided)")
        else:
            logger.info("Initializing MT5 using currently running terminal instance (no path or credentials provided)")
            
        if not mt5.initialize(**init_args):
            # Fallback to default path if no path was provided and default initialization failed
            if not terminal_path:
                default_path = "C:\\\\Program Files\\\\MetaTrader 5\\\\terminal64.exe"
                logger.info(f"Currently running instance not found. Falling back to default path: {default_path}")
                if mt5.initialize(path=default_path, timeout=60000):
                    logger.info("Successfully connected to default MT5 Terminal!")
                else:
                    logger.error(f"MT5 initialization failed. Error code: {mt5.last_error()}")
                    sys.exit(1)
            else:
                logger.error(f"MT5 initialization failed. Error code: {mt5.last_error()}")
                sys.exit(1)"""

def apply_patch(file_path):
    if not os.path.exists(file_path):
        print(f"File {file_path} does not exist.")
        return
        
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Locate initialize_mt5 function and replace it
    start_idx = content.find("def initialize_mt5():")
    if start_idx == -1:
        print(f"Could not find initialize_mt5 in {file_path}")
        return
        
    # Find next function definition or end of block
    # In data_ingestion.py, the next def is resolve_broker_symbol
    end_idx = content.find("def resolve_broker_symbol", start_idx)
    if end_idx == -1:
        print(f"Could not find resolve_broker_symbol in {file_path}")
        return
        
    # Replace block
    new_content = content[:start_idx] + patch_code + "\n\n" + content[end_idx:]
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"Patched initialize_mt5 in {file_path}")

apply_patch(path1)
apply_patch(path2)
