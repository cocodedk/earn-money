---
tier: CAPABLE
depends_on: [04-api-hooks]
files:
  creates: [frontend/src/features/missions/useAgentEvents.ts, frontend/src/features/missions/useAgentEvents.test.tsx]
  modifies: []
exports:
  - name: useAgentEvents
    file: frontend/src/features/missions/useAgentEvents.ts
allow_extra_files: false
---

# Task 9: useAgentEvents Hook

**Goal:** SSE wrapper that filters agent events by session, invalidates queries, and manages the optimistic budget overlay.

**Depends on:** [Task 4](04-api-hooks.md)

**Files:**
- Create: `frontend/src/features/missions/useAgentEvents.ts`
- Create: `frontend/src/features/missions/useAgentEvents.test.tsx`

Tests: see [09-use-agent-events-tests.md](09-use-agent-events-tests.md)

- [ ] **Step 1: Write failing tests** — see test file above.

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
  "agent.session_updated",
  "agent.phase_changed",
  "agent.budget_updated",
  "agent.mission_finished",
  "agent.session_failed",
  "agent.session_stopped",
]);
const TURNS_EVENTS = new Set([
  "agent.turn_started",
  "agent.action_proposed",
  "agent.action_executed",
  "agent.action_denied",
  "agent.turn_completed",
  "agent.turn_error",
  "agent.observation_created",
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
          void client.invalidateQueries({
            queryKey: missionTurnsKey(sessionId),
          });
        }
        if (NOTES_EVENTS.has(evt.type)) {
          void client.invalidateQueries({
            queryKey: missionNotesKey(sessionId),
          });
        }
        const data = evt.data as Partial<AgentEventData> | undefined;
        if (data?.budget_snapshot) {
          setBudgetOverlay(data.budget_snapshot);
        }
      }
      if (newCount > 0) setProcessedCount((c) => c + newCount);
    },
    [sessionId, client],
  );

  useEffect(() => {
    processEvents(events);
  }, [events, processEvents]);

  return { budgetOverlay, processedCount };
}
```

- [ ] **Step 4: Run tests** — `cd frontend && npx vitest run src/features/missions/useAgentEvents.test.tsx` → PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/missions/useAgentEvents.ts frontend/src/features/missions/useAgentEvents.test.tsx
git commit -m "feat(frontend): useAgentEvents — SSE filter, invalidation, budget overlay"
```
