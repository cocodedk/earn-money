# Phase 3 — Wire into `ScanRunDetail` + integration tests + E2E

Connect `ScanRunTargetsTable` to the detail page, lock the parent-status transition tests + lifecycle-cascade + visible-badge-update + parent-background-error branches at the integration level, and add a focused E2E.

---

### Task A: Render `ScanRunTargetsTable` inside `ScanRunDetail`

**Files:**
- Modify: `frontend/src/features/scan-runs/ScanRunDetail.tsx`

- [ ] **Step 1: Wire the table below the MetaList**

At the top of the `DetailBody` (or whatever the inner component is named — grep for the existing `MetaList` render), derive `livePolling` from the resolved `run.status` and render the table:

```tsx
import { ScanRunTargetsTable } from "./ScanRunTargetsTable";

// inside DetailBody, after the existing <MetaList>:
const livePolling = run.status === "running" || run.status === "stopping";
return (
  <>
    {/* existing header + MetaList */}
    <ScanRunTargetsTable scanRunId={run.id} livePolling={livePolling} />
  </>
);
```

The parent's self-polling already runs inside `useScanRunQuery` (Phase 1 Task B); `livePolling` here is just a derived bool passed down.

- [ ] **Step 2: Run existing `ScanRunDetail.test.tsx` — must still pass**

```bash
cd frontend && npm test -- src/features/scan-runs/ScanRunDetail.test.tsx
```

Expected: PASS — existing tests don't assert table absence; they assert header + MetaList, which are untouched.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/scan-runs/ScanRunDetail.tsx
git commit -m "feat(frontend): render ScanRunTargetsTable inside ScanRunDetail"
```

Run `/simplify` to clean.

---

### Task B: Integration tests for the table inside `ScanRunDetail`

**Files:**
- Create: `frontend/src/features/scan-runs/ScanRunDetail.target-runs.test.tsx`

- [ ] **Step 1: Imports + `mountAt` helper at the top of the file**

```tsx
import { describe, it, expect, vi } from "vitest";
import { screen, within, waitFor } from "@testing-library/react";
import { Routes, Route } from "react-router-dom";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { scanRunKey } from "./api";
import { makeScanRun } from "./__fixtures__/scan-run";
import { makeScanTargetRun } from "./__fixtures__/scan-target-run";
import type { ScanRun } from "../../types/api";
import { ScanRunDetail } from "./ScanRunDetail";

function mountAt(id: string) {
  // renderWithProviders already wraps in MemoryRouter + QueryClientProvider
  // and returns the test `client` for invalidation/seeding from the test.
  return renderWithProviders(
    <Routes>
      <Route path="/scan-runs/:id" element={<ScanRunDetail />} />
    </Routes>,
    { route: `/scan-runs/${id}` },
  );
}
```

> **Hook+integration layered coverage is deliberate.** Some branches below (terminal flush in-flight, no-cached-data in-flight, lifecycle cascade) are ALSO covered at the hook level in `api.target-runs.test.tsx`. The hook tests lock the hook's contract; these integration tests lock the same contract end-to-end through `ScanRunDetail`. Do NOT delete one as "duplicate" — they exercise different layers.

- [ ] **Step 2: Write the test body (10 branches across 4 logical groups)**

Append the `describe` open + all 10 `it(...)` blocks to the file, organised into the four groups below. Group boundaries are flagged with `// --- group: name ---` so the engineer can self-checkpoint between groups:

1. **Happy + parent-driven transitions** (4): happy load, queued→running, running→done, running→stopping→stopped.
2. **Terminal-flush in-flight branches** (2): cached data exists, no cached data (round-5 edge case).
3. **Cascade + visible polling** (2): lifecycle stop-from-paused cascade, visible badge update on poll.
4. **Background error silence** (2): parent 500, parent 404.

Total: 10 `it` blocks. The hook-level tests in `api.target-runs.test.tsx` cover similar branches at the hook layer; the integration tests here lock the same contract end-to-end through `ScanRunDetail`. Deliberate layered coverage — do NOT delete one as "duplicate" (see also the note in Step 1).

