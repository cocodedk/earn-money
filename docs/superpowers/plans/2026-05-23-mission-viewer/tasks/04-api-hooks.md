---
tier: FAST
depends_on: [01-types, 02-fixtures]
files:
  creates: [frontend/src/features/missions/api.ts, frontend/src/features/missions/api.test.ts]
  modifies: []
exports:
  - name: useSessionQuery
    file: frontend/src/features/missions/api.ts
  - name: useTurnsQuery
    file: frontend/src/features/missions/api.ts
  - name: useNotesQuery
    file: frontend/src/features/missions/api.ts
  - name: missionKey
    file: frontend/src/features/missions/api.ts
  - name: missionTurnsKey
    file: frontend/src/features/missions/api.ts
  - name: missionNotesKey
    file: frontend/src/features/missions/api.ts
allow_extra_files: false
---

# Task 4: API Hooks

**Goal:** React Query hooks for session detail, turns, and notes.

**Depends on:** [Task 1](01-types.md), [Task 2](02-fixtures.md)

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
  it("is disabled when session id is undefined", () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useTurnsQuery(undefined), {
      wrapper: Wrapper,
    });
    expect(result.current.fetchStatus).toBe("idle");
  });

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
  it("is disabled when session id is undefined", () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useNotesQuery(undefined), {
      wrapper: Wrapper,
    });
    expect(result.current.fetchStatus).toBe("idle");
  });

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
Expected: FAIL — hooks not found.

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
