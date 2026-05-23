# Task 10 — Tests: MissionViewerPage

Test code for [Task 10](10-mission-viewer-page.md).

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

function stubSession(session = makeSession()) {
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
}

afterEach(() => {
  MockEventSource.instances = [];
  MockEventSource.autoOpen = true;
});

describe("MissionViewerPage", () => {
  it("loads session and renders strip + timeline", async () => {
    const turn = makeTurn({
      index: 0,
      actions: [makeAction({ goal: "Looked at home" })],
    });
    server.use(
      msw.get(`/api/agent-sessions/${SESSION_ID}/`, () =>
        HttpResponse.json(makeSession()),
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

  it("shows loading state", () => {
    server.use(
      msw.get(`/api/agent-sessions/${SESSION_ID}/`, () =>
        new Promise(() => {}),
      ),
    );
    renderAt(`/missions/${SESSION_ID}`);
    expect(screen.getByText("Loading mission...")).toBeInTheDocument();
  });

  it("shows 404", async () => {
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

  it("shows inline error when turns fail", async () => {
    server.use(
      msw.get(`/api/agent-sessions/${SESSION_ID}/`, () =>
        HttpResponse.json(makeSession()),
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

  it("shows inline error when notes fail", async () => {
    server.use(
      msw.get(`/api/agent-sessions/${SESSION_ID}/`, () =>
        HttpResponse.json(makeSession()),
      ),
      msw.get(`/api/agent-sessions/${SESSION_ID}/turns/`, () =>
        HttpResponse.json(paged([])),
      ),
      msw.get(`/api/agent-sessions/${SESSION_ID}/notes/`, () =>
        HttpResponse.json({ detail: "error" }, { status: 500 }),
      ),
    );
    renderAt(`/missions/${SESSION_ID}`);
    await waitFor(() => {
      expect(screen.getByText("juice_shop_scoreboard")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText(/could not load notebook entries/i)).toBeInTheDocument();
    });
  });

  it("shows a turns loading state instead of the empty timeline while loading", async () => {
    server.use(
      msw.get(`/api/agent-sessions/${SESSION_ID}/`, () =>
        HttpResponse.json(makeSession()),
      ),
      msw.get(`/api/agent-sessions/${SESSION_ID}/turns/`, () =>
        new Promise(() => {}),
      ),
      msw.get(`/api/agent-sessions/${SESSION_ID}/notes/`, () =>
        HttpResponse.json(paged([])),
      ),
    );
    renderAt(`/missions/${SESSION_ID}`);
    await waitFor(() => {
      expect(screen.getByText("juice_shop_scoreboard")).toBeInTheDocument();
    });
    expect(screen.getByText("Loading turns...")).toBeInTheDocument();
    expect(screen.queryByText("The agent has not started yet.")).not.toBeInTheDocument();
  });

  it("opens SSE for running sessions", async () => {
    stubSession(makeSession({ status: "running" }));
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
    stubSession(makeSession({ status: "completed" }));
    renderAt(`/missions/${SESSION_ID}`);
    await waitFor(() => {
      expect(screen.getByText("juice_shop_scoreboard")).toBeInTheDocument();
    });
    expect(MockEventSource.instances).toHaveLength(0);
  });
});
```