```tsx
describe("ScanRunDetail target-runs integration", () => {
  // --- group 1: happy + parent-driven transitions ---
  it("renders the table beneath the MetaList on happy detail load", async () => {
    server.use(
      msw.get("/api/scan-runs/r-1/", () => HttpResponse.json(makeScanRun({ id: "r-1", status: "running" }))),
      msw.get("/api/scan-runs/r-1/target-runs/", () => HttpResponse.json({
        count: 1, next: null, previous: null,
        results: [makeScanTargetRun({ id: "tr-1", status: "queued" })],
      })),
    );
    mountAt("r-1");
    expect(await screen.findByTestId("target-run-row-tr-1")).toBeInTheDocument();
  });

  it("parent queued → running: table starts polling", async () => {
    vi.useFakeTimers();
    let parent: ScanRun = makeScanRun({ id: "r-1", status: "queued" });
    let calls = 0;
    server.use(
      msw.get("/api/scan-runs/r-1/", () => HttpResponse.json(parent)),
      msw.get("/api/scan-runs/r-1/target-runs/", () => {
        calls += 1;
        return HttpResponse.json({ count: 0, next: null, previous: null, results: [] });
      }),
    );
    const { client } = mountAt("r-1");
    await vi.advanceTimersByTimeAsync(2500);
    const beforeFlip = calls;
    // With status "queued", parent's refetchInterval is false (no polling),
    // so flipping `parent` here alone wouldn't trigger a re-fetch. The test
    // explicitly invalidates the parent key to simulate the cascade that
    // a lifecycle mutation (or focus event) would deliver in real use.
    parent = makeScanRun({ id: "r-1", status: "running" });
    await client.invalidateQueries({ queryKey: scanRunKey("r-1") });
    await vi.advanceTimersByTimeAsync(3000);
    expect(calls).toBeGreaterThan(beforeFlip);
    vi.useRealTimers();
  });

  it("parent running → done: cache ends with fresh terminal rows (terminal flush)", async () => {
    vi.useFakeTimers();
    let parent: ScanRun = makeScanRun({ id: "r-1", status: "running" });
    let target = makeScanTargetRun({ id: "tr-1", status: "running" });
    server.use(
      msw.get("/api/scan-runs/r-1/", () => HttpResponse.json(parent)),
      msw.get("/api/scan-runs/r-1/target-runs/", () =>
        HttpResponse.json({ count: 1, next: null, previous: null, results: [target] }),
      ),
    );
    mountAt("r-1");
    await vi.advanceTimersByTimeAsync(2500);
    parent = makeScanRun({ id: "r-1", status: "done" });
    target = makeScanTargetRun({ id: "tr-1", status: "done" });
    await vi.advanceTimersByTimeAsync(3000); // parent flips, flush fires
    await waitFor(() => {
      const row = screen.getByTestId("target-run-row-tr-1");
      expect(within(row).getByTestId("status-done")).toBeInTheDocument();
    });
    vi.useRealTimers();
  });

  it("parent running → stopping → stopped: same cache-content assertion shape", async () => {
    vi.useFakeTimers();
    let parent: ScanRun = makeScanRun({ id: "r-1", status: "running" });
    let target = makeScanTargetRun({ id: "tr-1", status: "running" });
    server.use(
      msw.get("/api/scan-runs/r-1/", () => HttpResponse.json(parent)),
      msw.get("/api/scan-runs/r-1/target-runs/", () =>
        HttpResponse.json({ count: 1, next: null, previous: null, results: [target] }),
      ),
    );
    mountAt("r-1");
    await vi.advanceTimersByTimeAsync(2500);
    parent = makeScanRun({ id: "r-1", status: "stopping" });
    await vi.advanceTimersByTimeAsync(2500);
    parent = makeScanRun({ id: "r-1", status: "stopped" });
    target = makeScanTargetRun({ id: "tr-1", status: "stopped", finished_at: "2026-05-19T10:00:00Z" });
    await vi.advanceTimersByTimeAsync(3000);
    await waitFor(() => {
      const row = screen.getByTestId("target-run-row-tr-1");
      expect(within(row).getByTestId("status-stopped")).toBeInTheDocument();
    });
    vi.useRealTimers();
  });

  // --- group 2: terminal-flush in-flight branches ---
  it("in-flight flush — cached data exists: cache ends fresh", async () => {
    vi.useFakeTimers();
    let parent: ScanRun = makeScanRun({ id: "r-1", status: "running" });
    let phase: "pre" | "post" = "pre";
    server.use(
      msw.get("/api/scan-runs/r-1/", () => HttpResponse.json(parent)),
      msw.get("/api/scan-runs/r-1/target-runs/", async () => {
        if (phase === "pre") {
          return HttpResponse.json({
            count: 1, next: null, previous: null,
            results: [makeScanTargetRun({ id: "tr-1", status: "running" })],
          });
        }
        await new Promise((r) => setTimeout(r, 200));
        return HttpResponse.json({
          count: 1, next: null, previous: null,
          results: [makeScanTargetRun({ id: "tr-1", status: "done" })],
        });
      }),
    );
    mountAt("r-1");
    await vi.advanceTimersByTimeAsync(2500); // cached "running" landed
    phase = "post";
    parent = makeScanRun({ id: "r-1", status: "done" });
    await vi.advanceTimersByTimeAsync(2000); // parent polls done, flush fires while child is in-flight
    await vi.advanceTimersByTimeAsync(500);
    await waitFor(() => {
      const row = screen.getByTestId("target-run-row-tr-1");
      expect(within(row).getByTestId("status-done")).toBeInTheDocument();
    });
    vi.useRealTimers();
  });

  it("no-cached-data in-flight at terminal flip: cache ends fresh (round-5 edge case)", async () => {
    vi.useFakeTimers();
    let parent: ScanRun = makeScanRun({ id: "r-1", status: "running" });
    let delayMs = 800; // initial fetch slow
    server.use(
      msw.get("/api/scan-runs/r-1/", () => HttpResponse.json(parent)),
      msw.get("/api/scan-runs/r-1/target-runs/", async () => {
        await new Promise((r) => setTimeout(r, delayMs));
        return HttpResponse.json({
          count: 1, next: null, previous: null,
          results: [makeScanTargetRun({ id: "tr-1", status: parent.status === "done" ? "done" : "running" })],
        });
      }),
    );
    mountAt("r-1");
    await vi.advanceTimersByTimeAsync(100); // initial fetch in flight, no cached data
    parent = makeScanRun({ id: "r-1", status: "done" });
    delayMs = 0;
    await vi.advanceTimersByTimeAsync(3000);
    await waitFor(() => {
      const row = screen.getByTestId("target-run-row-tr-1");
      expect(within(row).getByTestId("status-done")).toBeInTheDocument();
    });
    vi.useRealTimers();
  });

  // --- group 3: cascade + visible polling ---
  it("lifecycle stop-from-paused cascade refetches target-runs", async () => {
    let parent: ScanRun = makeScanRun({ id: "r-1", status: "paused" });
    let targetCalls = 0;
    server.use(
      msw.get("/api/scan-runs/r-1/", () => HttpResponse.json(parent)),
      msw.get("/api/scan-runs/r-1/target-runs/", () => {
        targetCalls += 1;
        return HttpResponse.json({ count: 0, next: null, previous: null, results: [] });
      }),
      msw.post("/api/scan-runs/r-1/stop/", () => {
        parent = makeScanRun({ id: "r-1", status: "stopping" });
        return HttpResponse.json(parent);
      }),
    );
    mountAt("r-1");
    await screen.findByTestId("targets-empty");
    const before = targetCalls;
    (await screen.findByRole("button", { name: /stop/i })).click();
    await waitFor(() => expect(targetCalls).toBeGreaterThan(before));
  });

  it("visible badge update on poll (within 2 s)", async () => {
    vi.useFakeTimers();
    let target = makeScanTargetRun({ id: "tr-1", status: "queued" });
    server.use(
      msw.get("/api/scan-runs/r-1/", () => HttpResponse.json(makeScanRun({ id: "r-1", status: "running" }))),
      msw.get("/api/scan-runs/r-1/target-runs/", () =>
        HttpResponse.json({ count: 1, next: null, previous: null, results: [target] }),
      ),
    );
    mountAt("r-1");
    const row = await screen.findByTestId("target-run-row-tr-1");
    expect(within(row).getByTestId("status-queued")).toBeInTheDocument();
    target = makeScanTargetRun({ id: "tr-1", status: "running" });
    await vi.advanceTimersByTimeAsync(2500);
    await waitFor(() => {
      const badge = within(row).getByTestId("status-running");
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveTextContent("running"); // assert visible text flipped, not just data-testid
    });
    vi.useRealTimers();
  });

  // --- group 4: background error silence ---
  it("parent background 500 → page stays mounted, no full-page takeover", async () => {
    let serveError = false;
    server.use(
      msw.get("/api/scan-runs/r-1/", () => {
        if (serveError) return new HttpResponse(null, { status: 500 });
        return HttpResponse.json(makeScanRun({ id: "r-1", status: "running" }));
      }),
      msw.get("/api/scan-runs/r-1/target-runs/", () =>
        HttpResponse.json({ count: 1, next: null, previous: null, results: [makeScanTargetRun({ id: "tr-1" })] }),
      ),
    );
    mountAt("r-1");
    await screen.findByTestId("target-run-row-tr-1");
    serveError = true;
    await new Promise((r) => setTimeout(r, 2500));
    expect(screen.getByTestId("target-run-row-tr-1")).toBeInTheDocument();
    expect(screen.queryByText(/backend unreachable/i)).not.toBeInTheDocument();
  });

  it("parent background 404 → page stays mounted, no not-found takeover", async () => {
    let serve404 = false;
    server.use(
      msw.get("/api/scan-runs/r-1/", () => {
        if (serve404) return new HttpResponse(null, { status: 404 });
        return HttpResponse.json(makeScanRun({ id: "r-1", status: "running" }));
      }),
      msw.get("/api/scan-runs/r-1/target-runs/", () =>
        HttpResponse.json({ count: 1, next: null, previous: null, results: [makeScanTargetRun({ id: "tr-1" })] }),
      ),
    );
    mountAt("r-1");
    await screen.findByTestId("target-run-row-tr-1");
    serve404 = true;
    await new Promise((r) => setTimeout(r, 2500));
    expect(screen.getByTestId("target-run-row-tr-1")).toBeInTheDocument();
    expect(screen.queryByText(/not found/i)).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run tests — must pass**

```bash
cd frontend && npm test -- src/features/scan-runs/ScanRunDetail.target-runs.test.tsx
```

Expected: PASS for all 10 branches (happy / queued→running / running→done / running→stopping→stopped / in-flight-with-cached-data / no-cached-data / lifecycle cascade / visible badge / parent 500 / parent 404).

- [ ] **Step 4: Coverage + commit**

```bash
cd frontend && npm test -- --coverage
git add frontend/src/features/scan-runs/ScanRunDetail.target-runs.test.tsx
git commit -m "test(frontend): ScanRunDetail target-runs integration branches"
```

Run `/simplify` to clean.

---

### Task C: E2E — `/scan-runs/:id` renders header + ≥1 target row

**Files:**
- Create: `frontend/src/features/scan-runs/ScanRunDetail.e2e.test.tsx`

- [ ] **Step 1: Write the E2E**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { App } from "../../App";
import { makeScanRun } from "./__fixtures__/scan-run";
import { makeScanTargetRun } from "./__fixtures__/scan-target-run";

describe("/scan-runs/:id e2e", () => {
  it("renders the 6A header AND ≥1 target row from the 6B table", async () => {
    server.use(
      msw.get("/api/scan-runs/r-1/", () =>
        HttpResponse.json(makeScanRun({ id: "r-1", status: "running" })),
      ),
      msw.get("/api/scan-runs/r-1/target-runs/", () =>
        HttpResponse.json({
          count: 2, next: null, previous: null,
          results: [
            makeScanTargetRun({ id: "tr-1", status: "queued" }),
            makeScanTargetRun({ id: "tr-2", status: "done", finished_at: "2026-05-19T10:00:00Z" }),
          ],
        }),
      ),
      msw.get("/api/projects/", () =>
        HttpResponse.json({ count: 1, next: null, previous: null, results: [{ id: "p-1", name: "Test", description: "", target_count: 1, scan_run_count: 1, created_at: "2026-05-19T00:00:00Z" }] }),
      ),
      msw.get("/api/stubs/", () =>
        HttpResponse.json([{ slug: "1.15", title: "Public JS bundles", status: "active" }]),
      ),
    );

    window.history.pushState({}, "", "/scan-runs/r-1");
    render(<App />);

    expect(await screen.findByTestId("target-run-row-tr-1")).toBeInTheDocument();
    expect(screen.getByTestId("target-run-row-tr-2")).toBeInTheDocument();
    expect(screen.queryByTestId("targets-truncation")).not.toBeInTheDocument();
  });

  it("renders truncation footer when next !== null", async () => {
    server.use(
      msw.get("/api/scan-runs/r-2/", () =>
        HttpResponse.json(makeScanRun({ id: "r-2", status: "done" })),
      ),
      msw.get("/api/scan-runs/r-2/target-runs/", () =>
        HttpResponse.json({
          count: 75, next: "?page=2", previous: null,
          results: [makeScanTargetRun({ id: "tr-1" })],
        }),
      ),
      msw.get("/api/projects/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      msw.get("/api/stubs/", () => HttpResponse.json([])),
    );
    window.history.pushState({}, "", "/scan-runs/r-2");
    render(<App />);
    expect(await screen.findByTestId("targets-truncation")).toHaveTextContent(
      "Showing first 1 of 75 targets",
    );
  });
});
```

