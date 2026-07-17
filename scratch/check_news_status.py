import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import news_guard

# Check news halt status
is_halted, msg = news_guard.get_news_halt_status(["EURUSD", "GBPUSD"])
print("=== NEWS GUARD DIAGNOSTIC ===")
print("Is Halted:", is_halted)
print("Message:", msg)
