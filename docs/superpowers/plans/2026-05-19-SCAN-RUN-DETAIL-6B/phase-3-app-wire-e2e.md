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

- [ ] **Step 1: Write the file (mutable MSW pattern + transition + cascade + visible-badge + silent-error branches)**

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, within, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { makeScanRun } from "./__fixtures__/scan-run";
import { makeScanTargetRun } from "./__fixtures__/scan-target-run";
import type { ScanRun } from "../../types/api";
import { ScanRunDetail } from "./ScanRunDetail";

function mountAt(id: string) {
  return renderWithProviders(
    <MemoryRouter initialEntries={[`/scan-runs/${id}`]}>
      <Routes>
        <Route path="/scan-runs/:id" element={<ScanRunDetail />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ScanRunDetail target-runs integration", () => {
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
    mountAt("r-1");
    await vi.advanceTimersByTimeAsync(2500);
    const beforeFlip = calls;
    parent = makeScanRun({ id: "r-1", status: "running" });
    await vi.advanceTimersByTimeAsync(3000); // wait for parent poll + child polls
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
    await waitFor(() =>
      expect(within(row).getByTestId("status-running")).toBeInTheDocument(),
    );
    vi.useRealTimers();
  });

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

- [ ] **Step 2: Run tests — must pass**

```bash
cd frontend && npm test -- src/features/scan-runs/ScanRunDetail.target-runs.test.tsx
```

Expected: PASS for all 9 branches.

- [ ] **Step 3: Coverage + commit**

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
