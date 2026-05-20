import { Callout } from "../../../components/Callout";
import { Table } from "../../../components/Table";
import { useTargetEventsQuery } from "../api";
import type { Event as ApiEvent } from "../../../types/api";

function fmtTime(ts: string): string {
  return new Date(ts).toLocaleTimeString();
}

const columns = [
  { key: "time", header: "Time", cell: (e: ApiEvent) => fmtTime(e.created_at) },
  { key: "level", header: "Level", cell: (e: ApiEvent) => e.level },
  {
    key: "scan_run",
    header: "Scan run",
    cell: (e: ApiEvent) => <code>{e.scan_run.slice(0, 8)}</code>,
  },
  { key: "type", header: "Event", cell: (e: ApiEvent) => e.type },
  { key: "message", header: "Message", cell: (e: ApiEvent) => e.message },
];

export function TargetEventsTable({ targetId }: { targetId: string }) {
  const query = useTargetEventsQuery(targetId);

  if (query.isError) {
    return <Callout variant="error">Could not load events.</Callout>;
  }
  if (!query.data) {
    return <div data-testid="target-events-loading">Loading events…</div>;
  }
  const { results, count, next } = query.data;
  return (
    <section data-testid="target-events-section">
      <h3>Events for target ({count})</h3>
      {count === 0 ? (
        <p data-testid="target-events-empty">No events yet for this target.</p>
      ) : (
        <>
          <Table<ApiEvent>
            columns={columns}
            rows={results}
            rowKey={(e) => e.id}
            rowTestId={(e) => `target-event-row-${e.id}`}
          />
          {next !== null && (
            <p data-testid="target-events-truncation">
              Showing first {results.length} of {count} events
            </p>
          )}
        </>
      )}
    </section>
  );
}
