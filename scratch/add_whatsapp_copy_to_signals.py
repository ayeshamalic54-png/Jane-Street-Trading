import os

signals_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "trading-dashboard", "src", "pages", "signals.tsx")

with open(signals_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Insert handleCopySignal helper definition above the main return statement of Signals()
old_return = "  return ("
copy_helper_code = """  const handleCopySignal = (sig: any) => {
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
      `  📥 *Position:* ${legBDirection}`;

    navigator.clipboard.writeText(text).then(() => {
      toast({
        title: "📋 Copied to Clipboard!",
        description: "Signal text formatted for WhatsApp has been copied successfully.",
      });
    }).catch(() => {
      toast({
        title: "❌ Failed to Copy",
        description: "Could not copy signal to clipboard.",
        variant: "destructive"
      });
    });
  };

"""

content = content.replace(old_return, copy_helper_code + old_return)

# 2. Add the COPY button next to the EXECUTE button
old_button_cell = """                      <TableCell className="text-center">
                        <Button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleExecuteSignal(sig);
                          }}
                          size="sm"
                          className="bg-emerald-600 hover:bg-emerald-500 text-white font-mono text-[10px] font-bold h-7 px-2"
                          disabled={executeTrade.isPending}
                        >
                          ⚡ EXECUTE
                        </Button>
                      </TableCell>"""

new_button_cell = """                      <TableCell className="text-center">
                        <div className="flex items-center justify-center gap-1.5">
                          <Button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleExecuteSignal(sig);
                            }}
                            size="sm"
                            className="bg-emerald-600 hover:bg-emerald-500 text-white font-mono text-[10px] font-bold h-7 px-2"
                            disabled={executeTrade.isPending}
                          >
                            ⚡ EXECUTE
                          </Button>
                          <Button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleCopySignal(sig);
                            }}
                            size="sm"
                            className="bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border border-zinc-700 font-mono text-[10px] font-bold h-7 px-2"
                          >
                            📋 COPY
                          </Button>
                        </div>
                      </TableCell>"""

if old_button_cell in content:
    content = content.replace(old_button_cell, new_button_cell)
    print("signals.tsx updated with WhatsApp copy button and helper.")
else:
    print("old_button_cell target not found in signals.tsx!")

with open(signals_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
