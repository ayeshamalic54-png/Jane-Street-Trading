import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Lock, User, ShieldAlert } from "lucide-react";

export default function Login({ onLoginSuccess }: { onLoginSuccess: () => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (username.trim() === "wasee" && password === "AWais1133@") {
      setIsLoading(true);
      // Simulate authenticating & transition loading exactly like the user's spinner screenshot
      setTimeout(() => {
        localStorage.setItem("wasee_auth", "true");
        onLoginSuccess();
      }, 1200);
    } else {
      setError("Incorrect username or password. Please try again.");
    }
  };

  if (isLoading) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-zinc-950 z-50">
        <div className="flex flex-col items-center space-y-4">
          {/* Blue Circular Loading Spinner matching screenshot */}
          <div className="relative w-12 h-12">
            <div className="w-12 h-12 rounded-full border-4 border-zinc-800 border-t-blue-500 animate-spin" />
          </div>
          <span className="text-zinc-500 font-mono text-[10px] tracking-wider uppercase animate-pulse">
            Loading Quant Dashboard...
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 flex items-center justify-center bg-zinc-950 text-foreground px-4">
      {/* Background radial glow */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(59,130,246,0.1),rgba(255,255,255,0))]" />
      
      <Card className="w-full max-w-md bg-zinc-900/50 border-zinc-800 backdrop-blur-md relative z-10 shadow-[0_8px_30px_rgb(0,0,0,0.4)]">
        <CardHeader className="space-y-2 text-center pb-4">
          <div className="mx-auto w-12 h-12 bg-blue-500/10 border border-blue-500/20 rounded-md flex items-center justify-center mb-2">
            <Lock className="h-5 w-5 text-blue-400" />
          </div>
          <CardTitle className="text-xl font-bold font-mono tracking-tight text-zinc-100">
            JANE STREET QUANT
          </CardTitle>
          <CardDescription className="text-xs text-zinc-500 uppercase tracking-wider font-mono">
            Algorithmic Trading Dashboard
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <Alert className="bg-red-500/10 text-red-400 border-red-500/20 py-2.5 rounded-sm">
                <div className="flex gap-2 items-center">
                  <ShieldAlert className="h-4 w-4 shrink-0" />
                  <AlertDescription className="text-xs font-mono">{error}</AlertDescription>
                </div>
              </Alert>
            )}

            <div className="space-y-1">
              <label className="text-[10px] uppercase tracking-wider text-zinc-500 font-mono block">
                Username
              </label>
              <div className="relative">
                <User className="absolute left-3 top-2.5 h-4 w-4 text-zinc-500" />
                <Input
                  placeholder="Enter username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="pl-10 font-mono text-sm border-zinc-800 bg-zinc-950/50 text-zinc-200 placeholder:text-zinc-600 focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50"
                  required
                />
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-[10px] uppercase tracking-wider text-zinc-500 font-mono block">
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-2.5 h-4 w-4 text-zinc-500" />
                <Input
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="pl-10 font-mono text-sm border-zinc-800 bg-zinc-950/50 text-zinc-200 placeholder:text-zinc-600 focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50"
                  required
                />
              </div>
            </div>

            <Button
              type="submit"
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-mono text-sm font-bold mt-2 rounded-sm shadow-[0_4px_12px_rgba(59,130,246,0.2)] hover:shadow-[0_4px_16px_rgba(59,130,246,0.3)] transition-all"
            >
              LOG IN
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
