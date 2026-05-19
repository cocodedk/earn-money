# Phase 1 — Hooks

Add the `ScanTargetRun` type, extend `useScanRunQuery` with internal self-polling, add `useScanRunTargetRunsQuery` + terminal flush, and MSW handlers for the new endpoint. All four hook-level test branches (cascade, no-in-flight flush, in-flight flush with cached data, no-cached-data in-flight) land here.

---

### Task A: Add `ScanTargetRun` type

**Files:**
- Modify: `frontend/src/types/api.ts`

- [ ] **Step 1: Add the type**

```ts
export type ScanTargetRun = {
  id: Uuid;
  target: Uuid;
  target_base_url: string;
  target_host: string;
  status: ScanRunStatus;
  started_at: Iso8601 | null;
  finished_at: Iso8601 | null;
  updated_at: Iso8601;
  findings_count: number;
  evidence_count: number;
  created_at: Iso8601;
};
```

Place it alongside `ScanRun` so the file stays organised. `ScanRunStatus` is the shared enum (see existing exports near line 4) — future per-target states extend, not fork.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/types/api.ts
git commit -m "feat(frontend): add ScanTargetRun type for 6B target-runs table"
```

---

### Task B: Extend `useScanRunQuery` with internal `refetchInterval` callback (self-polling)

**Files:**
- Modify: `frontend/src/features/scan-runs/api.ts`
- Modify: `frontend/src/features/scan-runs/api.test.tsx`

- [ ] **Step 1: Write failing tests for parent self-polling**

Append to `api.test.tsx` (if the file approaches 200 lines, move the new tests to a new `api.scan-run-polling.test.tsx`):

```tsx
describe("useScanRunQuery self-polling", () => {
  it.each(["running", "stopping"] as const)(
    "polls every 2s while status is %s",
    async (status) => {
      vi.useFakeTimers();
      let calls = 0;
      server.use(
        msw.get("/api/scan-runs/r-1/", () => {
          calls += 1;
          return HttpResponse.json(makeScanRun({ id: "r-1", status }));
        }),
      );
      const { Wrapper } = makeRenderHookWrapper();
      renderHook(() => useScanRunQuery("r-1"), { wrapper: Wrapper });
      await vi.advanceTimersByTimeAsync(2500);
      expect(calls).toBeGreaterThanOrEqual(2);
      vi.useRealTimers();
    },
  );

  it.each(["queued", "paused", "done", "failed", "stopped"] as const)(
    "does NOT poll when status is %s",
    async (status) => {
      vi.useFakeTimers();
      let calls = 0;
      server.use(
        msw.get("/api/scan-runs/r-1/", () => {
          calls += 1;
          return HttpResponse.json(makeScanRun({ id: "r-1", status }));
        }),
      );
      const { Wrapper } = makeRenderHookWrapper();
      renderHook(() => useScanRunQuery("r-1"), { wrapper: Wrapper });
      await vi.advanceTimersByTimeAsync(2500);
      expect(calls).toBe(1);
      vi.useRealTimers();
    },
  );

  it("stops polling on running → done transition", async () => {
    vi.useFakeTimers();
    let calls = 0;
    let status: ScanRunStatus = "running";
    server.use(
      msw.get("/api/scan-runs/r-1/", () => {
        calls += 1;
        return HttpResponse.json(makeScanRun({ id: "r-1", status }));
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    renderHook(() => useScanRunQuery("r-1"), { wrapper: Wrapper });
    await vi.advanceTimersByTimeAsync(2500); // poll fires while running
    status = "done";
    await vi.advanceTimersByTimeAsync(2500); // catches done
    const afterDone = calls;
    await vi.advanceTimersByTimeAsync(5000); // no more polls
    expect(calls).toBe(afterDone);
    vi.useRealTimers();
  });
});
```

- [ ] **Step 2: Run tests — must fail**

```bash
cd frontend && npm test -- src/features/scan-runs/api.test.tsx -t "useScanRunQuery self-polling"
```

Expected: FAIL — no `refetchInterval` callback yet, polling doesn't fire.

- [ ] **Step 3: Add the internal refetchInterval callback**

Replace the existing `useScanRunQuery` body in `api.ts`:

```ts
export function useScanRunQuery(id: string | undefined) {
  return useQuery({
    queryKey: scanRunKey(id ?? ""),
    queryFn: () => http<ScanRun>(`/api/scan-runs/${id}/`),
    enabled: Boolean(id),
    refetchInterval: (q) => {
      const status = q.state.data?.status;
      return status === "running" || status === "stopping" ? 2000 : false;
    },
  });
}
```

The callback reads its own query state — no caller-provided option, no circular dep on `run.status` before the hook fetches it.

- [ ] **Step 4: Run tests — must pass**

```bash
cd frontend && npm test -- src/features/scan-runs/api.test.tsx
```

Expected: PASS, including pre-existing tests untouched.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/scan-runs/api.ts frontend/src/features/scan-runs/api.test.tsx
git commit -m "feat(frontend): useScanRunQuery self-polls while running/stopping"
```

---

### Task C: Add `useScanRunTargetRunsQuery` + `scanRunTargetRunsKey` + terminal flush

**Files:**
- Modify: `frontend/src/features/scan-runs/api.ts`
- Create: `frontend/src/features/scan-runs/api.target-runs.test.tsx`

- [ ] **Step 1: Write failing tests in `api.target-runs.test.tsx`**

```tsx
import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { http as msw, HttpResponse, delay } from "msw";
import { server } from "../../test/server";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import { makeScanTargetRun } from "./__fixtures__/scan-target-run";
import {
  SCAN_RUNS_KEY,
  scanRunTargetRunsKey,
  useScanRunTargetRunsQuery,
} from "./api";

describe("useScanRunTargetRunsQuery", () => {
  it("fetches page 1 by scan run id", async () => {
    server.use(
      msw.get("/api/scan-runs/r-1/target-runs/", () =>
        HttpResponse.json({
          count: 1, next: null, previous: null,
          results: [makeScanTargetRun({ id: "tr-1" })],
        }),
      ),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(
      () => useScanRunTargetRunsQuery("r-1"),
      { wrapper: Wrapper },
    );
    await waitFor(() => expect(result.current.data?.count).toBe(1));
  });

  it("is disabled when scanRunId is undefined — no network call", async () => {
    let calls = 0;
    server.use(
      msw.get("/api/scan-runs/:id/target-runs/", () => {
        calls += 1;
        return HttpResponse.json({ count: 0, next: null, previous: null, results: [] });
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    renderHook(() => useScanRunTargetRunsQuery(undefined), { wrapper: Wrapper });
    await new Promise((r) => setTimeout(r, 20));
    expect(calls).toBe(0);
  });

  it("polls every 2s with livePolling: true", async () => {
    vi.useFakeTimers();
    let calls = 0;
    server.use(
      msw.get("/api/scan-runs/r-1/target-runs/", () => {
        calls += 1;
        return HttpResponse.json({ count: 0, next: null, previous: null, results: [] });
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    renderHook(
      () => useScanRunTargetRunsQuery("r-1", { livePolling: true }),
      { wrapper: Wrapper },
    );
    await vi.advanceTimersByTimeAsync(2500);
    expect(calls).toBeGreaterThanOrEqual(2);
    vi.useRealTimers();
  });

  it("does NOT poll with livePolling: false", async () => {
    vi.useFakeTimers();
    let calls = 0;
    server.use(
      msw.get("/api/scan-runs/r-1/target-runs/", () => {
        calls += 1;
        return HttpResponse.json({ count: 0, next: null, previous: null, results: [] });
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    renderHook(
      () => useScanRunTargetRunsQuery("r-1", { livePolling: false }),
      { wrapper: Wrapper },
    );
    await vi.advanceTimersByTimeAsync(2500);
    expect(calls).toBe(1);
    vi.useRealTimers();
  });

  it("terminal flush — no-in-flight branch: cache ends with fresh post-flush rows", async () => {
    vi.useFakeTimers();
    let phase: "pre" | "post" = "pre";
    server.use(
      msw.get("/api/scan-runs/r-1/target-runs/", () =>
        HttpResponse.json({
          count: 1, next: null, previous: null,
          results: [makeScanTargetRun({ id: "tr-1", status: phase === "pre" ? "running" : "done" })],
        }),
      ),
    );
    const { Wrapper, client } = makeRenderHookWrapper();
    const { rerender, result } = renderHook(
      ({ live }: { live: boolean }) =>
        useScanRunTargetRunsQuery("r-1", { livePolling: live }),
      { wrapper: Wrapper, initialProps: { live: true } },
    );
    await vi.advanceTimersByTimeAsync(2500); // poll settles with "running"
    phase = "post";
    rerender({ live: false }); // terminal flush fires
    await vi.advanceTimersByTimeAsync(50);
    await waitFor(() =>
      expect(result.current.data?.results[0].status).toBe("done"),
    );
    vi.useRealTimers();
  });

  it("terminal flush — in-flight with cached data: cache ends fresh", async () => {
    vi.useFakeTimers();
    let phase: "pre" | "post" = "pre";
    server.use(
      msw.get("/api/scan-runs/r-1/target-runs/", async () => {
        if (phase === "pre") {
          return HttpResponse.json({
            count: 1, next: null, previous: null,
            results: [makeScanTargetRun({ id: "tr-1", status: "running" })],
          });
        }
        await delay(200); // simulate in-flight
        return HttpResponse.json({
          count: 1, next: null, previous: null,
          results: [makeScanTargetRun({ id: "tr-1", status: "done" })],
        });
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { rerender, result } = renderHook(
      ({ live }: { live: boolean }) =>
        useScanRunTargetRunsQuery("r-1", { livePolling: live }),
      { wrapper: Wrapper, initialProps: { live: true } },
    );
    await vi.advanceTimersByTimeAsync(2500); // cached
    phase = "post";
    await vi.advanceTimersByTimeAsync(2000); // next poll fires (in-flight)
    rerender({ live: false }); // flush during in-flight
    await vi.advanceTimersByTimeAsync(500);
    await waitFor(() =>
      expect(result.current.data?.results[0].status).toBe("done"),
    );
    vi.useRealTimers();
  });

  it("terminal flush — no-cached-data in-flight: cache ends fresh (round-5 edge case)", async () => {
    vi.useFakeTimers();
    let phase: "pre" | "post" = "pre";
    server.use(
      msw.get("/api/scan-runs/r-1/target-runs/", async () => {
        if (phase === "pre") {
          await delay(500); // initial fetch still pending
          return HttpResponse.json({
            count: 1, next: null, previous: null,
            results: [makeScanTargetRun({ id: "tr-1", status: "running" })],
          });
        }
        return HttpResponse.json({
          count: 1, next: null, previous: null,
          results: [makeScanTargetRun({ id: "tr-1", status: "done" })],
        });
      }),
    );
    const { Wrapper } = makeRenderHookWrapper();
    const { rerender, result } = renderHook(
      ({ live }: { live: boolean }) =>
        useScanRunTargetRunsQuery("r-1", { livePolling: live }),
      { wrapper: Wrapper, initialProps: { live: true } },
    );
    await vi.advanceTimersByTimeAsync(100); // initial fetch in flight, no cached data
    phase = "post";
    rerender({ live: false }); // terminal flush during initial-fetch in-flight
    await vi.advanceTimersByTimeAsync(500);
    await waitFor(() =>
      expect(result.current.data?.results[0].status).toBe("done"),
    );
    vi.useRealTimers();
  });

  it("cascade refetch from SCAN_RUNS_KEY (paused parent, no polling)", async () => {
    let calls = 0;
    server.use(
      msw.get("/api/scan-runs/r-1/target-runs/", () => {
        calls += 1;
        return HttpResponse.json({ count: 0, next: null, previous: null, results: [] });
      }),
    );
    const { Wrapper, client } = makeRenderHookWrapper();
    renderHook(
      () => useScanRunTargetRunsQuery("r-1", { livePolling: false }),
      { wrapper: Wrapper },
    );
    await new Promise((r) => setTimeout(r, 20)); // initial fetch
    const before = calls;
    await client.invalidateQueries({ queryKey: SCAN_RUNS_KEY });
    await new Promise((r) => setTimeout(r, 20));
    expect(calls).toBe(before + 1);
  });
});
```

Also add a `makeScanTargetRun` fixture at `frontend/src/features/scan-runs/__fixtures__/scan-target-run.ts`:

```ts
import type { ScanTargetRun } from "../../../types/api";

export function makeScanTargetRun(over: Partial<ScanTargetRun> = {}): ScanTargetRun {
  return {
    id: "tr-1",
    target: "t-1",
    target_base_url: "https://example.test",
    target_host: "example.test",
    status: "queued",
    started_at: null,
    finished_at: null,
    updated_at: "2026-05-19T00:00:00Z",
    findings_count: 0,
    evidence_count: 0,
    created_at: "2026-05-19T00:00:00Z",
    ...over,
  };
}
```

- [ ] **Step 2: Run tests — must fail**

```bash
cd frontend && npm test -- src/features/scan-runs/api.target-runs.test.tsx
```

Expected: FAIL — `useScanRunTargetRunsQuery` / `scanRunTargetRunsKey` not exported.

- [ ] **Step 3: Implement hook in `api.ts`**

Append to `api.ts` (keep file under 200 lines; if it exceeds, split into `api.target-runs.ts` and re-export):

```ts
import { useEffect, useRef } from "react";
import type { ScanTargetRun } from "../../types/api";

export const scanRunTargetRunsKey = (id: string) =>
  [...SCAN_RUNS_KEY, id, "target-runs"] as const;

type TargetRunsOptions = { livePolling?: boolean };

export function useScanRunTargetRunsQuery(
  scanRunId: string | undefined,
  options?: TargetRunsOptions,
) {
  const client = useQueryClient();
  const livePolling = Boolean(options?.livePolling);
  const prev = useRef(livePolling);

  useEffect(() => {
    if (prev.current === true && livePolling === false && scanRunId) {
      const key = scanRunTargetRunsKey(scanRunId);
      void (async () => {
        await client.cancelQueries({ queryKey: key });
        await client.refetchQueries({ queryKey: key, type: "active" });
      })();
    }
    prev.current = livePolling;
  }, [livePolling, scanRunId, client]);

  return useQuery({
    queryKey: scanRunTargetRunsKey(scanRunId ?? ""),
    queryFn: () =>
      http<Paginated<ScanTargetRun>>(`/api/scan-runs/${scanRunId}/target-runs/`),
    enabled: Boolean(scanRunId),
    refetchInterval: livePolling ? 2000 : false,
  });
}
```

- [ ] **Step 4: Run tests — must pass**

```bash
cd frontend && npm test -- src/features/scan-runs/api.target-runs.test.tsx
```

Expected: PASS, all 8 branches green.

- [ ] **Step 5: Coverage check + commit**

```bash
cd frontend && npm test -- --coverage src/features/scan-runs/api.ts src/features/scan-runs/api.target-runs.test.tsx
git add frontend/src/features/scan-runs/api.ts frontend/src/features/scan-runs/api.target-runs.test.tsx frontend/src/features/scan-runs/__fixtures__/scan-target-run.ts
git commit -m "feat(frontend): useScanRunTargetRunsQuery with terminal flush"
```

Then run `/simplify` on the commit (per-commit gate) and iterate to clean.

---

### Task D: MSW default handler for `/api/scan-runs/:id/target-runs/`

**Files:**
- Modify: `frontend/src/test/handlers.ts` (or the existing handlers file — `git grep -l "scan-runs" frontend/src/test`)

- [ ] **Step 1: Add the default handler**

```ts
import { makeScanTargetRun } from "../features/scan-runs/__fixtures__/scan-target-run";

http.get("/api/scan-runs/:id/target-runs/", () =>
  HttpResponse.json({
    count: 1, next: null, previous: null,
    results: [makeScanTargetRun()],
  }),
),
```

Place alongside the existing `/api/scan-runs/:id/` handler so per-test overrides via `server.use(...)` work uniformly.

- [ ] **Step 2: Run full suite — no regressions**

```bash
cd frontend && npm test
```

Expected: PASS for all existing tests.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/test/handlers.ts
git commit -m "test(frontend): default MSW handler for /api/scan-runs/:id/target-runs/"
```

---

### Phase 1 done

Hooks + types + MSW handlers in place. Parent self-polling, child polling, and terminal flush all locked by hook-level tests. Next: phase 2 — table component + DetailPageGuard narrowing.
