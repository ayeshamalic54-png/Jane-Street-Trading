import os

signals_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "trading-dashboard", "src", "pages", "signals.tsx")
trades_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "trading-dashboard", "src", "pages", "trades.tsx")

# 1. Patch signals.tsx
with open(signals_path, "r", encoding="utf-8") as f:
    content_sig = f.read()

# Replace HH:mm:ss formatting in signals.tsx (three occurrences)
old_time_str = 'const timeStr = format(new Date(sig.timestamp), "HH:mm:ss");'
new_time_str = 'const timeStr = format(new Date(sig.timestamp), "EEEE, dd/MM/yyyy, hh:mm:ss a");'

if old_time_str in content_sig:
    content_sig = content_sig.replace(old_time_str, new_time_str)
    print("Formatted WhatsApp signal time string to 12-hour format.")
else:
    print("old_time_str not found in signals.tsx!")

# Replace display time in signals table
old_display_time = 'format(new Date(sig.timestamp), "HH:mm:ss.SSS")'
new_display_time = 'format(new Date(sig.timestamp), "EEEE, dd/MM/yyyy, hh:mm:ss a")'

if old_display_time in content_sig:
    content_sig = content_sig.replace(old_display_time, new_display_time)
    print("Formatted table signal display time to 12-hour format.")
else:
    print("old_display_time not found in signals.tsx!")

with open(signals_path, "w", encoding="utf-8") as f:
    f.write(content_sig)

# 2. Patch trades.tsx
with open(trades_path, "r", encoding="utf-8") as f:
    content_trades = f.read()

old_trade_entry = 'format(new Date(trade.entryTime), "MM/dd HH:mm:ss")'
new_trade_entry = 'format(new Date(trade.entryTime), "EEEE, dd/MM/yyyy, hh:mm:ss a")'

if old_trade_entry in content_trades:
    content_trades = content_trades.replace(old_trade_entry, new_trade_entry)
    print("Formatted trade entry time to 12-hour format.")
else:
    print("old_trade_entry not found in trades.tsx!")

old_trade_close = 'format(new Date(trade.closeTime), "MM/dd HH:mm:ss")'
new_trade_close = 'format(new Date(trade.closeTime), "EEEE, dd/MM/yyyy, hh:mm:ss a")'

if old_trade_close in content_trades:
    content_trades = content_trades.replace(old_trade_close, new_trade_close)
    print("Formatted trade close time to 12-hour format.")
else:
    print("old_trade_close not found in trades.tsx!")

with open(trades_path, "w", encoding="utf-8") as f:
    f.write(content_trades)

print("Formatting patch complete!")
