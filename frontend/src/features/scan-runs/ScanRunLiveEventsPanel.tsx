import { useScanRunEvents } from "./useScanRunEvents";
import type { ConnectionStatus } from "./useScanRunEvents.utils";

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
          <tbody />
        </table>
      )}
    </section>
  );
}
