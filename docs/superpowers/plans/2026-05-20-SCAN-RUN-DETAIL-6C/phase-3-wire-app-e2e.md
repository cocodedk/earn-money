# Phase 3 — Wire into ScanRunDetail + integration + E2E

**Goal:** Render `<ScanRunFindingsPanel />` and `<ScanRunEvidencePanel />` below the existing target table on `/scan-runs/:id`, with `livePolling` driven by `isRunActive(run.status)`. Add integration tests for the happy path and a transition assertion, plus an E2E test that asserts all four sections render.

**Insertion point:** `frontend/src/features/scan-runs/ScanRunDetail.tsx:39-42` — directly after `<ScanRunTargetsTable …/>`. Both new panels receive the same `scanRunId` + `livePolling` props.

---

### Task 8: Render both panels in ScanRunDetail

**Files:**
- Modify: `frontend/src/features/scan-runs/ScanRunDetail.tsx` (currently 65 lines; new panels add ~10, target ~75)
- Test: integration tests live in `ScanRunDetail.findings-evidence.test.tsx` (new file, Task 9)

- [ ] **Step 1: Write a minimal failing assertion** — add to a new test file `ScanRunDetail.findings-evidence.test.tsx`. Use the `mountAt(id)` pattern from the shipped `ScanRunDetail.target-runs.test.tsx:15-26` (which seeds `/api/projects/` + `/api/stubs/` so ScanRunDetail's sibling queries don't 404, and returns the `client` for invalidation in later tasks):

```tsx
import { describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { Routes, Route } from "react-router-dom";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { withBareArray, withPaginated } from "../../test/helpers";
import { scanRunKey } from "./api";
import { ScanRunDetail } from "./ScanRunDetail";
import { makeScanRun } from "./__fixtures__/scan-run";
import { makeScanTargetRun } from "./__fixtures__/scan-target-run";
import { makeStub } from "../stubs/__fixtures__/stub";
import { makeFinding } from "./__fixtures__/finding";
import { makeEvidence } from "./__fixtures__/evidence";
import type { ScanRun } from "../../types/api";

const ID = "11111111-1111-1111-1111-111111111111";

function mountAt(id: string) {
  withPaginated("/api/projects/", []);
  withBareArray("/api/stubs/", [makeStub()]);
  return renderWithProviders(
    <Routes>
      <Route path="/scan-runs/:id" element={<ScanRunDetail />} />
    </Routes>,
    { route: `/scan-runs/${id}` },
  );
}

it("renders Findings panel below targets table", async () => {
  server.use(
    msw.get(`/api/scan-runs/${ID}/`, () =>
      HttpResponse.json(makeScanRun({ id: ID, status: "done" })),
    ),
  );
  mountAt(ID);
  expect(await screen.findByText(/Findings \(0\)/)).toBeInTheDocument();
});
```

`renderWithProviders` returns `{ client, ...render }` — so tasks 9 case 3 can call `mountAt(ID)` and destructure `const { client } = mountAt(ID)` to get the QueryClient for invalidation.

Run: `npm test -C frontend -- ScanRunDetail.findings-evidence.test.tsx --run`
Expected: FAIL (panel not rendered)

- [ ] **Step 2: Insert the two panels** — modify `ScanRunDetail.tsx`, after line 42:

```tsx
import { ScanRunFindingsPanel } from "./ScanRunFindingsPanel";
import { ScanRunEvidencePanel } from "./ScanRunEvidencePanel";

// inside DetailBody, after <ScanRunTargetsTable />:
<ScanRunFindingsPanel
  scanRunId={run.id}
  livePolling={isRunActive(run.status)}
/>
<ScanRunEvidencePanel
  scanRunId={run.id}
  livePolling={isRunActive(run.status)}
/>
```

- [ ] **Step 3: Run tests**

