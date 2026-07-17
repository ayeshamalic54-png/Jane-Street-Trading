import { Switch, Route, Router as WouterRouter } from "wouter";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Layout } from "@/components/layout";
import { useEffect, useState } from "react";
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

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 3000, // Serve cached data for 3 seconds to prevent navigation lag
      refetchOnWindowFocus: false, // Don't refetch on window focus
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
  const [isAuthenticated, setIsAuthenticated] = useState(() => localStorage.getItem("wasee_auth") === "true");

  useEffect(() => {
    document.documentElement.classList.add("dark");
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        {!isAuthenticated ? (
          <Login onLoginSuccess={() => setIsAuthenticated(true)} />
        ) : (
          <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, "")}>
            <Router />
          </WouterRouter>
        )}
        <Toaster />
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;
