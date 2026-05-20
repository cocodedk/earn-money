# Phase 2 — API client + lifecycle hooks + fixture

### Task B: Hooks + factory

**Files:**
- Create: `frontend/src/features/scan-runs/api.ts`
- Create: `frontend/src/features/scan-runs/api.test.tsx`
- Create: `frontend/src/features/scan-runs/__fixtures__/scan-run.ts`

- [ ] **Step 1: Fixture factory**

`frontend/src/features/scan-runs/__fixtures__/scan-run.ts`:

```ts
import type { ScanRun } from "../../../types/api";

const BASE: ScanRun = {
  id: "r-1",
  project: "p-1",
  stub_slug: "1.1",
  status: "queued",
  started_at: null,
  finished_at: null,
  target_run_count: 1,
  findings_count: 0,
  created_at: "2026-05-19T08:00:00.000000Z",
  updated_at: "2026-05-19T08:00:00.000000Z",
};

export function makeScanRun(overrides: Partial<ScanRun> = {}): ScanRun {
  return { ...BASE, ...overrides };
}
```

- [ ] **Step 2: Failing test — `api.test.tsx`**

```tsx
import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { withPaginated } from "../../test/helpers";
import { makeRenderHookWrapper } from "../../test/renderWithProviders";
import { makeScanRun } from "./__fixtures__/scan-run";
import {
  SCAN_RUNS_KEY,
  useCreateScanRunMutation,
  usePauseScanRunMutation,
  useResumeScanRunMutation,
  useScanRunsQuery,
  useStartScanRunMutation,
  useStopScanRunMutation,
} from "./api";

describe("useScanRunsQuery", () => {
  it("fetches the paginated list", async () => {
    withPaginated("/api/scan-runs/", [makeScanRun()]);
    const { Wrapper } = makeRenderHookWrapper();
    const { result } = renderHook(() => useScanRunsQuery(), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.data?.count).toBe(1));
    expect(result.current.data?.results[0].stub_slug).toBe("1.1");
  });
});

describe("useCreateScanRunMutation", () => {
  it("POSTs the body and invalidates SCAN_RUNS_KEY", async () => {
    let received: unknown = null;
    server.use(
      msw.post("/api/scan-runs/", async ({ request }) => {
        received = await request.json();
        return HttpResponse.json(makeScanRun(), { status: 201 });
      }),
    );
    const { client, Wrapper } = makeRenderHookWrapper();
    const spy = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useCreateScanRunMutation(), { wrapper: Wrapper });
    await act(async () => {
      await result.current.mutateAsync({
        project: "p-1",
        stub_slug: "1.1",
        target_ids: ["t-1"],
      });
    });
    expect(received).toEqual({ project: "p-1", stub_slug: "1.1", target_ids: ["t-1"] });
    expect(spy).toHaveBeenCalledWith({ queryKey: SCAN_RUNS_KEY });
  });
});

describe("lifecycle mutations", () => {
  const cases = [
    { name: "start", hook: useStartScanRunMutation, path: "/api/scan-runs/r-1/start/" },
    { name: "pause", hook: usePauseScanRunMutation, path: "/api/scan-runs/r-1/pause/" },
    { name: "resume", hook: useResumeScanRunMutation, path: "/api/scan-runs/r-1/resume/" },
    { name: "stop", hook: useStopScanRunMutation, path: "/api/scan-runs/r-1/stop/" },
  ] as const;

  it.each(cases)("$name POSTs the right URL and invalidates the cache", async ({ hook, path }) => {
    let hit = false;
    server.use(
      msw.post(path, () => {
        hit = true;
        return HttpResponse.json(makeScanRun({ status: "running" }));
      }),
    );
    const { client, Wrapper } = makeRenderHookWrapper();
    const spy = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => hook(), { wrapper: Wrapper });
    await act(async () => {
      await result.current.mutateAsync("r-1");
    });
    expect(hit).toBe(true);
    expect(spy).toHaveBeenCalledWith({ queryKey: SCAN_RUNS_KEY });
  });
});
```

- [ ] **Step 3: Run test — must fail**

```bash
cd frontend && npm test -- src/features/scan-runs/api
```

- [ ] **Step 4: Implement `api.ts`**

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../../lib/http";
import type {
  CreateScanRunBody,
  LifecycleAction,
  Paginated,
  ScanRun,
  Uuid,
} from "../../types/api";

export const SCAN_RUNS_KEY = ["scan-runs"] as const;

export function useScanRunsQuery() {
  return useQuery({
    queryKey: SCAN_RUNS_KEY,
    queryFn: () => http<Paginated<ScanRun>>("/api/scan-runs/"),
  });
}

export function useCreateScanRunMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateScanRunBody) =>
      http<ScanRun>("/api/scan-runs/", { method: "POST", body }),
    onSuccess: () => void client.invalidateQueries({ queryKey: SCAN_RUNS_KEY }),
  });
}

function makeLifecycleHook(action: LifecycleAction) {
  return function useLifecycleMutation() {
    const client = useQueryClient();
    return useMutation({
      mutationFn: (id: Uuid) =>
        http<ScanRun>(`/api/scan-runs/${id}/${action}/`, { method: "POST" }),
      onSuccess: () => void client.invalidateQueries({ queryKey: SCAN_RUNS_KEY }),
    });
  };
}

export const useStartScanRunMutation = makeLifecycleHook("start");
export const usePauseScanRunMutation = makeLifecycleHook("pause");
export const useResumeScanRunMutation = makeLifecycleHook("resume");
export const useStopScanRunMutation = makeLifecycleHook("stop");
```

- [ ] **Step 5: Run + coverage 100%**

```bash
cd frontend && npm test -- src/features/scan-runs/api --coverage
```

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(frontend): add Scan Runs API hooks + lifecycle mutations"
```
