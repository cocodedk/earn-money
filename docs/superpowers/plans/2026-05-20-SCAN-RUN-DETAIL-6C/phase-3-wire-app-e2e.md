# Phase 3 — Wire into ScanRunDetail + integration + E2E

**Goal:** Render `<ScanRunFindingsPanel />` and `<ScanRunEvidencePanel />` below the existing target table on `/scan-runs/:id`, with `livePolling` driven by `isRunActive(run.status)`. Add integration tests for the happy path and a transition assertion, plus an E2E test that asserts all four sections render.

**Insertion point:** `frontend/src/features/scan-runs/ScanRunDetail.tsx:39-42` — directly after `<ScanRunTargetsTable …/>`. Both new panels receive the same `scanRunId` + `livePolling` props.

---

### Task 8: Render both panels in ScanRunDetail

**Files:**
- Modify: `frontend/src/features/scan-runs/ScanRunDetail.tsx` (currently 65 lines; new panels add ~10, target ~75)
- Test: integration tests live in `ScanRunDetail.findings-evidence.test.tsx` (new file, Task 9)

- [ ] **Step 1: Write a minimal failing assertion** — add to a new test file `ScanRunDetail.findings-evidence.test.tsx`:

```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "../../test/server";
import { ScanRunDetail } from "./ScanRunDetail";
import { makeScanRun } from "./__fixtures__/scan-run";

const ID = "s1111111-1111-1111-1111-111111111111";

function wrap() {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/scan-runs/${ID}`]}>
        <Routes>
          <Route path="/scan-runs/:id" element={<ScanRunDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

it("renders Findings panel below targets table", async () => {
  server.use(
    http.get(`/api/scan-runs/${ID}/`, () =>
      HttpResponse.json(makeScanRun({ id: ID, status: "done" })),
    ),
  );
  wrap();
  expect(await screen.findByText(/Findings \(0\)/)).toBeInTheDocument();
});
```

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

Add four more tests:

1. **Happy path with data** — server returns 2 findings + 3 evidence; assert both tables render with correct row counts and a specific cell value (e.g. finding title appears, evidence source appears).
2. **Both panels poll while running** — server returns `status: "running"` scan run + 0 findings + 0 evidence initially, then 1 finding after first poll tick; assert finding row appears within 2.5 s of mount.
3. **Terminal flush** — server starts with `status: "running"` + empty results, then transitions to `done`; assert the panels re-fetch (use the same `let scanRun = ...` mutable pattern as 6B's `ScanRunDetail.target-runs.test.tsx`).
4. **Both panels show "Could not load …" on error** — server returns 500 for both endpoints; assert two callouts present.

Each test uses `vi.useFakeTimers()` + `vi.useRealTimers()` flip-flop per the established pattern. File size target: under 200 lines. If approaching, split into two files: `ScanRunDetail.findings-panel.test.tsx` and `ScanRunDetail.evidence-panel.test.tsx`.

- [ ] **Step 1: Add the four tests** — mirror `ScanRunDetail.target-runs.test.tsx` (176 lines) for the transition pattern.

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

Extend the existing E2E test to also assert the Findings and Evidence headings appear. One new test, no replacement.

- [ ] **Step 1: Add a new test case** — "renders all four sections together"

```tsx
it("renders header + targets + findings + evidence sections", async () => {
  // Set up MSW with scan run + 1 target run + 1 finding + 1 evidence
  // Render <ScanRunDetail />
  // Assert: heading "Scan run · {id_prefix}" present
  // Assert: "Targets" heading or target-row-{id} present
  // Assert: "Findings (1)" present
  // Assert: "Evidence (1)" present
});
```

- [ ] **Step 2: Verify file size**

Run: `wc -l frontend/src/features/scan-runs/ScanRunDetail.e2e.test.tsx`
Expected: under 200.

If at 190+, **split — do not strip existing assertions**. The existing 6A+6B E2E coverage is load-bearing. Splitting rule:
- Existing two tests stay in `ScanRunDetail.e2e.test.tsx` (header + table + truncation).
- New "all four sections" test moves to `ScanRunDetail.e2e.findings-evidence.test.tsx`.
- Shared MSW setup either inlines into each file (preferred, mirrors 6B per-file pattern) or extracts to `__fixtures__/scan-run-detail-e2e.ts`.

- [ ] **Step 3: Run tests**

Run: `npm test -C frontend -- ScanRunDetail.e2e.test.tsx --run`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/scan-runs/ScanRunDetail.e2e.test.tsx
git commit -m "test(frontend): ScanRunDetail e2e — header + targets + findings + evidence"
```

---

### Phase 3 exit criteria

- [ ] `npm test -C frontend -- --run` green; full suite.
- [ ] `npm test -C frontend -- --coverage --run` shows 100 % on all 6C files.
- [ ] No file over 200 lines (`ScanRunDetail.tsx` ~75, both panels ~70 each, integration test ~180, e2e ~110).
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
