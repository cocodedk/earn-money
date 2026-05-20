import { useTargetEventsQuery } from "../api";
import { TargetSection } from "./TargetSection";
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
  return (
    <TargetSection<ApiEvent>
      query={useTargetEventsQuery(targetId)}
      columns={columns}
      rowTestIdPrefix="target-event-row-"
      copy={{
        slug: "target-events",
        heading: "Events for target",
        errorMessage: "Could not load events.",
        loadingMessage: "Loading events…",
        emptyMessage: "No events yet for this target.",
        truncationNoun: "events",
      }}
    />
  );
}
