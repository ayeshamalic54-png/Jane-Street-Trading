import pandas as pd
import numpy as np
from smc_indicators import detect_smc_zones, is_price_in_zones

def run_tests():
    print("=========================================")
    print("        SMC INDICATOR UNIT TEST          ")
    print("=========================================\n")
    
    # Create mock candle data
    # We want to simulate a Bullish FVG:
    # Candle 0: Open=1.00, High=1.05, Low=0.99, Close=1.04
    # Candle 1: Open=1.04, High=1.12, Low=1.03, Close=1.10
    # Candle 2: Open=1.10, High=1.20, Low=1.08, Close=1.18
    # Here, Candle 0 High (1.05) is less than Candle 2 Low (1.08). Gap: [1.05, 1.08]
    
    # We also want to simulate a Bullish OB:
    # Candle 3: Open=1.18, High=1.19, Low=1.10, Close=1.12 (Down candle, red)
    # Candle 4: Open=1.12, High=1.25, Low=1.11, Close=1.24 (Strong up candle, breaks Candle 3 High)
    
    data = {
        'open':  [1.00, 1.04, 1.10, 1.18, 1.12, 1.24],
        'high':  [1.05, 1.12, 1.20, 1.19, 1.25, 1.28],
        'low':   [0.99, 1.03, 1.08, 1.10, 1.11, 1.22],
        'close': [1.04, 1.10, 1.18, 1.12, 1.24, 1.26]
    }
    
    df = pd.DataFrame(data)
    print("Mock Data:")
    print(df)
    print("\nDetecting SMC Zones...")
    
    zones = detect_smc_zones(df)
    
    print("\n--- RESULTS ---")
    for zone_type, val in zones.items():
        print(f"{zone_type.upper()}: {val}")
        
    # Assertions
    # Bullish FVG should be detected at [1.05, 1.08]
    assert len(zones['bullish_fvg']) > 0, "Bullish FVG not detected"
    print("\n[OK] Bullish FVG successfully detected!")
    
    # Bullish OB should be detected at [1.10, 1.19] (low and high of down candle 3)
    assert len(zones['bullish_ob']) > 0, "Bullish OB not detected"
    print("[OK] Bullish OB successfully detected!")
    
    # Test helper
    test_price_in = 1.06
    test_price_out = 1.09
    
    in_zone = is_price_in_zones(test_price_in, zones['bullish_fvg'])
    out_zone = is_price_in_zones(test_price_out, zones['bullish_fvg'])
    
    print(f"\nPrice {test_price_in} in Bullish FVG: {in_zone} (Expected: True)")
    print(f"Price {test_price_out} in Bullish FVG: {out_zone} (Expected: False)")
    
    assert in_zone == True, "Failed helper inside check"
    assert out_zone == False, "Failed helper outside check"
    print("[OK] Helper is_price_in_zones works perfectly!")
    
    print("\nALL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
