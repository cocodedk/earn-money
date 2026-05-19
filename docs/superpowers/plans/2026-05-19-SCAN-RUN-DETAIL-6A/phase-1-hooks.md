# Phase 1 — Hooks

Add `useScanRunQuery(id)` and lift `useScanRunActions(run)` from `ScanRunsList`'s inline `ActionButtons` so both ScanRunsList rows and the new detail page consume the same shape.

---

### Task A: `useScanRunQuery(id)` + `useScanRunActions(run)`

**Files:**
- Modify: `frontend/src/features/scan-runs/api.ts`
- Modify: `frontend/src/features/scan-runs/api.test.tsx`
- Create: `frontend/src/features/scan-runs/useScanRunActions.ts`
- Create: `frontend/src/features/scan-runs/useScanRunActions.test.tsx`
- Modify: `frontend/src/features/scan-runs/ScanRunsList.tsx` — consume the lifted hook

- [ ] **Step 1: Add `useScanRunQuery(id)` to `api.ts`**

```ts
export function useScanRunQuery(id: string | undefined) {
  return useQuery({
    queryKey: [...SCAN_RUNS_KEY, id ?? ""],
    queryFn: () => http<ScanRun>(`/api/scan-runs/${id}/`),
    enabled: Boolean(id),
  });
}
```

Add a per-id query-key helper next to the existing exports if useful (analogous to `stubKey(slug)`).

- [ ] **Step 2: Add tests for the new query**

```tsx
describe("useScanRunQuery", () => {
  it("fetches one scan run by id", async () => {
    server.use(
      msw.get("/api/scan-runs/r-1/", () => HttpResponse.json(makeScanRun())),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useScanRunQuery("r-1"), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.data?.id).toBe("r-1"));
  });

  it("is disabled when id is undefined — no network call", async () => {
    let calls = 0;
    server.use(
      msw.get("/api/scan-runs/:id/", () => {
        calls += 1;
        return HttpResponse.json(makeScanRun());
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useScanRunQuery(undefined), {
      wrapper: Wrapper,
    });
    expect(result.current.isLoading).toBe(false);
    expect(calls).toBe(0);
  });
});
```

- [ ] **Step 3: Create `useScanRunActions.ts`**

```ts
import { useMutation } from "@tanstack/react-query";
import {
  usePauseScanRunMutation,
  useResumeScanRunMutation,
  useStartScanRunMutation,
  useStopScanRunMutation,
} from "./api";
import type { LifecycleAction, ScanRun, ScanRunStatus } from "../../types/api";

export const VALID_ACTIONS: Record<ScanRunStatus, readonly LifecycleAction[]> = {
  queued: ["start"],
  running: ["pause", "stop"],
  paused: ["resume", "stop"],
  stopping: [],
  stopped: [],
  failed: [],
  done: [],
};

export const ACTION_LABEL: Record<LifecycleAction, string> = {
  start: "Start",
  pause: "Pause",
  resume: "Resume",
  stop: "Stop",
};

export type ScanRunActions = {
  visibleActions: readonly LifecycleAction[];
  handlers: Record<LifecycleAction, () => void>;
  isPending: boolean;
};

export function useScanRunActions(run: ScanRun): ScanRunActions {
  const start = useStartScanRunMutation();
  const pause = usePauseScanRunMutation();
  const resume = useResumeScanRunMutation();
  const stop = useStopScanRunMutation();
  return {
    visibleActions: VALID_ACTIONS[run.status],
    handlers: {
      start: () => start.mutate(run.id),
      pause: () => pause.mutate(run.id),
      resume: () => resume.mutate(run.id),
      stop: () => stop.mutate(run.id),
    },
    isPending:
      start.isPending || pause.isPending || resume.isPending || stop.isPending,
  };
}
```

The `useMutation` import is unused but TS will flag it; drop it before commit.

- [ ] **Step 4: Test useScanRunActions per-status**

`useScanRunActions.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import { makeScanRun } from "./__fixtures__/scan-run";
import { useScanRunActions, VALID_ACTIONS } from "./useScanRunActions";
import type { ScanRunStatus } from "../../types/api";

const STATUSES: ScanRunStatus[] = [
  "queued", "running", "paused", "stopping", "stopped", "failed", "done",
];

describe("useScanRunActions", () => {
  it.each(STATUSES)("returns the correct visible actions for %s", (status) => {
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useScanRunActions(makeScanRun({ status })),
      { wrapper: Wrapper },
    );
    expect(result.current.visibleActions).toEqual(VALID_ACTIONS[status]);
  });

  it.each([
    ["start", "/api/scan-runs/r-1/start/"],
    ["pause", "/api/scan-runs/r-1/pause/"],
    ["resume", "/api/scan-runs/r-1/resume/"],
    ["stop", "/api/scan-runs/r-1/stop/"],
  ] as const)("handlers.%s POSTs to %s", async (action, path) => {
    let hit = false;
    server.use(
      msw.post(path, () => {
        hit = true;
        return HttpResponse.json(makeScanRun({ status: "running" }));
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useScanRunActions(makeScanRun()),
      { wrapper: Wrapper },
    );
    await act(async () => {
      result.current.handlers[action]();
      // wait one tick for the mutation to fire
      await new Promise((r) => setTimeout(r, 0));
    });
    // mutation is fire-and-forget here; polling is fine for the test
    await new Promise((r) => setTimeout(r, 20));
    expect(hit).toBe(true);
  });
});
```

- [ ] **Step 5: Refactor `ScanRunsList.tsx` — `ActionButtons` consumes the hook**

Replace the inline `VALID_ACTIONS` / `ACTION_LABEL` / four `useXxxScanRunMutation()` calls with `const actions = useScanRunActions(run);`. Render the same `<Open> + visible buttons` shape.

- [ ] **Step 6: Coverage + commit**

```bash
cd frontend && npm test -- --coverage
git add frontend/src/features/scan-runs/api.ts frontend/src/features/scan-runs/api.test.tsx frontend/src/features/scan-runs/useScanRunActions.ts frontend/src/features/scan-runs/useScanRunActions.test.tsx frontend/src/features/scan-runs/ScanRunsList.tsx
git commit -m "feat(frontend): lift useScanRunActions hook + useScanRunQuery"
```
