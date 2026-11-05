import { Switch, Route, Router as WouterRouter } from "wouter";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Layout } from "@/components/layout";
import React, { useEffect, useState, Component, ErrorInfo, ReactNode } from "react";
import Dashboard from "@/pages/dashboard";
import Trades from "@/pages/trades";
import Signals from "@/pages/signals";
import Metrics from "@/pages/metrics";
import Config from "@/pages/config";
import Markets from "@/pages/markets";
import Backtest from "@/pages/backtest";
import NotFound from "@/pages/not-found";
import Backup from "@/pages/backup";
import Login from "@/pages/login";

// ── ERROR BOUNDARY TO PREVENT BLANK SCREEN CRASHES ─────────────
interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  public state: ErrorBoundaryState = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Dashboard caught React error:", error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-zinc-950 text-white flex flex-col items-center justify-center p-6 text-center">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8 max-w-lg shadow-2xl">
            <div className="text-4xl mb-4">⚠️</div>
            <h2 className="text-lg font-black tracking-wide text-rose-400 mb-2 font-mono">
              Dashboard Render Recovery
            </h2>
            <p className="text-xs text-zinc-400 mb-4 font-mono">
              A temporary render error was intercepted. Live engine on VPS remains active and unaffected.
            </p>
            <div className="p-3 bg-zinc-950 border border-zinc-800 rounded font-mono text-[11px] text-rose-300 text-left mb-6 overflow-x-auto max-h-32">
              {this.state.error?.message || "Unknown client error"}
            </div>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null });
                window.location.reload();
              }}
              className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-mono font-bold text-xs rounded-lg shadow-lg transition-all"
            >
              🔄 Reload Dashboard
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 3000,
      refetchOnWindowFocus: false,
      retry: 2,
    },
  },
});

function Router() {
  return (
    <Layout>
      <Switch>
        <Route path="/" component={Dashboard} />
        <Route path="/trades" component={Trades} />
        <Route path="/signals" component={Signals} />
        <Route path="/metrics" component={Metrics} />
        <Route path="/markets" component={Markets} />
        <Route path="/config" component={Config} />
        <Route path="/backtest" component={Backtest} />
        <Route path="/backup" component={Backup} />
        <Route component={NotFound} />
      </Switch>
    </Layout>
  );
}

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(() => {
    const isAuth = localStorage.getItem("wasee_auth") === "true";
    if (isAuth) {
      // Immediately refresh activity timestamp on mount
      localStorage.setItem("wasee_last_activity", Date.now().toString());
    }
    return isAuth;
  });

  useEffect(() => {
    document.documentElement.classList.add("dark");
  }, []);

  useEffect(() => {
    if (!isAuthenticated) return;

    // Refresh timestamp immediately
    localStorage.setItem("wasee_last_activity", Date.now().toString());

    const updateActivity = () => {
      localStorage.setItem("wasee_last_activity", Date.now().toString());
    };

    const events = ["mousedown", "keydown", "scroll", "click", "touchstart", "mousemove"];
    events.forEach((ev) => {
      window.addEventListener(ev, updateActivity, { passive: true });
    });

    // 7-day session timeout check every 60 seconds (prevents sudden 1-hour drops on mobile)
    const interval = setInterval(() => {
      const lastActivity = localStorage.getItem("wasee_last_activity");
      if (lastActivity) {
        const elapsed = Date.now() - Number(lastActivity);
        if (elapsed > 7 * 24 * 60 * 60 * 1000) {
          localStorage.removeItem("wasee_auth");
          localStorage.removeItem("wasee_role");
          localStorage.removeItem("wasee_last_activity");
          setIsAuthenticated(false);
        }
      }
    }, 60000);

    return () => {
      events.forEach((ev) => {
        window.removeEventListener(ev, updateActivity);
      });
      clearInterval(interval);
    };
  }, [isAuthenticated]);

  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <TooltipProvider>
          {!isAuthenticated ? (
            <Login
              onLoginSuccess={() => {
                localStorage.setItem("wasee_auth", "true");
                localStorage.setItem("wasee_last_activity", Date.now().toString());
                setIsAuthenticated(true);
              }}
            />
          ) : (
            <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, "")}>
              <Router />
            </WouterRouter>
          )}
          <Toaster />
        </TooltipProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;
