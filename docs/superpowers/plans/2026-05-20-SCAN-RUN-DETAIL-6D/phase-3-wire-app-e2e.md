# Phase 3 — Wire panel into `ScanRunDetail` + integration + E2E

**Goal:** Mount `ScanRunLiveEventsPanel` below the Findings + Evidence panels on `/scan-runs/:id`. Confirm SSE end-to-end happy path, disconnect-reconnect, polling fallback, terminal-status cleanup, and full-page E2E.

**Unblocked.** Em-backend confirmed all 4 contract answers on 2026-05-20 (SSE route, envelope, polling REST endpoint, `Last-Event-ID` honored). All URLs are now fixed in `00-overview.md` §Backend lock. Phase 3 may proceed once Phase 1 + Phase 2 land.

---

### Task 1: Mount panel in `ScanRunDetail`

**Files:**
- Modify: `frontend/src/features/scan-runs/ScanRunDetail.tsx`
- Test: `frontend/src/features/scan-runs/ScanRunDetail.test.tsx` (extend existing)

**Behaviour:**
- Render `<ScanRunLiveEventsPanel scanRunId={id} livePolling={isRunActive(run.status)} />` below the existing `<ScanRunEvidencePanel />`.
- `livePolling` derived from the existing `isRunActive` helper (`frontend/src/features/scan-runs/api.ts:15`). It currently returns `true` only for `running` or `stopping`. **`paused` returns `false`** — when the operator pauses a run, the SSE connection closes (per Task 5 behaviour); resuming reopens it via the `livePolling` flip false → true. This matches Findings + Evidence panel behaviour from 6C and is the canonical contract.
- Order on page: header → target table → findings → evidence → live events.

**Test:** new render assertion — `events-connection-status` testid present under the existing header + target + findings + evidence assertions.

**Commit:** `feat(frontend): mount LiveEventsPanel in ScanRunDetail`.

---

### Task 2: Integration — SSE happy path

**Files:**
- Create: `frontend/src/features/scan-runs/ScanRunDetail.events.happy.test.tsx`

**Test:**
- Render `<ScanRunDetail />` with a `running` scan run.
- `installMockEventSource()` in beforeEach.
- Assert: EventSource opened against expected URL; status pill shows `connected`; emitting a fixture event renders an `event-row-{id}` row in the panel.

**Commit:** `test(frontend): ScanRunDetail SSE happy path integration`.

---

### Task 3: Integration — disconnect-reconnect

**Files:**
- Create: `frontend/src/features/scan-runs/ScanRunDetail.events.reconnect.test.tsx`

**Test:**
- SSE fails → status pill `reconnecting` → wait for backoff (`vi.advanceTimersByTimeAsync(1000)`) → new EventSource opened → emit → row appears.

**Commit:** `test(frontend): ScanRunDetail SSE disconnect-reconnect integration`.

---

### Task 4: Integration — polling fallback

**Files:**
- Create: `frontend/src/features/scan-runs/ScanRunDetail.events.polling-fallback.test.tsx`

**Test:**
- SSE fails 5 times → status pill `polling-fallback` → polling tick hits `/api/scan-runs/<uuid>/events/` (with `Last-Event-ID` header set to the newest buffered event id, or omitted if buffer empty) → rows appear from REST response.
- MSW handler returns fixture events; assert dedupe across ticks.

**Commit:** `test(frontend): ScanRunDetail SSE polling-fallback integration`.

---

### Task 5: Integration — terminal status cleanup

**Files:**
- Create: `frontend/src/features/scan-runs/ScanRunDetail.events.terminal.test.tsx`

**Test:**
- `running` → SSE connected, status `connected`.
- Cancel the run (or refetch returns `succeeded` / `done` status) → `livePolling` flips to false → EventSource closed → status pill `closed`; previously buffered events **stay visible** in the table.
- Pause path: `running` → `paused` → `isRunActive` returns false → EventSource closed → status pill `closed`. Resume back to `running` → fresh EventSource opens, status `connecting → connected`. Buffer is **preserved across pause/resume** (no implicit clear).
- Kill-switch path: with `localStorage.setItem("disable_live_events", "1")` set before render → no EventSource opened, status pill `disabled`, the disabled-hint message is rendered. No SSE network activity.
- Mirrors the terminal-flush pattern from 6B + 6C target-runs/findings/evidence tests.

**Commit:** `test(frontend): ScanRunDetail SSE terminal + pause + kill-switch integration`.

---

### Task 6: E2E — full page including events

**Files:**
- Modify: `frontend/src/App.e2e.test.tsx` — extend the existing ScanRunDetail E2E case with the events assertion. File is at **305 lines pre-edit** (already over the 200-line cap); 6D adds one case (~10–15 lines) and does **not** split the file. The split lands in the table-primitive cleanup slice that follows 6D, per [`00-overview.md`](00-overview.md) §Definition of done.

**Test:**
- Navigate to `/scan-runs/<id>` for a running run.
- Assert: header testid present; target table testid present; findings panel testid present; evidence panel testid present; events panel testid present; emit one mock SSE event; assert event-row testid present.

**Commit:** `test(frontend): ScanRunDetail e2e — full page with live events`.

---

### Task 7: Spec-review pass

**Files:**
- Create: `docs/superpowers/spec-reviews/2026-05-20-6D-scan-run-detail-live-events.md`

Read the umbrella spec (sections 6 §Live events panel + 12 §Live events) end-to-end. Use the **seven CLAUDE.md spec-review audit dimensions** as report headings (the dimensions are codified in [`CLAUDE.md`](../../../../CLAUDE.md) under "After implementing a cookbook stub, run the spec-review pass before marking it done."; backend reference reports live in the canonical earn-money repo's `docs/superpowers/spec-reviews/` directory):

1. **Detection-logic coverage** — every signal/state the spec lists (SSE message arrival, connection-status transitions, reconnect path, polling fallback engagement, auto-scroll on/off, clear semantics) is reachable in code.
2. **Persistence contract** — N/A for read-only panel (no writes); explicitly note this.
3. **Pass/fail positive assertions** — each row column rendered, each control present, each connection status reachable.
4. **Pass/fail negative assertions** — `Clear local view` does NOT issue any network call (regression test in Phase 1 Task 5 item 6); panel does not mutate backend events; no `DELETE` requests issued anywhere.
5. **Acceptance criteria** — connection-status visible, reconnect works, polling fallback engages after 5 SSE failures, newest event at bottom (consistent across emit + clear + re-emit), auto-scroll toggle present and defaults to `on`.
6. **Idempotence / determinism / bounded** — buffer cap exercised; dedupe-by-id exercised; no unbounded growth.
7. **Transport-error tolerance** — SSE error → reconnect; 5 reconnect failures → polling fallback; polling tick error → handled (no crash).

Record any deferrals in the report; create follow-up tasks for non-deferrals.

**Commit:** `docs(stubs): spec-review audit for 6D live-events panel`.

---

### Phase 3 exit criteria

- [ ] `npm test -C frontend -- --run` green — 311 pre-existing + Phase 1 + Phase 2 + Phase 3.
- [ ] `npm test -C frontend -- --coverage --run` 100 % on all 6D files.
- [ ] `npm run -C frontend build` green.
- [ ] `/simplify` clean after each of the 7 commits.
- [ ] Spec-review report committed.
- [ ] Single peer ping to em-backend at slice completion (chat-noise-floor rule).
- [ ] All 6D files under 200 lines.