Run: `npm test -C frontend -- ScanRunDetail.findings-evidence.test.tsx --run`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/scan-runs/ScanRunDetail.tsx frontend/src/features/scan-runs/ScanRunDetail.findings-evidence.test.tsx
git commit -m "feat(frontend): render Findings + Evidence panels in ScanRunDetail"
```

---

### Task 9: Integration tests — happy path + transitions

**Files:**
- Modify: `frontend/src/features/scan-runs/ScanRunDetail.findings-evidence.test.tsx` (grew in Task 8)

Add four more tests. **Integration scope:** these tests prove that `ScanRunDetail` correctly wires `isRunActive(run.status)` into both panels' `livePolling`. They do **not** re-prove the cancel-vs-cache flush mechanics — those live in `api.findings.test.tsx`/`api.evidence.test.tsx` (Phase 1, Tasks 4–5). Keep each integration assertion narrow.

1. **Happy path with data** — server returns 2 findings + 3 evidence; assert `screen.findAllByTestId(/^finding-row-/)` returns 2 elements AND `screen.findAllByTestId(/^evidence-row-/)` returns 3 elements AND `screen.findByText(/Findings \(2\)/)` AND `screen.findByText(/Evidence \(3\)/)`.

2. **Both panels poll while running** — server returns scan run with `status: "running"` plus 0 findings + 0 evidence initially, then a `phase` flip injects 1 finding for the next poll tick. Gate on a **positive** marker that the initial fetch settled (empty-state testid) before flipping phase, so the assertion can't pass vacuously during the loading state:
   ```ts
   let phase: "pre" | "post" = "pre";
   server.use(
     msw.get(`/api/scan-runs/${ID}/`, () =>
       HttpResponse.json(makeScanRun({ id: ID, status: "running" })),
     ),
     msw.get("/api/findings/", () =>
       HttpResponse.json({
         count: phase === "pre" ? 0 : 1,
         next: null,
         previous: null,
         results: phase === "pre"
           ? []
           : [makeFinding({ id: "ffffffff-aaaa-aaaa-aaaa-aaaaaaaaaaaa" })],
       }),
     ),
   );
   vi.useFakeTimers();
   mountAt(ID);
   vi.useRealTimers();
   await screen.findByTestId("findings-empty"); // initial fetch settled
   phase = "post";
   vi.useFakeTimers();
   await vi.advanceTimersByTimeAsync(2100); // one poll tick past 2s
   vi.useRealTimers();
   await screen.findByTestId("finding-row-ffffffff-aaaa-aaaa-aaaa-aaaaaaaaaaaa");
   ```

3. **Terminal flush narrow scope** — server starts with `status: "running"`, then flips parent to `done`. Assert: both panels each issue **one** extra fetch after the parent flip. Counter pattern + mutable scan run:
   ```ts
   let scanRun: ScanRun = makeScanRun({ id: ID, status: "running" });
   let fcalls = 0;
   let ecalls = 0;
   server.use(
     msw.get(`/api/scan-runs/${ID}/`, () => HttpResponse.json(scanRun)),
     msw.get("/api/findings/", () => {
       fcalls += 1;
       return HttpResponse.json({ count: 0, next: null, previous: null, results: [] });
     }),
     msw.get("/api/evidence/", () => {
       ecalls += 1;
       return HttpResponse.json({ count: 0, next: null, previous: null, results: [] });
     }),
   );
   const { client } = mountAt(ID);
   await waitFor(() => expect(fcalls).toBe(1));
   await waitFor(() => expect(ecalls).toBe(1));
   const before = { f: fcalls, e: ecalls };
   scanRun = makeScanRun({ id: ID, status: "done" });
   await client.invalidateQueries({ queryKey: scanRunKey(ID) });
   await waitFor(() => expect(fcalls).toBe(before.f + 1));
   await waitFor(() => expect(ecalls).toBe(before.e + 1));
   ```

4. **Both panels show error callout on 500** — server returns `HttpResponse.error()` for both endpoints, assert `screen.findAllByText(/Could not load/)` returns at least 2 callouts.

Each test that polls uses `vi.useFakeTimers()` + `vi.useRealTimers()` flip-flop per the established pattern (see `api.findings.test.tsx` Task 4 for the verbatim flip pattern).

- [ ] **Step 1: Add the four tests** — copy the mutable parent and counter patterns from `frontend/src/features/scan-runs/ScanRunDetail.target-runs.test.tsx` lines 1–80 (the `let scanRun = ...` + `let calls = 0` setup). File size target after the four additions: ~190 lines under 200. If approaching the cap, split into two files (`...findings-integration.test.tsx` + `...evidence-integration.test.tsx`) — but in one commit, same task.

- [ ] **Step 2: Run tests**

Run: `npm test -C frontend -- ScanRunDetail.findings-evidence.test.tsx --run`
Expected: PASS, 5/5 (the assertion from Task 8 + four new ones)

- [ ] **Step 3: Coverage check**

Run: `npm test -C frontend -- ScanRunDetail --coverage --run`
Expected: 100 % on `ScanRunDetail.tsx`, `ScanRunFindingsPanel.tsx`, `ScanRunEvidencePanel.tsx`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/scan-runs/ScanRunDetail.findings-evidence.test.tsx
git commit -m "test(frontend): ScanRunDetail findings/evidence integration — happy/polling/transition/error"
```

---

### Task 10: E2E — all four sections render together

**Files:**
- Modify: `frontend/src/features/scan-runs/ScanRunDetail.e2e.test.tsx` (currently 94 lines from 6B)

