import { useCallback, useEffect, useRef, useState } from "react";
import type { Event as ApiEvent } from "../../types/api";
import { usePollingFallback } from "./useScanRunEvents.polling";
import {
  type ConnectionStatus,
  DEFAULT_MAX_BUFFER,
  MAX_SSE_ATTEMPTS,
  type ScanRunEventsOptions,
  type UseScanRunEventsResult,
  backoffMs,
  isApiEvent,
  isKillSwitchOn,
  mergeEvent,
} from "./useScanRunEvents.utils";

export type { ConnectionStatus, UseScanRunEventsResult } from "./useScanRunEvents.utils";

export function useScanRunEvents(
  scanRunId: string | undefined,
  options?: ScanRunEventsOptions,
): UseScanRunEventsResult {
  const livePolling = Boolean(options?.livePolling);
  const maxBuffer = options?.maxBuffer ?? DEFAULT_MAX_BUFFER;

  const [events, setEvents] = useState<ApiEvent[]>([]);
  const [status, setStatus] = useState<ConnectionStatus>("closed");
  const [openToken, setOpenToken] = useState(0);
  const attemptsRef = useRef(0);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const eventsRef = useRef<ApiEvent[]>([]);

  useEffect(() => {
    eventsRef.current = events;
  }, [events]);

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

  usePollingFallback({
    scanRunId,
    enabled: status === "polling-fallback" && livePolling,
    maxBuffer,
    eventsRef,
    setEvents,
  });

  const reconnect = useCallback(() => {
    clearRetryTimer();
    attemptsRef.current = 0;
    setStatus("connecting");
    setOpenToken((n) => n + 1);
  }, [clearRetryTimer]);

  const clear = useCallback(() => {
    setEvents([]);
    eventsRef.current = [];
  }, []);

  return { events, status, reconnect, clear };
}
