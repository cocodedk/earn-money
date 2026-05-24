import { useParams } from "react-router-dom";
import { ROUTES } from "../../app/routes";
import { DetailPageGuard } from "../../components/DetailPageGuard";
import { Callout, CalloutSlot } from "../../components/Callout";
import { useSessionQuery, useTurnsQuery, useNotesQuery } from "./api";
import { useAgentEvents } from "./useAgentEvents";
import { MissionStrip } from "./MissionStrip";
import { StoryTimeline } from "./StoryTimeline";
import { isTerminalStatus } from "./types";
import type { AgentSession } from "./types";

function MissionBody({ session }: { session: AgentSession }) {
  const terminal = isTerminalStatus(session.status);
  const turnsQ = useTurnsQuery(session.id);
  const notesQ = useNotesQuery(session.id);
  const { budgetOverlay } = useAgentEvents(
    session.id,
    session.scan_run,
    terminal,
    session.updated_at,
  );

  const turns = turnsQ.data?.results ?? [];
  const notes = notesQ.data?.results ?? [];
  const isTruncated = Boolean(turnsQ.data && turnsQ.data.next !== null);
  const isNotesTruncated = Boolean(notesQ.data && notesQ.data.next !== null);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <MissionStrip session={session} budgetOverlay={budgetOverlay} />
      {turnsQ.isError && (
        <CalloutSlot>
          <Callout variant="warning">Could not load turns. Retrying...</Callout>
        </CalloutSlot>
      )}
      {notesQ.isError && (
        <CalloutSlot>
          <Callout variant="warning">Could not load notebook entries.</Callout>
        </CalloutSlot>
      )}
      {turnsQ.isLoading ? (
        <p style={{ color: "var(--ink-soft)", textAlign: "center", padding: "3rem 0" }}>
          Loading turns...
        </p>
      ) : (
        <StoryTimeline
          turns={turns}
          notes={notes}
          isLive={!terminal}
          isTruncated={isTruncated}
          isNotesTruncated={isNotesTruncated}
        />
      )}
    </div>
  );
}

export function MissionViewerPage() {
  const { sessionId } = useParams();
  const query = useSessionQuery(sessionId);
  return (
    <DetailPageGuard
      query={query}
      options={{
        notFoundTitle: "Mission not found",
        notFoundMessage: `No mission matches "${sessionId}".`,
        backTo: ROUTES.scanRuns,
        backLabel: "Back to scan runs.",
        errorTitle: "Mission",
        errorBody: "Could not load mission.",
        loadingTitle: "Loading mission...",
      }}
    >
      {(session) => <MissionBody session={session} />}
    </DetailPageGuard>
  );
}
