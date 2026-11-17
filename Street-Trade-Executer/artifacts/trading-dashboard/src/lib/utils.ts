import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

const PKT_TIME_ZONE = "Asia/Karachi";

export function formatPktDateTime(ts: string | number | Date | null | undefined): string {
  if (ts === null || ts === undefined || ts === "") return "-";
  const d = ts instanceof Date ? ts : new Date(ts);
  if (isNaN(d.getTime())) return "-";
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: PKT_TIME_ZONE,
    weekday: "long",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  }).formatToParts(d);
  const get = (t: string) => parts.find((p) => p.type === t)?.value || "";
  const dp = (get("dayPeriod") || "").toUpperCase();
  return `${get("weekday")}, ${get("day")}/${get("month")}/${get("year")}, ${get("hour")}:${get("minute")}:${get("second")} ${dp} PKT`;
}

export function formatPktTime(
  ts: string | number | Date | null | undefined,
  opts: { withSeconds?: boolean; hour12?: boolean; suffix?: boolean } = {}
): string {
  if (ts === null || ts === undefined || ts === "") return "-";
  const d = ts instanceof Date ? ts : new Date(ts);
  if (isNaN(d.getTime())) return "-";
  const { withSeconds = true, hour12 = true, suffix = true } = opts;
  const formatted = d.toLocaleTimeString("en-US", {
    timeZone: PKT_TIME_ZONE,
    hour: "2-digit",
    minute: "2-digit",
    ...(withSeconds ? { second: "2-digit" } : {}),
    hour12,
  });
  return suffix ? `${formatted} PKT` : formatted;
}
