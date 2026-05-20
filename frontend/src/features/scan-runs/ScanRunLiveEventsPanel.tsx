import { useEffect, useRef, useState } from "react";
import { useScanRunEvents } from "./useScanRunEvents";
import type { ConnectionStatus } from "./useScanRunEvents.utils";
import type { Event as ApiEvent } from "../../types/api";
import { EventsPanelHeader } from "./EventsPanelHeader";
import styles from "./ScanRunLiveEventsPanel.module.css";

type Props = { scanRunId: string; livePolling: boolean };

const SCROLL_THRESHOLD_PX = 20;

const EMPTY_HINT: Record<ConnectionStatus, string> = {
  connecting: "Connecting…",
  connected: "No events yet",
  reconnecting: "Reconnecting…",
  "polling-fallback": "SSE unavailable — polling for events.",
  closed: "Disconnected",
  disabled:
    "Live events disabled (run \"localStorage.removeItem('disable_live_events')\" in DevTools and reload to re-enable).",
};

function fmtTarget(target: string | null): string {
  return target ? target.slice(0, 8) : "—";
}

function EventRow({
  event,
  rowRef,
}: {
  event: ApiEvent;
  rowRef?: React.Ref<HTMLTableRowElement>;
}): JSX.Element {
  return (
    <tr ref={rowRef} data-testid={`event-row-${event.id}`}>
      <td>{new Date(event.created_at).toLocaleTimeString()}</td>
      <td data-level={event.level} className={styles.levelCell}>
        {event.level}
      </td>
      <td>{fmtTarget(event.target)}</td>
      <td>{event.type}</td>
      <td>{event.message}</td>
    </tr>
  );
}

function isScrolledUp(el: HTMLElement): boolean {
  return el.scrollTop < el.scrollHeight - el.clientHeight - SCROLL_THRESHOLD_PX;
}

export function ScanRunLiveEventsPanel({
  scanRunId,
  livePolling,
}: Props): JSX.Element {
  const { events, status, clear, reconnect } = useScanRunEvents(scanRunId, {
    livePolling,
  });
  const hasEvents = events.length > 0;

  const [autoScroll, setAutoScroll] = useState(true);
  const lastRowRef = useRef<HTMLTableRowElement | null>(null);
  const prevLenRef = useRef(events.length);

  useEffect(() => {
    const prev = prevLenRef.current;
    prevLenRef.current = events.length;
    if (autoScroll && events.length > prev && lastRowRef.current) {
      lastRowRef.current.scrollIntoView({ block: "end" });
    }
  }, [events.length, autoScroll]);

  function onScroll(e: React.UIEvent<HTMLDivElement>): void {
    if (isScrolledUp(e.currentTarget)) {
      setAutoScroll(false);
    }
  }

  return (
    <section>
      <EventsPanelHeader
        status={status}
        autoScroll={autoScroll}
        setAutoScroll={setAutoScroll}
        clear={clear}
        reconnect={reconnect}
      />
      {!hasEvents && <p>{EMPTY_HINT[status]}</p>}
      {hasEvents && (
        <div
          data-testid="events-scroll-container"
          className="max-h-96 overflow-y-auto"
          onScroll={onScroll}
        >
          <table data-testid="events-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Level</th>
                <th>Target</th>
                <th>Event</th>
                <th>Message</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e, i) => (
                <EventRow
                  key={e.id}
                  event={e}
                  rowRef={i === events.length - 1 ? lastRowRef : undefined}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
