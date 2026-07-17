import os

signals_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "trading-dashboard", "src", "pages", "signals.tsx")

with open(signals_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace getSignalDetails function to include Leg B entry and SL calculations
old_details_fn = """  const getSignalDetails = (sig: any) => {
    const entry = Number(sig.priceA);
    const slPips = config?.slPips ?? 10;
    const tpPips = config?.tpPips ?? 20;
    
    const s = sig.symbolA.toUpperCase();
    const isCrypto = s.endsWith("USDT") || ["BTC", "ETH", "SOL", "BNB", "AVAX", "XRP", "ADA", "DOGE", "MATIC"].some(x => s.includes(x));
    
    const slDist = isCrypto ? slPips * (entry * 0.001) : slPips * getPipSize(sig.symbolA);
    const tpDist = isCrypto ? tpPips * (entry * 0.001) : tpPips * getPipSize(sig.symbolA);
    const pricePrecision = isCrypto ? 2 : (getPipSize(sig.symbolA) <= 0.0001 ? 5 : getPipSize(sig.symbolA) <= 0.01 ? 3 : 2);

    if (sig.action === "BUY_SPREAD") {
      return {
        entry: entry.toFixed(pricePrecision),
        sl: (entry - slDist).toFixed(pricePrecision),
        tp1: (entry + slDist).toFixed(pricePrecision),
        tp2: (entry + tpDist).toFixed(pricePrecision),
        tp3: (entry + slDist * 3.5).toFixed(pricePrecision),
      };
    } else if (sig.action === "SELL_SPREAD") {
      return {
        entry: entry.toFixed(pricePrecision),
        sl: (entry + slDist).toFixed(pricePrecision),
        tp1: (entry - slDist).toFixed(pricePrecision),
        tp2: (entry - tpDist).toFixed(pricePrecision),
        tp3: (entry - slDist * 3.5).toFixed(pricePrecision),
      };
    }
    return { entry: "—", sl: "—", tp1: "—", tp2: "—", tp3: "—" };
  };"""

new_details_fn = """  const getSignalDetails = (sig: any) => {
    const entry = Number(sig.priceA);
    const entryB = Number(sig.priceB);
    const slPips = config?.slPips ?? 10;
    const tpPips = config?.tpPips ?? 20;
    
    const s = sig.symbolA.toUpperCase();
    const isCrypto = s.endsWith("USDT") || ["BTC", "ETH", "SOL", "BNB", "AVAX", "XRP", "ADA", "DOGE", "MATIC"].some(x => s.includes(x));
    
    const slDist = isCrypto ? slPips * (entry * 0.001) : slPips * getPipSize(sig.symbolA);
    const tpDist = isCrypto ? tpPips * (entry * 0.001) : tpPips * getPipSize(sig.symbolA);
    const pricePrecision = isCrypto ? 2 : (getPipSize(sig.symbolA) <= 0.0001 ? 5 : getPipSize(sig.symbolA) <= 0.01 ? 3 : 2);

    const sB = sig.symbolB.toUpperCase();
    const isCryptoB = sB.endsWith("USDT") || ["BTC", "ETH", "SOL", "BNB", "AVAX", "XRP", "ADA", "DOGE", "MATIC"].some(x => sB.includes(x));
    const slDistB = isCryptoB ? slPips * (entryB * 0.001) : slPips * getPipSize(sig.symbolB);
    const pricePrecisionB = isCryptoB ? 2 : (getPipSize(sig.symbolB) <= 0.0001 ? 5 : getPipSize(sig.symbolB) <= 0.01 ? 3 : 2);

    const isBuy = sig.action === "BUY_SPREAD";
    const slB = isBuy ? (entryB + slDistB) : (entryB - slDistB);

    if (sig.action === "BUY_SPREAD") {
      return {
        entry: entry.toFixed(pricePrecision),
        sl: (entry - slDist).toFixed(pricePrecision),
        tp1: (entry + slDist).toFixed(pricePrecision),
        tp2: (entry + tpDist).toFixed(pricePrecision),
        tp3: (entry + slDist * 3.5).toFixed(pricePrecision),
        entryB: entryB.toFixed(pricePrecisionB),
        slB: slB.toFixed(pricePrecisionB),
      };
    } else if (sig.action === "SELL_SPREAD") {
      return {
        entry: entry.toFixed(pricePrecision),
        sl: (entry + slDist).toFixed(pricePrecision),
        tp1: (entry - slDist).toFixed(pricePrecision),
        tp2: (entry - tpDist).toFixed(pricePrecision),
        tp3: (entry - slDist * 3.5).toFixed(pricePrecision),
        entryB: entryB.toFixed(pricePrecisionB),
        slB: slB.toFixed(pricePrecisionB),
      };
    }
    return { entry: "—", sl: "—", tp1: "—", tp2: "—", tp3: "—", entryB: "—", slB: "—" };
  };"""

content = content.replace(old_details_fn, new_details_fn)

# Replace handleCopySignal format to include Leg B entry and SL coordinates
old_copy_helper = """    const text = `📢 *AWAIS JANE STREET SIGNAL* 📢\\n\\n` +
      `${actionEmoji} *ACTION:* ${sig.action} (${sig.symbolA} / ${sig.symbolB})\\n` +
      `⏱ *Time:* ${timeStr}\\n` +
      `📊 *Z-Score:* ${sig.zScore.toFixed(3)}\\n\\n` +
      `🛡 *LEG A (${sig.symbolA}) - 3 Parts:*\\n` +
      `  📥 *Entry:* ${details.entry}\\n` +
      `  ⛔ *Stop Loss (SL):* ${details.sl}\\n` +
      `  🎯 *TP1:* ${details.tp1}\\n` +
      `  🎯 *TP2:* ${details.tp2}\\n` +
      `  🎯 *TP3:* ${details.tp3}\\n\\n` +
      `⚖ *LEG B (${sig.symbolB}) - Hedge:*\\n` +
      `  📥 *Position:* ${legBDirection}`;"""

new_copy_helper = """    const text = `📢 *AWAIS JANE STREET SIGNAL* 📢\\n\\n` +
      `${actionEmoji} *ACTION:* ${sig.action} (${sig.symbolA} / ${sig.symbolB})\\n` +
      `⏱ *Time:* ${timeStr}\\n` +
      `📊 *Z-Score:* ${sig.zScore.toFixed(3)}\\n\\n` +
      `🛡 *LEG A (${sig.symbolA}) - 3 Parts:*\\n` +
      `  📥 *Entry:* ${details.entry}\\n` +
      `  ⛔ *Stop Loss (SL):* ${details.sl}\\n` +
      `  🎯 *TP1:* ${details.tp1}\\n` +
      `  🎯 *TP2:* ${details.tp2}\\n` +
      `  🎯 *TP3:* ${details.tp3}\\n\\n` +
      `⚖ *LEG B (${sig.symbolB}) - Hedge:*\\n` +
      `  📥 *Entry:* ${details.entryB}\\n` +
      `  ⛔ *Stop Loss (SL):* ${details.slB}\\n` +
      `  📥 *Position:* ${legBDirection}`;"""

content = content.replace(old_copy_helper, new_copy_helper)

with open(signals_path, "w", encoding="utf-8") as f:
    f.write(content)
print("signals.tsx updated with Leg B entry and SL coordinates.")
