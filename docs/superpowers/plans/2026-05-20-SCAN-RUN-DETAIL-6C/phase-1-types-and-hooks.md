# Phase 1 — Types and hooks

**Goal:** Add the `Finding` / `Evidence` / `Confidence` / `FindingStatus` types and the two scan-run-scoped query hooks with self-polling + terminal flush, plus default MSW handlers. No UI yet.

**Reference patterns:** Mirror 6B exactly — `useScanRunTargetRunsQuery` (api.ts:71–97) is the template for both new hooks. `scanRunTargetRunsKey` (api.ts:66–67) is the template for the new keys. Default MSW handler for `/api/scan-runs/:id/target-runs/` (`frontend/src/test/handlers.ts`) is the template for the new handlers.

---

### Task 1: Add Finding and Evidence types

**Files:**
- Modify: `frontend/src/types/api.ts` (currently 116 lines; new types push to ~150)
- Test: none (pure type declarations have no runtime behaviour to test; coverage tooling does not measure `.d.ts`-equivalent constructs)

- [ ] **Step 1: Append exact type declarations** (after `LifecycleAction` on line 115)

```ts
export type Confidence = "low" | "medium" | "high";

export type FindingStatus = "candidate" | "confirmed" | "rejected" | "stale";

export type Finding = {
  id: Uuid;
  scan_run: Uuid;
  target: Uuid;
  stub_slug: string;
  title: string;
  category: string;
  severity: Severity;
  confidence: Confidence;
  status: FindingStatus;
  data: Record<string, unknown>;
  created_at: Iso8601;
  updated_at: Iso8601;
};

export type Evidence = {
  id: Uuid;
  scan_run: Uuid;
  target: Uuid;
  finding: Uuid | null;
  source: string;
  url: string | null;
  method: string | null;
  field: string | null;
  matched_value: string | null;
  raw_excerpt: string | null;
  content_hash: string;
  data: Record<string, unknown>;
  created_at: Iso8601;
};
```

These shapes are copied verbatim from `origin/feat/em-frontend-slice-3:frontend/src/types/api.ts` and verified against the live backend serializers in `backend/apps/findings/serializers.py` and `backend/apps/evidence/serializers.py`.

- [ ] **Step 2: Verify build**

Run: `npm run -C frontend typecheck` (or `npm run -C frontend build`)
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/api.ts
git commit -m "feat(frontend): add Finding/Evidence/Confidence/FindingStatus types for 6C"
```

---

### Task 2: Add fixture factories

**Files:**
- Create: `frontend/src/features/scan-runs/__fixtures__/finding.ts`
- Create: `frontend/src/features/scan-runs/__fixtures__/evidence.ts`

These are test-only helpers — no production code, no test file of their own (they're tested transitively by every test that uses them).

- [ ] **Step 1: Write `__fixtures__/finding.ts`** (~15 lines)

```ts
import type { Finding } from "../../../types/api";

export function makeFinding(over: Partial<Finding> = {}): Finding {
  return {
    id: "f1111111-1111-1111-1111-111111111111",
    scan_run: "s1111111-1111-1111-1111-111111111111",
    target: "t1111111-1111-1111-1111-111111111111",
    stub_slug: "1.1-headers",
    title: "Missing security header",
    category: "headers",
    severity: "low",
    confidence: "medium",
    status: "candidate",
    data: {},
    created_at: "2026-05-20T08:00:00Z",
    updated_at: "2026-05-20T08:00:00Z",
    ...over,
  };
}
```

- [ ] **Step 2: Write `__fixtures__/evidence.ts`** (~18 lines)

```ts
import type { Evidence } from "../../../types/api";

export function makeEvidence(over: Partial<Evidence> = {}): Evidence {
  return {
    id: "e1111111-1111-1111-1111-111111111111",
    scan_run: "s1111111-1111-1111-1111-111111111111",
    target: "t1111111-1111-1111-1111-111111111111",
    finding: null,
    source: "http-headers",
    url: "https://target.cocode.dk/",
    method: "GET",
    field: "X-Frame-Options",
    matched_value: "ALLOWALL",
    raw_excerpt: null,
    content_hash: "abc123",
    data: {},
    created_at: "2026-05-20T08:00:00Z",
    ...over,
  };
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/scan-runs/__fixtures__/finding.ts frontend/src/features/scan-runs/__fixtures__/evidence.ts
git commit -m "test(frontend): add Finding + Evidence fixture factories"
```

---

### Task 3: Default MSW handlers

**Files:**
- Modify: `frontend/src/test/handlers.ts`
- Test: no dedicated test — handlers are exercised by every component test

The 6B handler for `/api/scan-runs/:id/target-runs/` is the template. We add two new handlers that return empty paginated lists by default; individual tests override with `server.use(...)`.

- [ ] **Step 1: Add the two handlers** (append before the closing `]`)

```ts
http.get("/api/findings/", () =>
  HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
),
http.get("/api/evidence/", () =>
  HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
),
```

These match exactly because both new queries hit collection endpoints with a `?scan_run=<uuid>` query string — MSW matches on path, ignores query params unless we explicitly handle them.

- [ ] **Step 2: Verify**

Run: `npm test -C frontend -- --run`
Expected: existing tests still pass (no behaviour change yet)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/test/handlers.ts
git commit -m "test(frontend): default MSW handlers for /api/findings/ and /api/evidence/"
```

