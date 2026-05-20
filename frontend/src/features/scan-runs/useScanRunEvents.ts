import { useCallback, useEffect, useState } from "react";
import type { Event as ApiEvent } from "../../types/api";

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

interface Options {
  livePolling?: boolean;
  maxBuffer?: number;
}

const KILL_SWITCH_KEY = "disable_live_events";
const DEFAULT_MAX_BUFFER = 500;

function isKillSwitchOn(): boolean {
  return localStorage.getItem(KILL_SWITCH_KEY) === "1";
}

function isApiEvent(value: unknown): value is ApiEvent {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  return typeof v.id === "string" && typeof v.type === "string";
}

function mergeEvent(prev: ApiEvent[], next: ApiEvent, cap: number): ApiEvent[] {
  const idx = prev.findIndex((e) => e.id === next.id);
  if (idx >= 0) {
    const copy = prev.slice();
    copy[idx] = next;
    return copy;
  }
  const appended = [...prev, next];
  return appended.length > cap ? appended.slice(appended.length - cap) : appended;
}

export function useScanRunEvents(
  scanRunId: string | undefined,
  options?: Options,
): UseScanRunEventsResult {
  const livePolling = Boolean(options?.livePolling);
  const maxBuffer = options?.maxBuffer ?? DEFAULT_MAX_BUFFER;

  const [events, setEvents] = useState<ApiEvent[]>([]);
  const [status, setStatus] = useState<ConnectionStatus>("closed");
  const [openToken, setOpenToken] = useState(0);

  useEffect(() => {
    setEvents([]);
  }, [scanRunId]);

  useEffect(() => {
    if (!scanRunId || !livePolling) {
      setStatus("closed");
      return;
    }
    if (isKillSwitchOn()) {
      setStatus("disabled");
      return;
    }

    const url = `/sse/scan-runs/${scanRunId}/events/`;
    const es = new EventSource(url);
    setStatus("connecting");

    es.onopen = () => setStatus("connected");
    es.onmessage = (e: MessageEvent) => {
      let parsed: unknown;
      try {
        parsed = JSON.parse(e.data);
      } catch {
        return;
      }
      if (!isApiEvent(parsed)) return;
      setEvents((prev) => mergeEvent(prev, parsed, maxBuffer));
    };

    return () => {
      es.close();
    };
  }, [scanRunId, livePolling, maxBuffer, openToken]);

  const reconnect = useCallback(() => {
    setOpenToken((n) => n + 1);
  }, []);

  const clear = useCallback(() => {
    setEvents([]);
  }, []);

  return { events, status, reconnect, clear };
}
