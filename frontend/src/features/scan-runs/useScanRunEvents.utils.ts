import type { Event as ApiEvent, Paginated } from "../../types/api";

export type ConnectionStatus =
  | "connecting"
  | "connected"
  | "reconnecting"
  | "polling-fallback"
  | "closed"
  | "disabled";

export interface UseScanRunEventsResult {
  events: ApiEvent[];
  status: ConnectionStatus;
  reconnect: () => void;
  clear: () => void;
}

export interface ScanRunEventsOptions {
  livePolling?: boolean;
  maxBuffer?: number;
}

export const KILL_SWITCH_KEY = "disable_live_events";
export const DEFAULT_MAX_BUFFER = 500;
export const MAX_SSE_ATTEMPTS = 5;
const BACKOFF_CAP_MS = 30_000;
export const POLL_INTERVAL_MS = 2000;

export function isKillSwitchOn(): boolean {
  return localStorage.getItem(KILL_SWITCH_KEY) === "1";
}

export function isApiEvent(value: unknown): value is ApiEvent {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  return typeof v.id === "string" && typeof v.type === "string";
}

export function mergeEvent(
  prev: ApiEvent[],
  next: ApiEvent,
  cap: number,
): ApiEvent[] {
  const idx = prev.findIndex((e) => e.id === next.id);
  if (idx >= 0) {
    const copy = prev.slice();
    copy[idx] = next;
    return copy;
  }
  const appended = [...prev, next];
  return appended.length > cap
    ? appended.slice(appended.length - cap)
    : appended;
}

export function mergeEvents(
  prev: ApiEvent[],
  incoming: ApiEvent[],
  cap: number,
): ApiEvent[] {
  let buf = prev;
  for (const e of incoming) buf = mergeEvent(buf, e, cap);
  return buf;
}

export function backoffMs(attempt: number): number {
  return Math.min(1000 * 2 ** attempt, BACKOFF_CAP_MS);
}

export function hasResults(value: unknown): value is Paginated<ApiEvent> {
  return Array.isArray((value as { results?: unknown } | null)?.results);
}
