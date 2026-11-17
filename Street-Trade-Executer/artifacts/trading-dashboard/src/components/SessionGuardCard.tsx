import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useToast } from "@/hooks/use-toast";
import { useQueryClient } from "@tanstack/react-query";
import { getGetConfigQueryKey, getGetDashboardQueryKey } from "@workspace/api-client-react";

export interface SessionGuardState {
  enabled: boolean;
  startHour: number;
  endHour: number;
  session2Enabled: boolean;
  session2StartHour: number;
  session2EndHour: number;
}

interface SessionGuardCardProps {
  data: any;
  isReadOnly?: boolean;
  onSynced?: (state: SessionGuardState) => void;
}

const HALF_HOUR_OPTIONS: { value: number; label: string }[] = Array.from({ length: 48 }, (_, idx) => {
  const value = idx * 0.5;
  const h24 = Math.floor(value);
  const mins = value % 1 === 0.5 ? "30" : "00";
  const ampm = h24 < 12 ? "AM" : "PM";
  const h12 = h24 === 0 ? 12 : h24 > 12 ? h24 - 12 : h24;
  return {
    value,
    label: `${String(h12).padStart(2, "0")}:${mins} ${ampm} PKT`,
  };
});

function formatHourPkt(val: number): string {
  const matched = HALF_HOUR_OPTIONS.find((o) => Math.abs(o.value - val) < 0.01);
  return matched ? matched.label : `${val}:00 PKT`;
}

function snapHalfHour(raw: any, fallback: number): number {
  const num = Number(raw);
  if (!Number.isFinite(num)) return fallback;
  const clamped = ((num % 24) + 24) % 24;
  return Math.round(clamped * 2) / 2;
}

export function extractSessionState(data: any): SessionGuardState {
  return {
    enabled: Boolean(data?.sessionGuardEnabled ?? data?.session_guard_enabled ?? false),
    startHour: snapHalfHour(data?.sessionStartHour ?? data?.session_start_hour, 12.0),
    endHour: snapHalfHour(data?.sessionEndHour ?? data?.session_end_hour, 16.0),
    session2Enabled: Boolean(data?.session2Enabled ?? data?.session2_enabled ?? true),
    session2StartHour: snapHalfHour(data?.session2StartHour ?? data?.session2_start_hour, 18.0),
    session2EndHour: snapHalfHour(data?.session2EndHour ?? data?.session2_end_hour, 22.0),
  };
}

function getCurrentPktDecimal(): { decimal: number; label: string } {
  const now = new Date();
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Karachi",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(now);
  const get = (t: string) => Number(parts.find((p) => p.type === t)?.value || "0");
  const h = get("hour") % 24;
  const m = get("minute");
  const label = now.toLocaleTimeString("en-US", {
    timeZone: "Asia/Karachi",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  });
  return { decimal: h + m / 60, label: `${label} PKT` };
}

function isInWindow(val: number, startH: number, endH: number): boolean {
  if (Math.abs(startH - endH) < 1e-6) return true;
  if (startH < endH) return val >= startH && val < endH;
  return val >= startH || val < endH;
}

