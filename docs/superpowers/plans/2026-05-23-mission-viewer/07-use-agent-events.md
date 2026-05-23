# Mission Viewer Plan — Task 7: useAgentEvents Hook

**Goal:** SSE wrapper that filters agent events by session, invalidates React Query caches, and manages the optimistic budget overlay.

---

### Task 9: useAgentEvents

**Files:**
- Create: `frontend/src/features/missions/useAgentEvents.ts`
- Create: `frontend/src/features/missions/useAgentEvents.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/features/missions/useAgentEvents.test.tsx`:

```typescript
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { MockEventSource } from "../../test/sseMock";
import {
  makeRenderHookWrapper,
  makeTestQueryClient,
} from "../../test/renderWithProviders";
import { useAgentEvents } from "./useAgentEvents";
import { makeSession, SESSION_ID, SCAN_RUN_ID } from "./__fixtures__/mission";
import { makeEvent } from "../scan-runs/__fixtures__/event";
import { missionKey, missionTurnsKey, missionNotesKey } from "./api";

function agentEvent(type: string, extra: Record<string, unknown> = {}) {
  return makeEvent({
    id: `evt-${Math.random().toString(36).slice(2, 8)}`,
    type,
    data: { session_id: SESSION_ID, ...extra },
  });
}

describe("useAgentEvents", () => {
  let restore: () => void;
  beforeEach(() => {
    MockEventSource.instances = [];
    MockEventSource.autoOpen = true;
  });
  afterEach(() => {
    MockEventSource.instances = [];
    MockEventSource.autoOpen = true;
  });

  it("filters agent events matching the session id", async () => {
    const { client, Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useAgentEvents(SESSION_ID, SCAN_RUN_ID, false),
      { wrapper: Wrapper },
    );
    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    const es = MockEventSource.instances[0];

    act(() => es.emit(agentEvent("agent.action_executed")));
    act(() => es.emit(makeEvent({ type: "target_started" })));

    expect(result.current.processedCount).toBe(1);
  });

  it("ignores agent events for a different session", async () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useAgentEvents(SESSION_ID, SCAN_RUN_ID, false),
      { wrapper: Wrapper },
    );
    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    const es = MockEventSource.instances[0];

    act(() =>
      es.emit(makeEvent({
        type: "agent.action_executed",
        data: { session_id: "other-session" },
      })),
    );
    expect(result.current.processedCount).toBe(0);
  });

  it("does not re-process duplicate event IDs", async () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useAgentEvents(SESSION_ID, SCAN_RUN_ID, false),
      { wrapper: Wrapper },
    );
    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    const es = MockEventSource.instances[0];
    const evt = agentEvent("agent.action_executed");

    act(() => es.emit(evt));
    act(() => es.emit(evt));

    expect(result.current.processedCount).toBe(1);
  });

  it("updates budget overlay from event budget_snapshot", async () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useAgentEvents(SESSION_ID, SCAN_RUN_ID, false),
      { wrapper: Wrapper },
    );
    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    const es = MockEventSource.instances[0];

    act(() =>
      es.emit(agentEvent("agent.action_executed", {
        budget_snapshot: { turns: 5, mission: { turns: 5 } },
      })),
    );
    expect(result.current.budgetOverlay?.mission?.turns).toBe(5);
  });

  it("clears budget overlay when sessionId is undefined", () => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useAgentEvents(undefined, undefined, false),
      { wrapper: Wrapper },
    );
    expect(result.current.budgetOverlay).toBeNull();
  });

  it("does not open SSE when isTerminal is true", () => {
    const { Wrapper } = makeRenderHookWrapper();
    renderHook(
      () => useAgentEvents(SESSION_ID, SCAN_RUN_ID, true),
      { wrapper: Wrapper },
    );
    expect(MockEventSource.instances).toHaveLength(0);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/features/missions/useAgentEvents.test.tsx`
Expected: FAIL — `useAgentEvents` not found.

- [ ] **Step 3: Implement useAgentEvents**

Create `frontend/src/features/missions/useAgentEvents.ts`:

```typescript
import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useScanRunEvents } from "../scan-runs/useScanRunEvents";
import type { Event as ApiEvent } from "../../types/api";
import type { AgentEventData, BudgetSnapshot } from "./types";
import { missionKey, missionTurnsKey, missionNotesKey } from "./api";

function isAgentEvent(event: ApiEvent, sessionId: string): boolean {
  if (!event.type.startsWith("agent.")) return false;
  const data = event.data as Partial<AgentEventData> | undefined;
  return data?.session_id === sessionId;
}

const SESSION_EVENTS = new Set([
  "agent.session_started",
  "agent.phase_changed",
  "agent.mission_finished",
]);
const TURNS_EVENTS = new Set([
  "agent.action_executed",
  "agent.action_denied",
]);
const NOTES_EVENTS = new Set(["agent.note_created"]);

export type UseAgentEventsResult = {
  budgetOverlay: BudgetSnapshot | null;
  processedCount: number;
};

export function useAgentEvents(
  sessionId: string | undefined,
  scanRunId: string | undefined,
  isTerminal: boolean,
): UseAgentEventsResult {
  const client = useQueryClient();
  const processedRef = useRef(new Set<string>());
  const [budgetOverlay, setBudgetOverlay] = useState<BudgetSnapshot | null>(null);
  const [processedCount, setProcessedCount] = useState(0);

  const livePolling = Boolean(sessionId && scanRunId && !isTerminal);
  const { events } = useScanRunEvents(
    livePolling ? scanRunId : undefined,
    { livePolling },
  );

  useEffect(() => {
    processedRef.current = new Set<string>();
    setBudgetOverlay(null);
    setProcessedCount(0);
  }, [sessionId]);

  const processEvents = useCallback(
    (allEvents: ApiEvent[]) => {
      if (!sessionId) return;
      let newCount = 0;
      for (const evt of allEvents) {
        if (processedRef.current.has(evt.id)) continue;
        if (!isAgentEvent(evt, sessionId)) continue;
        processedRef.current.add(evt.id);
        newCount++;

        if (SESSION_EVENTS.has(evt.type)) {
          void client.invalidateQueries({ queryKey: missionKey(sessionId) });
        }
        if (TURNS_EVENTS.has(evt.type)) {
          void client.invalidateQueries({ queryKey: missionTurnsKey(sessionId) });
        }
        if (NOTES_EVENTS.has(evt.type)) {
          void client.invalidateQueries({ queryKey: missionNotesKey(sessionId) });
        }

        const data = evt.data as Partial<AgentEventData> | undefined;
        if (data?.budget_snapshot) {
          setBudgetOverlay(data.budget_snapshot);
        }
      }
      if (newCount > 0) {
        setProcessedCount((c) => c + newCount);
      }
    },
    [sessionId, client],
  );

  useEffect(() => {
    processEvents(events);
  }, [events, processEvents]);

  return { budgetOverlay, processedCount };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/features/missions/useAgentEvents.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/missions/useAgentEvents.ts frontend/src/features/missions/useAgentEvents.test.tsx
git commit -m "feat(frontend): useAgentEvents — SSE filter, invalidation, budget overlay"
```
