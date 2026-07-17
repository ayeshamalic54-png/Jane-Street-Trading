import { useState, useEffect, useRef, useCallback } from "react";

export interface WsDashboardData {
  systemStatus: string;
  currentPair: string;
  lastUpdate: string | null;
  equity: number;
  drawdownPercent: number;
  floatingProfit: number;
  zScore: number;
  hedgeRatio: number;
  obiA: number;
  obiB: number;
  tradesToday: number;
  maxTrades: number;
  activePositions: Array<{
    ticket: number;
    symbol: string;
    type: string;
    lots: number;
    entry: number;
    current: number;
    profit: number;
    comment: string;
  }>;
  recentTrades: Array<{
    ticket: number;
    symbol: string;
    orderType: string;
    lots: number;
    entryPrice: number;
    closePrice: number | null;
    profit: number | null;
    entryTime: string;
    closeTime: string | null;
    status: string;
    comment: string | null;
  }>;
  activeZones: Array<{ type: string; label: string; range: string }>;
  scannedAssets: Array<{
    symbolPair: string;
    priceA: number;
    priceB: number;
    winRate: number;
    zScore: number;
    action: string;
  }>;
  botOnline: boolean;
  autoExecute: boolean;
  cryptoEnabled?: boolean;
  metalsEnabled?: boolean;
  forexEnabled?: boolean;
  indicesEnabled?: boolean;
  initialBalance?: number;
  overallDrawdown?: number;
  maxEquityPeak?: number;
  mt5Login?: number;
}

export function useLiveDashboard() {
  const [data, setData] = useState<WsDashboardData | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/ws`);
    wsRef.current = ws;

    ws.onopen = () => {
      if (mountedRef.current) setWsConnected(true);
    };

    ws.onclose = () => {
      if (mountedRef.current) {
        setWsConnected(false);
        reconnectRef.current = setTimeout(connect, 2500);
      }
    };

    ws.onerror = () => {
      ws.close();
    };

    ws.onmessage = (ev) => {
      if (!mountedRef.current) return;
      try {
        const msg = JSON.parse(ev.data as string) as { type: string; data: WsDashboardData };
        if (msg.type === "dashboard") {
          setData(msg.data);
        }
      } catch {
        // ignore parse errors
      }
    };
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { data, wsConnected };
}