export function SessionGuardCard({ data, isReadOnly = false, onSynced }: SessionGuardCardProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<SessionGuardState | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [pktNow, setPktNow] = useState(() => getCurrentPktDecimal());

  useEffect(() => {
    const t = setInterval(() => setPktNow(getCurrentPktDecimal()), 15000);
    return () => clearInterval(t);
  }, []);

  const serverState = extractSessionState(data);
  const state = draft ?? serverState;

  const windowOpenNow =
    isInWindow(pktNow.decimal, state.startHour, state.endHour) ||
    (state.session2Enabled && isInWindow(pktNow.decimal, state.session2StartHour, state.session2EndHour));

  const scheduleSummary = !state.enabled
    ? "Session Guard OFF — Bot trades 24/7 unrestricted"
    : state.session2Enabled
    ? `Active Windows: ${formatHourPkt(state.startHour)} – ${formatHourPkt(state.endHour)}  &  ${formatHourPkt(state.session2StartHour)} – ${formatHourPkt(state.session2EndHour)}`
    : `Active Window: ${formatHourPkt(state.startHour)} – ${formatHourPkt(state.endHour)}`;

  const persistState = async (next: SessionGuardState, actionLabel: string) => {
    if (isReadOnly || isSaving) return;
    setDraft(next);
    setIsSaving(true);
    try {
      const res = await fetch("/api/toggle-session-guard", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          enabled: next.enabled,
          start_hour: next.startHour,
          end_hour: next.endHour,
          session2_enabled: next.session2Enabled,
          session2_start_hour: next.session2StartHour,
          session2_end_hour: next.session2EndHour,
        }),
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const savedJson = await res.json();
      const confirmed = extractSessionState(savedJson);
      setDraft(null);
      onSynced?.(confirmed);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: getGetConfigQueryKey() }),
        queryClient.invalidateQueries({ queryKey: getGetDashboardQueryKey() }),
      ]);
      toast({
        title: confirmed.enabled ? "Session Guard ENABLED 🟢" : "Session Guard DISABLED 🔴",
        description: `${actionLabel} — synced to Dashboard, Config & VPS bot log.`,
      });
    } catch (err: any) {
      setDraft(null);
      toast({
        title: "Session Guard Update Failed",
        description: err?.message || "Could not save Session Guard settings to backend.",
        variant: "destructive",
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Card className={cn(
      "rounded-md p-4 transition-all border space-y-3",
      state.enabled ? "bg-blue-500/5 border-blue-500/40" : "bg-zinc-900/60 border-zinc-800"
    )}>
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <div className="flex items-start gap-2.5">
          <span className="text-xl leading-none mt-0.5">⏰</span>
          <div>
            <div className="font-bold text-sm text-zinc-100">
              Session Time Guard (Pakistani Time PKT Trading Windows)
            </div>
            <div className="text-xs font-mono text-sky-300 mt-0.5">
              {scheduleSummary}
            </div>
            <div className="text-[11px] text-zinc-400 mt-0.5">
              Active Breakeven &amp; SL/TP management remain active 24/7.
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Badge variant="outline" className="font-mono text-[10px] border-zinc-700 text-zinc-300">
            Now: {pktNow.label}
          </Badge>
          <span className={cn(
            "px-2.5 py-1 rounded text-xs font-bold border",
            !state.enabled
              ? "bg-zinc-800 text-zinc-400 border-zinc-700"
              : windowOpenNow
              ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/40"
              : "bg-amber-500/20 text-amber-300 border-amber-500/40"
          )}>
            {!state.enabled
              ? "🔴 DISABLED (24/7)"
              : windowOpenNow
              ? "🟢 ACTIVE · WINDOW OPEN"
              : "🟠 ACTIVE · OUTSIDE WINDOW"}
          </span>
        </div>
      </div>

      {/* Top row: Master Toggle + Preset Button */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 border-t border-border/50">
        <div>
          <label className="text-[10px] font-bold text-blue-400 uppercase block mb-1">
            Session Guard Toggle
          </label>
          <div className="flex gap-2">
            <Button
              type="button"
              size="sm"
              disabled={isReadOnly || isSaving}
              onClick={() => persistState({ ...state, enabled: true }, "Restricted to PKT windows")}
              className={cn(
                "flex-1 font-mono text-xs font-bold h-8",
                state.enabled
                  ? "bg-emerald-600 hover:bg-emerald-500 text-white"
                  : "bg-zinc-900 hover:bg-zinc-800 text-zinc-400 border border-zinc-700"
              )}
            >
              🟢 ENABLED
            </Button>
            <Button
              type="button"
              size="sm"
              disabled={isReadOnly || isSaving}
              onClick={() => persistState({ ...state, enabled: false }, "Trading 24/7 unrestricted")}
              className={cn(
                "flex-1 font-mono text-xs font-bold h-8",
                !state.enabled
                  ? "bg-rose-600 hover:bg-rose-500 text-white"
                  : "bg-zinc-900 hover:bg-zinc-800 text-zinc-400 border border-zinc-700"
              )}
            >
              🔴 DISABLED (24/7)
            </Button>
          </div>
        </div>

        <div className="flex items-end">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={isReadOnly || isSaving}
            onClick={() =>
              persistState(
                {
                  enabled: true,
                  startHour: 12.0,
                  endHour: 16.0,
                  session2Enabled: true,
                  session2StartHour: 18.0,
                  session2EndHour: 22.0,
                },
                "Dual Killzones (12:00-4:00 PM & 6:00-10:00 PM PKT)"
              )
            }
            className="w-full h-8 font-mono text-[11px] font-bold border-sky-500/40 text-sky-300 hover:bg-sky-500/15"
          >
            ⚡ Optimal Preset: 12:00–4:00 PM &amp; 6:00–10:00 PM PKT
          </Button>
        </div>
      </div>

      {/* Window 1 (London) & Window 2 (NY) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
        <div className="p-2.5 rounded border border-emerald-500/20 bg-zinc-950/60 space-y-2">
          <div className="text-[10px] font-bold text-emerald-400 uppercase">
            Window 1 (London Session · 12:00 PM – 04:00 PM PKT)
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[10px] text-zinc-400 block mb-1">Start (PKT)</label>
              <select
                disabled={isReadOnly || isSaving}
                value={String(state.startHour)}
                onChange={(e) => {
                  const next = { ...state, startHour: parseFloat(e.target.value) };
                  void persistState(next, "Window 1 start updated");
                }}
                className="w-full bg-background border border-input rounded p-1.5 text-xs font-mono font-bold text-foreground focus:outline-none"
              >
                {HALF_HOUR_OPTIONS.map((opt) => (
                  <option key={opt.value} value={String(opt.value)}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-[10px] text-zinc-400 block mb-1">End (PKT)</label>
              <select
                disabled={isReadOnly || isSaving}
                value={String(state.endHour)}
                onChange={(e) => {
                  const next = { ...state, endHour: parseFloat(e.target.value) };
                  void persistState(next, "Window 1 end updated");
                }}
                className="w-full bg-background border border-input rounded p-1.5 text-xs font-mono font-bold text-foreground focus:outline-none"
              >
                {HALF_HOUR_OPTIONS.map((opt) => (
                  <option key={opt.value} value={String(opt.value)}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        <div className="p-2.5 rounded border border-indigo-500/20 bg-zinc-950/60 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold text-indigo-400 uppercase">
              Window 2 (NY Session · 06:00 PM – 10:00 PM PKT)
            </span>
            <button
              type="button"
              disabled={isReadOnly || isSaving}
              onClick={() => {
                const next = { ...state, session2Enabled: !state.session2Enabled };
                void persistState(next, `Window 2 ${next.session2Enabled ? "ENABLED" : "DISABLED"}`);
              }}
              className={cn(
                "text-[10px] font-mono font-bold px-2 py-0.5 rounded border",
                state.session2Enabled
                  ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
                  : "bg-zinc-800 text-zinc-400 border-zinc-700"
              )}
            >
              {state.session2Enabled ? "ON 🟢" : "OFF 🔴"}
            </button>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[10px] text-zinc-400 block mb-1">Start (PKT)</label>
              <select
                disabled={isReadOnly || isSaving || !state.session2Enabled}
                value={String(state.session2StartHour)}
                onChange={(e) => {
                  const next = { ...state, session2StartHour: parseFloat(e.target.value) };
                  void persistState(next, "Window 2 start updated");
                }}
                className="w-full bg-background border border-input rounded p-1.5 text-xs font-mono font-bold text-foreground focus:outline-none disabled:opacity-40"
              >
                {HALF_HOUR_OPTIONS.map((opt) => (
                  <option key={opt.value} value={String(opt.value)}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-[10px] text-zinc-400 block mb-1">End (PKT)</label>
              <select
                disabled={isReadOnly || isSaving || !state.session2Enabled}
                value={String(state.session2EndHour)}
                onChange={(e) => {
                  const next = { ...state, session2EndHour: parseFloat(e.target.value) };
                  void persistState(next, "Window 2 end updated");
                }}
                className="w-full bg-background border border-input rounded p-1.5 text-xs font-mono font-bold text-foreground focus:outline-none disabled:opacity-40"
              >
                {HALF_HOUR_OPTIONS.map((opt) => (
                  <option key={opt.value} value={String(opt.value)}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
}