Extend the existing E2E file with one new test. The new test asserts the cross-cutting structural wiring (one element from each of the four sections) using **testids** rather than heading text, because heading text is already exercised by the unit tests at Phase 2 / integration tests at Task 9 — re-asserting heading-text strings at E2E layer is redundant.

- [ ] **Step 1: Add a new test case** — verbatim:

```tsx
it("renders header + targets + findings + evidence sections", async () => {
  const id = "11111111-1111-1111-1111-111111111111";
  server.use(
    msw.get(`/api/scan-runs/${id}/`, () =>
      HttpResponse.json(
        makeScanRun({ id, status: "done", finished_at: "2026-05-20T08:30:00Z" }),
      ),
    ),
    msw.get(`/api/scan-runs/${id}/target-runs/`, () =>
      HttpResponse.json({
        count: 1, next: null, previous: null,
        results: [makeScanTargetRun({ id: "33333333-3333-3333-3333-333333333333" })],
      }),
    ),
    msw.get("/api/findings/", () =>
      HttpResponse.json({
        count: 1, next: null, previous: null,
        results: [makeFinding({ id: "ffffffff-aaaa-aaaa-aaaa-aaaaaaaaaaaa" })],
      }),
    ),
    msw.get("/api/evidence/", () =>
      HttpResponse.json({
        count: 1, next: null, previous: null,
        results: [makeEvidence({ id: "eeeeeeee-bbbb-bbbb-bbbb-bbbbbbbbbbbb" })],
      }),
    ),
  );
  renderWithProviders(<App />, { route: `/scan-runs/${id}` });

  // One observable per section — testids only (heading-text covered at lower layers):
  await screen.findByText(new RegExp(id.slice(0, 8)));                                  // header
  await screen.findByTestId("target-run-row-33333333-3333-3333-3333-333333333333");     // 6B target table
  await screen.findByTestId("finding-row-ffffffff-aaaa-aaaa-aaaa-aaaaaaaaaaaa");        // 6C findings
  await screen.findByTestId("evidence-row-eeeeeeee-bbbb-bbbb-bbbb-bbbbbbbbbbbb");       // 6C evidence
});
```

The imports for `makeFinding` / `makeEvidence` / `makeScanTargetRun` / `makeScanRun` / `msw` / `HttpResponse` / `server` / `renderWithProviders` / `App` / `screen` either already exist in the existing E2E file (from 6A+6B) or need adding alongside this test. Inspect the current file first to avoid duplicate imports.

- [ ] **Step 2: Verify file size**

Run: `wc -l frontend/src/features/scan-runs/ScanRunDetail.e2e.test.tsx`
Expected: ~115 (94 baseline + ~21 new lines). Under 200, no split needed.

- [ ] **Step 3: Run tests**

Run: `npm test -C frontend -- ScanRunDetail.e2e.test.tsx --run`
Expected: PASS, 3/3 (the existing two from 6B + this new one)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/scan-runs/ScanRunDetail.e2e.test.tsx
git commit -m "test(frontend): ScanRunDetail e2e — header + targets + findings + evidence"
```

---

### Phase 3 exit criteria

- [ ] `npm test -C frontend -- --run` green; full suite.
- [ ] `npm test -C frontend -- --coverage --run` shows 100 % on all 6C files.
- [ ] No file over 200 lines (`ScanRunDetail.tsx` ~75, both panels ~70 each, integration test ~190 single file OR ~120 + ~100 if split, e2e ~115).
- [ ] `npm run -C frontend build` green.
- [ ] Manual smoke: operator can launch dev server, open `/scan-runs/<active-run-id>`, see Findings and Evidence headings update during a real scan. (Can be deferred to PR review; not part of the per-commit gate.)
- [ ] `/simplify` round clean across all 6C changes.
- [ ] Single peer notify to em-backend at slice completion: "6C shipped — Findings + Evidence panels live on `/scan-runs/:id`, both scoped to `?scan_run=<id>`, 2s polling while active, terminal flush, truncation footer fires at the DRF `PAGE_SIZE = 50` boundary (text reads `Showing first {results.length} of {count} ...`). No contract changes."

---

### Slice completion checklist (whole 6C)

- [ ] All 10 tasks above committed; 10 commits in `git log origin/main..HEAD`.
- [ ] Spec-review pass: re-read `../../specs/2026-05-18-MVP-GUI/06-scan-run-detail.md` §Findings + §Evidence and confirm every listed column rendered (note: Actions column deferred — see README Out-of-scope).
- [ ] Cross-cutting code review on the slice diff before opening PR (use `feature-dev:code-reviewer` agent or `/codex-review-branch`).
- [ ] PR opened against `main` mirroring the 6B PR description structure.
- [ ] em-frontend notifies em-backend once: slice done.