---

### Task 4: `useScanRunFindingsQuery` hook with polling + terminal flush

**Files:**
- Modify: `frontend/src/features/scan-runs/api.ts` (currently 97 lines; new hook adds ~30, target ~130)
- Test: `frontend/src/features/scan-runs/api.findings.test.tsx`

This hook mirrors `useScanRunTargetRunsQuery` (api.ts:71–97) line-for-line, but hits `/api/findings/?scan_run=<id>` instead of `/api/scan-runs/:id/target-runs/`.

- [ ] **Step 1: Write the failing test** — `api.findings.test.tsx`

```tsx
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse, delay } from "msw";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactNode } from "react";
import { server } from "../../test/server";
import {
  useScanRunFindingsQuery,
  scanRunFindingsKey,
  SCAN_RUNS_KEY,
} from "./api";
import { makeFinding } from "./__fixtures__/finding";

const SCAN_RUN_ID = "s1111111-1111-1111-1111-111111111111";

function wrapper(client: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

describe("useScanRunFindingsQuery", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("hits /api/findings/?scan_run=<id>", async () => {
    let calledWith = "";
    server.use(
      http.get("/api/findings/", ({ request }) => {
        calledWith = new URL(request.url).searchParams.get("scan_run") ?? "";
        return HttpResponse.json({
          count: 1, next: null, previous: null,
          results: [makeFinding()],
        });
      }),
    );
    const client = new QueryClient();
    const { result } = renderHook(
      () => useScanRunFindingsQuery(SCAN_RUN_ID, { livePolling: false }),
      { wrapper: wrapper(client) },
    );
    vi.useRealTimers();
    await waitFor(() => expect(result.current.data?.count).toBe(1));
    expect(calledWith).toBe(SCAN_RUN_ID);
  });

  it("polls every 2s when livePolling=true", async () => {
    let calls = 0;
    server.use(
      http.get("/api/findings/", () => {
        calls += 1;
        return HttpResponse.json({
          count: 0, next: null, previous: null, results: [],
        });
      }),
    );
    const client = new QueryClient();
    renderHook(
      () => useScanRunFindingsQuery(SCAN_RUN_ID, { livePolling: true }),
      { wrapper: wrapper(client) },
    );
    vi.useRealTimers();
    await waitFor(() => expect(calls).toBeGreaterThanOrEqual(1));
    vi.useFakeTimers();
    await vi.advanceTimersByTimeAsync(2100);
    vi.useRealTimers();
    await waitFor(() => expect(calls).toBeGreaterThanOrEqual(2));
  });

  // Three flush cases mirror 6B's `api.target-runs.flush.test.tsx` exactly:

  it("flush — no in-flight request: refetches and locks fresh data", async () => {
    // 1. Mount with livePolling=true; let one fetch complete (cached data present).
    // 2. Re-render with livePolling=false.
    // 3. Assert: another fetch fires (refetchQueries on terminal flip) and the
    //    cache shows the new value.
  });

  it("flush — in-flight with cached data: cancels then refetches", async () => {
    // 1. Mount with livePolling=true; complete one fetch (cache has v1).
    // 2. Start a second fetch but delay the response.
    // 3. Re-render with livePolling=false BEFORE the in-flight resolves.
    // 4. Assert: in-flight request was cancelled (server saw cancellation OR
    //    promise rejected) AND a fresh fetch fires (refetchQueries) AND cache
    //    settles to v2 (the post-flush response).
  });

  it("flush — in-flight with NO cached data: cancels then refetches (the 6B race fix)", async () => {
    // 1. Mount with livePolling=true; FIRST fetch is delayed (no cache yet).
    // 2. Re-render with livePolling=false BEFORE the first fetch resolves.
    // 3. Assert: the in-flight initial fetch was cancelled AND a new fetch
    //    fires (refetchQueries with type:"active" still triggers it) AND
    //    cache settles. This is the case `invalidateQueries+cancelRefetch`
    //    silently lost in 6B before the cancelQueries+refetchQueries fix.
  });

  it("flush — no flush on initial render (livePolling: false from start)", async () => {
    // Mount with livePolling=false, never flip. Assert: exactly one fetch.
    // Guards against firing flush on every render where prev.current === false.
  });

  it("disabled when scanRunId is undefined", () => {
    const client = new QueryClient();
    const { result } = renderHook(
      () => useScanRunFindingsQuery(undefined, { livePolling: false }),
      { wrapper: wrapper(client) },
    );
    expect(result.current.fetchStatus).toBe("idle");
  });

  it("cascades from SCAN_RUNS_KEY invalidation (key shape is child of SCAN_RUNS_KEY)", async () => {
    let calls = 0;
    server.use(
      http.get("/api/findings/", () => {
        calls += 1;
        return HttpResponse.json({
          count: 0, next: null, previous: null, results: [],
        });
      }),
    );
    const client = new QueryClient();
    renderHook(
      () => useScanRunFindingsQuery(SCAN_RUN_ID, { livePolling: false }),
      { wrapper: wrapper(client) },
    );
    vi.useRealTimers();
    await waitFor(() => expect(calls).toBe(1));
    const before = calls;
    await client.invalidateQueries({ queryKey: SCAN_RUNS_KEY });
    await waitFor(() => expect(calls).toBe(before + 1));
  });
});
```

