import { useEffect } from "react";
import type { Event as ApiEvent } from "../../types/api";
import {
  POLL_INTERVAL_MS,
  hasResults,
  mergeEvents,
} from "./useScanRunEvents.utils";

interface PollingParams {
  scanRunId: string | undefined;
  enabled: boolean; // true iff status === 'polling-fallback' && livePolling
  maxBuffer: number;
  eventsRef: { current: ApiEvent[] };
  setEvents: React.Dispatch<React.SetStateAction<ApiEvent[]>>;
}

async function pollOnce(
  url: string,
  lastEventId: string | undefined,
): Promise<unknown> {
  const init: RequestInit = {};
  if (lastEventId) init.headers = { "Last-Event-ID": lastEventId };
  const res = await fetch(url, init);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function drain(
  startUrl: string,
  lastEventId: string | undefined,
  maxBuffer: number,
  eventsRef: { current: ApiEvent[] },
  setEvents: React.Dispatch<React.SetStateAction<ApiEvent[]>>,
): Promise<void> {
  let url: string | null = startUrl;
  let anchor = lastEventId;
  while (url) {
    let body: unknown;
    try {
      body = await pollOnce(url, anchor);
    } catch (err) {
      console.warn("[useScanRunEvents] polling fetch failed", err);
      return;
    }
    if (!hasResults(body)) {
      console.warn("[useScanRunEvents] polling response missing 'results'");
      return;
    }
    if (body.results.length > 0) {
      setEvents((prev) => {
        const merged = mergeEvents(prev, body.results, maxBuffer);
        eventsRef.current = merged;
        return merged;
      });
    }
    url = body.next;
    // Subsequent pages of the same drain don't need a Last-Event-ID — DRF's
    // `next` URL already encodes the cursor. Header only applies to page 1.
    anchor = undefined;
  }
}

export function usePollingFallback(params: PollingParams): void {
  const { scanRunId, enabled, maxBuffer, eventsRef, setEvents } = params;
  useEffect(() => {
    if (!enabled || !scanRunId) return;
    const baseUrl = `/api/scan-runs/${scanRunId}/events/`;
    const tick = () => {
      const newest = eventsRef.current[eventsRef.current.length - 1];
      void drain(baseUrl, newest?.id, maxBuffer, eventsRef, setEvents);
    };
    const interval = setInterval(tick, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [enabled, scanRunId, maxBuffer, eventsRef, setEvents]);
}
