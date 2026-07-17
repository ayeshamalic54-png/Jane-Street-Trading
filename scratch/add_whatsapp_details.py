import os

signals_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "trading-dashboard", "src", "pages", "signals.tsx")

with open(signals_path, "r", encoding="utf-8") as f:
    content = f.read()

# Locate the handleCopySignal function block and replace it with the new comprehensive layout
old_helper = """  const handleCopySignal = (sig: any) => {
    const isBuy = sig.action === "BUY_SPREAD";
    const details = getSignalDetails(sig);
    const timeStr = format(new Date(sig.timestamp), "HH:mm:ss");
    
    const actionEmoji = isBuy ? "🟢" : "🔴";
    const legBDirection = isBuy ? "SELL" : "BUY";

    const text = `📢 *AWAIS JANE STREET SIGNAL* 📢\\n\\n` +
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

new_helper = """  const handleCopySignal = (sig: any) => {
    const isBuy = sig.action === "BUY_SPREAD";
    const details = getSignalDetails(sig);
    const timeStr = format(new Date(sig.timestamp), "HH:mm:ss");
    
    const actionEmoji = isBuy ? "🟢" : "🔴";
    const legBDirection = isBuy ? "SELL" : "BUY";

    const defaultLots = config?.defaultLots ?? 0.01;
    const partLotsA = (defaultLots / 3.0).toFixed(2);
    const totalLotsA = defaultLots.toFixed(2);
    const lotsB = (defaultLots * Number(sig.beta ?? 1.0)).toFixed(2);

    const text = `📢 *AWAIS JANE STREET QUANTUM ENGINE SIGNAL* 📢\\n\\n` +
      `${actionEmoji} *ACTION:* ${sig.action} (${sig.symbolA} / ${sig.symbolB})\\n` +
      `⏱ *Time:* ${timeStr}\\n` +
      `📊 *Z-Score:* ${sig.zScore.toFixed(3)}\\n\\n` +
      `🛡 *LEG A (${sig.symbolA}) - 3 Parts:*\\n` +
      `  📥 *Entry:* ${details.entry}\\n` +
      `  ⛔ *Stop Loss (SL):* ${details.sl}\\n` +
      `  🎯 *TP1:* ${details.tp1}\\n` +
      `  🎯 *TP2:* ${details.tp2}\\n` +
      `  🎯 *TP3:* ${details.tp3}\\n` +
      `  📦 *Lots:* 3 parts of ${partLotsA} (Total ${totalLotsA})\\n\\n` +
      `⚖ *LEG B (${sig.symbolB}) - Hedge:*\\n` +
      `  📥 *Entry:* ${details.entryB}\\n` +
      `  ⛔ *Stop Loss (SL):* ${details.slB}\\n` +
      `  🎯 *TP:* Dynamic (Spread Reversion)\\n` +
      `  📦 *Lots:* ${lotsB}\\n` +
      `  📥 *Position:* ${legBDirection}`;"""

if old_helper in content:
    content = content.replace(old_helper, new_helper)
    print("signals.tsx updated with comprehensive copy signal coordinates.")
else:
    print("old_helper target not found in signals.tsx!")

with open(signals_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