Run: `npm test -C frontend -- api.findings.test.tsx --run`
Expected: FAIL with "useScanRunFindingsQuery is not exported"

- [ ] **Step 2: Implement the hook** — append to `frontend/src/features/scan-runs/api.ts`

```ts
export const scanRunFindingsKey = (id: string) =>
  [...SCAN_RUNS_KEY, id, "findings"] as const;

type ScanRunChildOptions = { livePolling?: boolean };

export function useScanRunFindingsQuery(
  scanRunId: string | undefined,
  options?: ScanRunChildOptions,
) {
  const client = useQueryClient();
  const livePolling = Boolean(options?.livePolling);
  const prev = useRef(livePolling);

  useEffect(() => {
    if (prev.current && !livePolling && scanRunId) {
      const key = scanRunFindingsKey(scanRunId);
      void (async () => {
        await client.cancelQueries({ queryKey: key });
        await client.refetchQueries({ queryKey: key, type: "active" });
      })();
    }
    prev.current = livePolling;
  }, [livePolling, scanRunId, client]);

  return useQuery({
    queryKey: scanRunFindingsKey(scanRunId ?? ""),
    queryFn: () =>
      http<Paginated<Finding>>(`/api/findings/?scan_run=${scanRunId}`),
    enabled: Boolean(scanRunId),
    refetchInterval: livePolling ? 2000 : false,
  });
}
```

Add `Finding` to the import list at the top of the file.

Note: we deliberately do **not** introduce a shared `useScanRunChildQuery` helper yet — two callsites (target-runs and findings) is not enough to justify the abstraction; three (after evidence) is the moment to revisit, but per YAGNI it stays inline through 6C.

- [ ] **Step 3: Run tests**

Run: `npm test -C frontend -- api.findings.test.tsx --run`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/scan-runs/api.ts frontend/src/features/scan-runs/api.findings.test.tsx
git commit -m "feat(frontend): useScanRunFindingsQuery with polling + terminal flush"
```

---

### Task 5: `useScanRunEvidenceQuery` hook with polling + terminal flush

**Files:**
- Modify: `frontend/src/features/scan-runs/api.ts` (after task 4 ~130 lines; this adds ~30, target ~160)
- Test: `frontend/src/features/scan-runs/api.evidence.test.tsx`

Identical structure to Task 4. Hits `/api/evidence/?scan_run=<id>`. Type: `Paginated<Evidence>`. Key: `scanRunEvidenceKey(id) = [...SCAN_RUNS_KEY, id, "evidence"]` (child of `SCAN_RUNS_KEY` so it cascades on scan-run invalidation, mirroring task 4 and the 6B target-runs key).

- [ ] **Step 1: Write the failing test** — copy `api.findings.test.tsx`, change `findings` → `evidence`, `Finding` → `Evidence`, `makeFinding` → `makeEvidence`. Copy the **full** test matrix from Task 4: basic fetch with `?scan_run=<id>` assertion, 2 s polling, all four terminal-flush cases (no in-flight, in-flight + cache, in-flight + no cache, never-flipped), `enabled: false` when scanRunId undefined, and `SCAN_RUNS_KEY` cascade invalidation. ~8 tests total per hook.

- [ ] **Step 2: Implement** — mirror the findings hook exactly. The shape difference (Evidence has no `severity`/`status`) doesn't matter at this layer — the hook just returns `Paginated<Evidence>`.

- [ ] **Step 3: Run tests**

Run: `npm test -C frontend -- api.evidence.test.tsx --run`
Expected: PASS

- [ ] **Step 4: Verify api.ts size**

Run: `wc -l frontend/src/features/scan-runs/api.ts`
Expected: under 200 lines. If at 195+, plan to split in a follow-up (do **not** split now — keep the slice focused).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/scan-runs/api.ts frontend/src/features/scan-runs/api.evidence.test.tsx
git commit -m "feat(frontend): useScanRunEvidenceQuery with polling + terminal flush"
```

---

### Phase 1 exit criteria

- [ ] `npm test -C frontend -- --run` green.
- [ ] `npm test -C frontend -- --coverage --run` shows 100 % on the two new hooks and the modified `api.ts`.
- [ ] `frontend/src/features/scan-runs/api.ts` under 200 lines.
- [ ] Two new fixture factories, two new test files, two new exports from `api.ts`, two new entries in default MSW handlers.
- [ ] `/simplify` round clean (or fixes applied + recommitted).
