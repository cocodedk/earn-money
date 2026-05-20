import { useCallback, useEffect, useRef, useState } from "react";
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
const MAX_SSE_ATTEMPTS = 5;
const BACKOFF_CAP_MS = 30_000;

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

function backoffMs(attempt: number): number {
  return Math.min(1000 * 2 ** attempt, BACKOFF_CAP_MS);
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
  const attemptsRef = useRef(0);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearRetryTimer = useCallback(() => {
    if (retryTimerRef.current !== null) {
      clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }
  }, []);

  useEffect(() => {
    setEvents([]);
  }, [scanRunId]);

  useEffect(() => {
    if (!scanRunId || !livePolling) {
      clearRetryTimer();
      attemptsRef.current = 0;
      setStatus("closed");
      return;
    }
    if (isKillSwitchOn()) {
      clearRetryTimer();
      attemptsRef.current = 0;
      setStatus("disabled");
      return;
    }

    const url = `/sse/scan-runs/${scanRunId}/events/`;
    const es = new EventSource(url);
    setStatus("connecting");

    es.onopen = () => {
      attemptsRef.current = 0;
      setStatus("connected");
    };
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
    es.onerror = () => {
      es.close();
      if (attemptsRef.current >= MAX_SSE_ATTEMPTS) {
        setStatus("polling-fallback");
        return;
      }
      const delay = backoffMs(attemptsRef.current);
      attemptsRef.current += 1;
      setStatus("reconnecting");
      clearRetryTimer();
      retryTimerRef.current = setTimeout(() => {
        retryTimerRef.current = null;
        setOpenToken((n) => n + 1);
      }, delay);
    };

    return () => {
      es.close();
      clearRetryTimer();
    };
  }, [scanRunId, livePolling, maxBuffer, openToken, clearRetryTimer]);

  const reconnect = useCallback(() => {
    clearRetryTimer();
    attemptsRef.current = 0;
    setOpenToken((n) => n + 1);
  }, [clearRetryTimer]);

  const clear = useCallback(() => {
    setEvents([]);
  }, []);

  return { events, status, reconnect, clear };
}