Note: this is a **separate** E2E file. Do NOT extend `App.e2e.test.tsx` — it is already over the 200-line cap (305 lines) and is a separate deferred refactor.

- [ ] **Step 2: Run tests — must pass**

```bash
cd frontend && npm test -- src/features/scan-runs/ScanRunDetail.e2e.test.tsx
```

Expected: PASS for both branches.

- [ ] **Step 3: Final coverage check + commit**

```bash
cd frontend && npm test -- --coverage
npm run build
git add frontend/src/features/scan-runs/ScanRunDetail.e2e.test.tsx
git commit -m "test(frontend): ScanRunDetail e2e — header + table + truncation footer"
```

Run `/simplify` to clean.

---

### Task D: Slice-complete chat ping to em-backend

Per chat-noise-floor: one peer ping at slice completion (not per phase).

- [ ] **Step 1: Send the ping**

After the final commit lands and `/simplify` is clean:

```text
to: agent-em-backend
6B slice complete on feat/em-frontend (commits up to <SHA>). Backend lock: e93c6f4 (paused→stop enqueue) + 8f5caec (serializer fields). Polling: parent self-polls 2 s while running/stopping; table mirrors via livePolling derived from parent status; terminal flush uses cancelQueries + refetchQueries to handle the no-cached-data in-flight edge. DetailPageGuard narrowing keeps the page mounted on background 500/404. All tests + coverage + build green. Next: 6C (Findings/Evidence panels) — will pick up after operator review.
```

- [ ] **Step 2: Update task tracker**

Mark task #3 ("Write 6B 3-phase plan tree") done if not already; mark new "Execute 6B" task if you created one.

---

### Phase 3 done — 6B shipped

- 6A header + 6B table both render on `/scan-runs/:id`.
- Polling, terminal flush, DetailPageGuard narrowing, mixed-status timestamp rendering, scoped inline error all locked by tests.
- 100% coverage on new/modified files, no file over 200 lines, `/simplify` clean per commit, em-backend pinged.

Resume target: 6C (Findings + Evidence panels) — separate spec, separate plan tree.
