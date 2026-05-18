import { useEffect, useState } from "react";
import type { ScanEvent } from "../types/api";

export type ScanRunEventsStatus =
  | "connecting"
  | "open"
  | "closed";

export type UseScanRunEventsResult = {
  events: ScanEvent[];
  status: ScanRunEventsStatus;
};

export function useScanRunEvents(scanRunId: string): UseScanRunEventsResult {
  const [events, setEvents] = useState<ScanEvent[]>([]);
  const [status, setStatus] = useState<ScanRunEventsStatus>("connecting");

  useEffect(() => {
    setEvents([]);
    setStatus("connecting");
    const source = new EventSource(`/sse/scan-runs/${scanRunId}/events/`);
    source.onopen = () => setStatus("open");
    source.onmessage = (event: MessageEvent) => {
      const payload = JSON.parse(event.data) as ScanEvent;
      setEvents((prev) => [...prev, payload]);
    };
    source.onerror = () => {
      source.close();
      setStatus("closed");
    };
    return () => {
      source.close();
    };
  }, [scanRunId]);

  return { events, status };
}
