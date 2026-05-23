# Mission Viewer Plan — Task 8: MissionViewerPage and Wiring

**Goal:** Route shell that ties everything together: session query, SSE, MissionStrip, StoryTimeline. Wire into App.tsx.

---

### Task 10: MissionViewerPage

**Files:**
- Create: `frontend/src/features/missions/MissionViewerPage.tsx`
- Create: `frontend/src/features/missions/MissionViewerPage.test.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/features/missions/MissionViewerPage.test.tsx`:

```typescript
import { describe, it, expect, afterEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { MockEventSource } from "../../test/sseMock";
import { renderWithProviders } from "../../test/renderWithProviders";
import { MissionViewerPage } from "./MissionViewerPage";
import {
  makeSession,
  makeTurn,
  makeNote,
  makeAction,
  SESSION_ID,
  SCAN_RUN_ID,
} from "./__fixtures__/mission";

function paged<T>(results: T[]) {
  return { count: results.length, next: null, previous: null, results };
}

function renderAt(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/missions/:sessionId" element={<MissionViewerPage />} />
    </Routes>,
    { route },
  );
}

afterEach(() => {
  MockEventSource.instances = [];
  MockEventSource.autoOpen = true;
});

describe("MissionViewerPage", () => {
  it("loads session and renders mission strip + timeline", async () => {
    const session = makeSession();
    const turn = makeTurn({ index: 0, actions: [makeAction({ goal: "Looked at home" })] });
    server.use(
      msw.get(`/api/agent-sessions/${SESSION_ID}/`, () =>
        HttpResponse.json(session),
      ),
      msw.get(`/api/agent-sessions/${SESSION_ID}/turns/`, () =>
        HttpResponse.json(paged([turn])),
      ),
      msw.get(`/api/agent-sessions/${SESSION_ID}/notes/`, () =>
        HttpResponse.json(paged([])),
      ),
    );

    renderAt(`/missions/${SESSION_ID}`);

    await waitFor(() => {
      expect(screen.getByText("juice_shop_scoreboard")).toBeInTheDocument();
    });
    expect(screen.getByText("Looked at home")).toBeInTheDocument();
  });

  it("shows loading state before session loads", () => {
    server.use(
      msw.get(`/api/agent-sessions/${SESSION_ID}/`, () =>
        new Promise(() => {}),
      ),
    );
    renderAt(`/missions/${SESSION_ID}`);
    expect(screen.getByText("Loading mission...")).toBeInTheDocument();
  });

  it("shows 404 when session not found", async () => {
    server.use(
      msw.get(`/api/agent-sessions/${SESSION_ID}/`, () =>
        HttpResponse.json({ detail: "Not found." }, { status: 404 }),
      ),
    );
    renderAt(`/missions/${SESSION_ID}`);
    await waitFor(() => {
      expect(screen.getByText("Mission not found")).toBeInTheDocument();
    });
  });

  it("shows inline error when turns fail but session loaded", async () => {
    const session = makeSession();
    server.use(
      msw.get(`/api/agent-sessions/${SESSION_ID}/`, () =>
        HttpResponse.json(session),
      ),
      msw.get(`/api/agent-sessions/${SESSION_ID}/turns/`, () =>
        HttpResponse.json({ detail: "error" }, { status: 500 }),
      ),
      msw.get(`/api/agent-sessions/${SESSION_ID}/notes/`, () =>
        HttpResponse.json(paged([])),
      ),
    );
    renderAt(`/missions/${SESSION_ID}`);
    await waitFor(() => {
      expect(screen.getByText("juice_shop_scoreboard")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText(/could not load turns/i)).toBeInTheDocument();
    });
  });

  it("opens SSE for running sessions", async () => {
    const session = makeSession({ status: "running" });
    server.use(
      msw.get(`/api/agent-sessions/${SESSION_ID}/`, () =>
        HttpResponse.json(session),
      ),
      msw.get(`/api/agent-sessions/${SESSION_ID}/turns/`, () =>
        HttpResponse.json(paged([])),
      ),
      msw.get(`/api/agent-sessions/${SESSION_ID}/notes/`, () =>
        HttpResponse.json(paged([])),
      ),
    );
    renderAt(`/missions/${SESSION_ID}`);
    await waitFor(() => {
      expect(screen.getByText("juice_shop_scoreboard")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(MockEventSource.instances.length).toBeGreaterThanOrEqual(1);
      expect(MockEventSource.instances[0].url).toContain(SCAN_RUN_ID);
    });
  });

  it("does not open SSE for terminal sessions", async () => {
    const session = makeSession({ status: "completed" });
    server.use(
      msw.get(`/api/agent-sessions/${SESSION_ID}/`, () =>
        HttpResponse.json(session),
      ),
      msw.get(`/api/agent-sessions/${SESSION_ID}/turns/`, () =>
        HttpResponse.json(paged([])),
      ),
      msw.get(`/api/agent-sessions/${SESSION_ID}/notes/`, () =>
        HttpResponse.json(paged([])),
      ),
    );
    renderAt(`/missions/${SESSION_ID}`);
    await waitFor(() => {
      expect(screen.getByText("juice_shop_scoreboard")).toBeInTheDocument();
    });
    expect(MockEventSource.instances).toHaveLength(0);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/features/missions/MissionViewerPage.test.tsx`
Expected: FAIL — `MissionViewerPage` not found.

- [ ] **Step 3: Implement MissionViewerPage**

Create `frontend/src/features/missions/MissionViewerPage.tsx`:

```tsx
import { useParams } from "react-router-dom";
import { ROUTES } from "../../app/routes";
import { PageHeader } from "../../components/PageHeader";
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
  const isTruncated = turnsQ.data?.next !== null && turnsQ.data?.next !== undefined;
  const isNotesTruncated = notesQ.data?.next !== null && notesQ.data?.next !== undefined;

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
      <StoryTimeline
        turns={turns}
        notes={notes}
        isLive={!terminal}
        isTruncated={isTruncated}
        isNotesTruncated={isNotesTruncated}
      />
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/features/missions/MissionViewerPage.test.tsx`
Expected: PASS

- [ ] **Step 5: Wire into App.tsx**

Add import and route to `frontend/src/App.tsx`:

```typescript
// Add import at top:
import { MissionViewerPage } from "./features/missions/MissionViewerPage";

// Add route inside <Route element={<Layout />}>, before the catch-all:
<Route path={ROUTES.missionDetail} element={<MissionViewerPage />} />
```

- [ ] **Step 6: Run full test suite**

Run: `cd frontend && npx vitest run`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/missions/MissionViewerPage.tsx frontend/src/features/missions/MissionViewerPage.test.tsx frontend/src/App.tsx
git commit -m "feat(frontend): MissionViewerPage — route shell wiring strip + timeline + SSE"
```
