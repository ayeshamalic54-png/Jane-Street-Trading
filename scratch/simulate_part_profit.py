import decimal

# Simulate the exact variables
close_price = 78.13500
entry_price = decimal.Decimal('78.10000')
lots = decimal.Decimal('98.30')
order_type = 'SELL'

mult = 1.0 if order_type.upper() == "BUY" else -1.0
part_profit = (close_price - float(entry_price)) * float(lots) * mult
print("Calculated part_profit:", part_profit)
