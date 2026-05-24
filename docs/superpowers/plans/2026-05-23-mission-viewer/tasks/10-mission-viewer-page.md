---
tier: CAPABLE
depends_on: [03-route, 04-api-hooks, 07-mission-strip, 08-story-timeline, 09-use-agent-events]
files:
  creates: [frontend/src/features/missions/MissionViewerPage.tsx, frontend/src/features/missions/MissionViewerPage.test.tsx]
  modifies: [frontend/src/App.tsx]
exports:
  - name: MissionViewerPage
    file: frontend/src/features/missions/MissionViewerPage.tsx
allow_extra_files: false
---

# Task 10: MissionViewerPage and App.tsx Wiring

**Goal:** Route shell that ties everything together. Wire into App.tsx.

**Depends on:** All previous tasks.

**Files:**
- Create: `frontend/src/features/missions/MissionViewerPage.tsx`
- Create: `frontend/src/features/missions/MissionViewerPage.test.tsx`
- Modify: `frontend/src/App.tsx`

Tests: see [10-mission-viewer-page-tests.md](10-mission-viewer-page-tests.md)

- [ ] **Step 1: Write failing tests** — see test file above.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/features/missions/MissionViewerPage.test.tsx`
Expected: FAIL — `MissionViewerPage` not found.

- [ ] **Step 3: Implement MissionViewerPage**

Create `frontend/src/features/missions/MissionViewerPage.tsx`:

```tsx
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
  );

  const turns = turnsQ.data?.results ?? [];
  const notes = notesQ.data?.results ?? [];
  const isTruncated = Boolean(turnsQ.data && turnsQ.data.next !== null);
  const isNotesTruncated = Boolean(notesQ.data && notesQ.data.next !== null);

  return (
    <div className="flex flex-col h-full">
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
        <p className="text-gray-500 text-center py-8">Loading turns...</p>
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
```

Note: `isTruncated` uses `Boolean(turnsQ.data && turnsQ.data.next !== null)` to avoid flashing the hint during loading.

- [ ] **Step 4: Run tests** — `cd frontend && npx vitest run src/features/missions/MissionViewerPage.test.tsx` → PASS

- [ ] **Step 5: Wire into App.tsx**

```typescript
import { MissionViewerPage } from "./features/missions/MissionViewerPage";
// Add route before catch-all:
<Route path={ROUTES.missionDetail} element={<MissionViewerPage />} />
```

- [ ] **Step 6: Run final verification**

```bash
cd frontend && npx vitest run src/app/routes.test.ts src/features/missions
cd frontend && npx vitest run
cd frontend && npx tsc --noEmit
```

Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/missions/MissionViewerPage.tsx frontend/src/features/missions/MissionViewerPage.test.tsx frontend/src/App.tsx
git commit -m "feat(frontend): MissionViewerPage — route shell wiring strip + timeline + SSE"
```
