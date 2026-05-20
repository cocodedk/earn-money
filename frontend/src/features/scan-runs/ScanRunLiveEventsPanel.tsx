import { useScanRunEvents } from "./useScanRunEvents";
import type { ConnectionStatus } from "./useScanRunEvents.utils";
import type { Event as ApiEvent, EventLevel } from "../../types/api";

type Props = { scanRunId: string; livePolling: boolean };

const PILL_CLASS: Record<ConnectionStatus, string> = {
  connecting: "bg-amber-100 text-amber-800",
  connected: "bg-green-100 text-green-800",
  reconnecting: "bg-amber-100 text-amber-800",
  "polling-fallback": "bg-blue-100 text-blue-800",
  closed: "bg-gray-100 text-gray-800",
  disabled: "bg-red-100 text-red-800",
};

const EMPTY_HINT: Record<ConnectionStatus, string> = {
  connecting: "Connecting…",
  connected: "No events yet",
  reconnecting: "Reconnecting…",
  "polling-fallback": "SSE unavailable — polling for events.",
  closed: "Disconnected",
  disabled:
    "Live events disabled (run \"localStorage.removeItem('disable_live_events')\" in DevTools and reload to re-enable).",
};

const LEVEL_CLASS: Record<EventLevel, string> = {
  debug: "text-gray-600 bg-gray-100",
  info: "text-blue-600 bg-blue-100",
  warning: "text-amber-600 bg-amber-100",
  error: "text-red-600 bg-red-100",
};

function fmtTarget(target: string | null): string {
  return target ? target.slice(0, 8) : "—";
}

function EventRow({ event }: { event: ApiEvent }): JSX.Element {
  return (
    <tr data-testid={`event-row-${event.id}`}>
      <td>{new Date(event.created_at).toLocaleTimeString()}</td>
      <td className={`px-1 rounded ${LEVEL_CLASS[event.level]}`}>
        {event.level}
      </td>
      <td>{fmtTarget(event.target)}</td>
      <td>{event.type}</td>
      <td>{event.message}</td>
    </tr>
  );
}

export function ScanRunLiveEventsPanel({
  scanRunId,
  livePolling,
}: Props): JSX.Element {
  const { events, status } = useScanRunEvents(scanRunId, { livePolling });
  const hasEvents = events.length > 0;

  return (
    <section>
      <header className="flex items-center gap-2">
        <h3>Live events</h3>
        <span
          data-testid="events-connection-status"
          className={`sticky top-0 px-2 py-0.5 rounded text-xs font-medium ${PILL_CLASS[status]}`}
        >
          {status}
        </span>
      </header>
      {!hasEvents && <p>{EMPTY_HINT[status]}</p>}
      {hasEvents && (
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
            {events.map((e) => (
              <EventRow key={e.id} event={e} />
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
