import os

config_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "trading-dashboard", "src", "pages", "config.tsx")

with open(config_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add useState imports if not already present, and ShieldAlert / Alert imports
# Let's search if useState is imported from react.
# In config.tsx, useState is probably already imported. Yes.
# Let's add Alert imports if they aren't there.
old_import = 'import { useToast } from "@/hooks/use-toast";'
new_import = """import { useToast } from "@/hooks/use-toast";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ShieldAlert } from "lucide-react";"""

content = content.replace(old_import, new_import)

# 2. Insert states and handleChangePassword handler at the top of Config() component
# Let's search for "const executeTrade = useExecuteTrade();" or "const { toast } = useToast();" to insert below it.
target_insert = "  const { toast } = useToast();"
helper_code = """  const [currentPass, setCurrentPass] = useState("");
  const [newPass, setNewPass] = useState("");
  const [confirmPass, setConfirmPass] = useState("");
  const isReadOnly = localStorage.getItem("wasee_role") === "user";

  const handleChangePassword = async () => {
    if (newPass !== confirmPass) {
      toast({
        title: "❌ Passwords Mismatch",
        description: "New password and confirmation password do not match.",
        variant: "destructive"
      });
      return;
    }

    try {
      const res = await fetch("/api/config/password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ currentPassword: currentPass, newPassword: newPass }),
      });

      if (res.ok) {
        toast({
          title: "🔑 Password Updated",
          description: "Admin master password updated successfully in the database.",
        });
        setCurrentPass("");
        setNewPass("");
        setConfirmPass("");
      } else {
        const data = await res.json();
        toast({
          title: "❌ Update Failed",
          description: data.error || "Failed to update admin password.",
          variant: "destructive"
        });
      }
    } catch (err) {
      toast({
        title: "❌ Connection Error",
        description: "Could not connect to the password update server.",
        variant: "destructive"
      });
    }
  };

"""

content = content.replace(target_insert, target_insert + "\n" + helper_code)

# 3. Add Warning Banner at the top of return statement
old_return = """  return (
    <div className="flex flex-col h-full overflow-auto bg-background p-6 space-y-6">"""

new_return = """  return (
    <div className="flex flex-col h-full overflow-auto bg-background p-6 space-y-6">
      {isReadOnly && (
        <Alert className="bg-red-500/5 text-red-400 border-red-500/20 py-2.5 rounded-sm">
          <div className="flex gap-2 items-center">
            <ShieldAlert className="h-4 w-4 shrink-0" />
            <AlertDescription className="text-xs font-mono font-bold">
              ⚠️ VIEWER MODE: Configuration changes and action triggers are disabled.
            </AlertDescription>
          </div>
        </Alert>
      )}"""

content = content.replace(old_return, new_return)

# 4. Wrap form grid inside <fieldset disabled={isReadOnly}>
old_form_grid = """        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">"""

new_form_grid = """        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
          <fieldset disabled={isReadOnly} className="grid grid-cols-1 xl:grid-cols-3 gap-6">"""

content = content.replace(old_form_grid, new_form_grid)

# 5. Insert Password Change Card and close fieldset at the bottom of the form
old_form_close = """          </Card>
        </form>"""

new_form_close = """          </Card>
          </fieldset>

          {/* PASSWORD CHANGE SECTION */}
          <Card className="bg-card border-border mt-6">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm uppercase tracking-wider text-muted-foreground">Admin Security Settings</CardTitle>
              <CardDescription className="text-xs">
                Update the master administrator credentials for the trading system.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="max-w-md space-y-4">
                <div className="space-y-1">
                  <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono block">Current Password</label>
                  <Input 
                    type="password" 
                    placeholder="••••••••" 
                    value={currentPass}
                    onChange={(e) => setCurrentPass(e.target.value)}
                    disabled={isReadOnly}
                    className="font-mono text-xs border-border bg-zinc-950/40 text-foreground"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono block">New Password</label>
                  <Input 
                    type="password" 
                    placeholder="••••••••" 
                    value={newPass}
                    onChange={(e) => setNewPass(e.target.value)}
                    disabled={isReadOnly}
                    className="font-mono text-xs border-border bg-zinc-950/40 text-foreground"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono block">Confirm New Password</label>
                  <Input 
                    type="password" 
                    placeholder="••••••••" 
                    value={confirmPass}
                    onChange={(e) => setConfirmPass(e.target.value)}
                    disabled={isReadOnly}
                    className="font-mono text-xs border-border bg-zinc-950/40 text-foreground"
                  />
                </div>
                <Button 
                  type="button" 
                  onClick={handleChangePassword}
                  disabled={isReadOnly || !currentPass || !newPass || !confirmPass}
                  className="bg-indigo-600 hover:bg-indigo-500 text-white font-mono text-xs px-4 h-9 font-bold"
                >
                  CHANGE ADMIN PASSWORD
                </Button>
                {isReadOnly && (
                  <div className="text-[10px] text-rose-500 font-mono animate-pulse">
                    🚫 Change password disabled for viewers.
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </form>"""

content = content.replace(old_form_close, new_form_close)

with open(config_path, "w", encoding="utf-8") as f:
    f.write(content)
print("config.tsx updated with admin password change options and read-only protections.")
