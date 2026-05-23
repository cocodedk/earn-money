# Mission Viewer Plan — Task 2: Routing and API Hooks

**Goal:** Add the `/missions/:sessionId` route and React Query hooks for session, turns, and notes.

---

### Task 3: Route registration

**Files:**
- Modify: `frontend/src/app/routes.ts`
- Modify: `frontend/src/app/routes.test.ts`

- [ ] **Step 1: Write the failing route test**

Add to `frontend/src/app/routes.test.ts`:

```typescript
import {
  ROUTES,
  scanRunDetailPath,
  stubDetailPath,
  missionDetailPath,
} from "./routes";

// Add inside the existing describe block:

it("locks the mission detail route path", () => {
  expect(ROUTES.missionDetail).toBe("/missions/:sessionId");
});

it("builds a mission detail path from a session UUID", () => {
  expect(missionDetailPath("s-1")).toBe("/missions/s-1");
  expect(missionDetailPath("abc-123")).toBe("/missions/abc-123");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/app/routes.test.ts`
Expected: FAIL — `missionDetailPath` not exported, `ROUTES.missionDetail` undefined.

- [ ] **Step 3: Add route and helper**

Add to `frontend/src/app/routes.ts`:

```typescript
// Add to ROUTES object, before the closing `} as const`:
  missionDetail: "/missions/:sessionId",

// Add at end of file:
export const missionDetailPath = (sessionId: string) =>
  `/missions/${sessionId}`;
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/app/routes.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/routes.ts frontend/src/app/routes.test.ts
git commit -m "feat(frontend): add /missions/:sessionId route and helper"
```

---

### Task 4: API hooks

**Files:**
- Create: `frontend/src/features/missions/api.ts`
- Create: `frontend/src/features/missions/api.test.ts`

- [ ] **Step 1: Write failing API hook tests**

Create `frontend/src/features/missions/api.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import { makeSession, makeTurn, makeNote, SESSION_ID } from "./__fixtures__/mission";
import { useSessionQuery, useTurnsQuery, useNotesQuery } from "./api";

function paged<T>(results: T[]) {
  return { count: results.length, next: null, previous: null, results };
}

describe("useSessionQuery", () => {
  it("fetches the session by id", async () => {
    const session = makeSession();
    server.use(
      msw.get(`/api/agent-sessions/${SESSION_ID}/`, () =>
        HttpResponse.json(session),
      ),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useSessionQuery(SESSION_ID), {
      wrapper: Wrapper,
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.id).toBe(SESSION_ID);
  });

  it("is disabled when id is undefined", () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useSessionQuery(undefined), {
      wrapper: Wrapper,
    });
    expect(result.current.fetchStatus).toBe("idle");
  });
});

describe("useTurnsQuery", () => {
  it("fetches paginated turns for a session", async () => {
    const turn = makeTurn({ index: 0 });
    server.use(
      msw.get(`/api/agent-sessions/${SESSION_ID}/turns/`, () =>
        HttpResponse.json(paged([turn])),
      ),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useTurnsQuery(SESSION_ID), {
      wrapper: Wrapper,
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.results).toHaveLength(1);
    expect(result.current.data?.results[0].index).toBe(0);
  });
});

describe("useNotesQuery", () => {
  it("fetches paginated notes for a session", async () => {
    const note = makeNote({ turn_index: 0 });
    server.use(
      msw.get(`/api/agent-sessions/${SESSION_ID}/notes/`, () =>
        HttpResponse.json(paged([note])),
      ),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useNotesQuery(SESSION_ID), {
      wrapper: Wrapper,
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.results).toHaveLength(1);
    expect(result.current.data?.results[0].note_type).toBe("hypothesis");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/features/missions/api.test.ts`
Expected: FAIL — `useSessionQuery`, `useTurnsQuery`, `useNotesQuery` not found.

- [ ] **Step 3: Implement API hooks**

Create `frontend/src/features/missions/api.ts`:

```typescript
import { useQuery } from "@tanstack/react-query";
import { http } from "../../lib/http";
import type { Paginated } from "../../types/api";
import type { AgentNote, AgentSession, AgentTurn } from "./types";
import { isTerminalStatus } from "./types";

export const MISSIONS_KEY = ["missions"] as const;

export const missionKey = (id: string) =>
  [...MISSIONS_KEY, id] as const;

export const missionTurnsKey = (id: string) =>
  [...MISSIONS_KEY, id, "turns"] as const;

export const missionNotesKey = (id: string) =>
  [...MISSIONS_KEY, id, "notes"] as const;

export function useSessionQuery(id: string | undefined) {
  return useQuery({
    queryKey: missionKey(id ?? ""),
    queryFn: () => http<AgentSession>(`/api/agent-sessions/${id}/`),
    enabled: Boolean(id),
    refetchInterval: (q) => {
      const status = q.state.data?.status;
      return status && !isTerminalStatus(status) ? 2000 : false;
    },
  });
}

export function useTurnsQuery(sessionId: string | undefined) {
  return useQuery({
    queryKey: missionTurnsKey(sessionId ?? ""),
    queryFn: () =>
      http<Paginated<AgentTurn>>(
        `/api/agent-sessions/${sessionId}/turns/?page_size=200`,
      ),
    enabled: Boolean(sessionId),
  });
}

export function useNotesQuery(sessionId: string | undefined) {
  return useQuery({
    queryKey: missionNotesKey(sessionId ?? ""),
    queryFn: () =>
      http<Paginated<AgentNote>>(
        `/api/agent-sessions/${sessionId}/notes/?page_size=200`,
      ),
    enabled: Boolean(sessionId),
  });
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/features/missions/api.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/missions/api.ts frontend/src/features/missions/api.test.ts
git commit -m "feat(frontend): mission viewer API hooks — session, turns, notes"
```
