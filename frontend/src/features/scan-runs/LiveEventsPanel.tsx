import { EventList } from "../../components/EventList";
import { useScanRunEvents } from "../../lib/useScanRunEvents";

export type LiveEventsPanelProps = { scanRunId: string };

export function LiveEventsPanel({ scanRunId }: LiveEventsPanelProps) {
  const { events, status } = useScanRunEvents(scanRunId);
  return (
    <div data-testid="live-events-panel" data-status={status}>
      <EventList events={events} />
    </div>
  );
}
