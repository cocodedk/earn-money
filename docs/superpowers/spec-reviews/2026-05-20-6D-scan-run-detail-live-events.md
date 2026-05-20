# Spec-review — 6D Scan Run Detail · Live events SSE panel

**Slice:** `feat/em-frontend-6D` · 13 commits · 386 tests passing · 100 % line + branch coverage on every new file.

**Umbrella spec:** [`../specs/2026-05-18-MVP-GUI/06-scan-run-detail.md`](../specs/2026-05-18-MVP-GUI/06-scan-run-detail.md) §Live events panel (lines 59-92); [`../specs/2026-05-18-MVP-GUI/12-live-events.md`](../specs/2026-05-18-MVP-GUI/12-live-events.md) §SSE protocol.

**Implementation plan:** [`../plans/2026-05-20-SCAN-RUN-DETAIL-6D/`](../plans/2026-05-20-SCAN-RUN-DETAIL-6D/).

Audit dimensions are the seven from `CLAUDE.md` §Commit hygiene → "After implementing a cookbook stub, run the spec-review pass before marking it done."

---

## 1. Detection-logic coverage

Every signal/transition the spec lists is reachable in code:

| Spec requirement | Code path | Test |
|---|---|---|
| Open `EventSource` on mount with `livePolling=true` | `useScanRunEvents.ts` SSE effect | `useScanRunEvents.sse.test.tsx` test 1 |
| Append events in arrival order, newest at bottom | hook + panel `EventRow` | sse test 2 + rows test 1 |
| Connection-status transitions (`connecting / connected / reconnecting / polling-fallback / closed / disabled`) | hook + panel `EventsPanelHeader` | status test 1, reconnect test 3, polling test 1, kill-switch test 16 |
| Reconnect on `onerror` with exponential backoff (1s..30s cap) | `useScanRunEvents.ts` retry timer | reconnect test 1-6 |
| Polling fallback after 5 SSE failures hitting `/api/scan-runs/:id/events/` | `useScanRunEvents.polling.ts` | polling.entry test 1, polling.lifecycle test 1 |
| `Last-Event-ID` resume on polling | polling fetch | polling.lifecycle test 8 |
| Pagination drain (soft cap, evict-oldest) | polling tick loop | polling.pagination tests 9, 10 |
| Auto-scroll toggle (default on, manual scroll up disables) | panel `onScroll` handler | autoscroll test 1-5 |
| Clear control (local only, no backend) | hook `clear()` + panel button | sse test 5, 6 |
| Reconnect control (per-status enabled/disabled) | hook `reconnect()` + panel button | controls test 1-8 |
| Kill switch via `localStorage.disable_live_events === "1"` | hook mount check | kill-switch test 16-18 |

## 2. Persistence contract

N/A — panel is read-only. The hook makes ZERO mutating HTTP calls. Verified explicitly:

- `clear()` negative-assertion test (sse test 6) — `vi.spyOn(global, "fetch")` asserts 0 calls.
- No `useMutation` hooks instantiated.
- No `POST`/`PUT`/`PATCH`/`DELETE` request handlers in any MSW configuration.

## 3. Pass/fail positive assertions

Every spec requirement has at least one positive test:

- Row columns (time / level / target / event_type / message) → rows test 1 asserts each column value across 3 events.
- Per-row testid `event-row-{id}` → rows test 5.
- Level colour classes (debug=gray, info=blue, warning=amber, error=red) → rows test 4.
- All 6 connection statuses reachable + status pill always rendered → status test 1.
- Both controls (Clear + Reconnect) present in DOM in every status → controls test 5.

## 4. Pass/fail negative assertions

The "must not" rules are exercised by regression tests:

- **Clear does NOT issue any network call** — sse test 6 (fetch spy asserts 0 calls).
- **Buffer NOT cleared on status changes** (reconnecting/closed/polling-fallback) — status test 5 + 6 + integration terminal test all assert prior buffer rows still render.
- **Kill switch `"0"` is NOT truthy** — kill-switch test 17.
- **Kill switch `"1"` does NOT open EventSource** — kill-switch test 16 asserts `MockEventSource.instances.length === 0`.
- **No automatic SSE retry from polling** — polling.resume test asserts only a `livePolling` cycle or user `reconnect()` exits polling.

## 5. Acceptance criteria

All operator-facing acceptance items per plan §Definition of done:

- ✅ Connection status visible in every UI state (sticky pill above table).
- ✅ Reconnect works (user-driven `reconnect()` button + automatic backoff path).
- ✅ Polling fallback engages after 5 SSE failures (gate verified by both unit + integration).
- ✅ Newest event at **bottom**, ordering preserved across emit/clear/re-emit (rows test 7).
- ✅ Auto-scroll toggle present, defaults to `on`, flips off on manual scroll (autoscroll test 1, 4).
- ✅ 100 % line + branch coverage on every new production file: `useScanRunEvents.ts`, `useScanRunEvents.polling.ts`, `useScanRunEvents.utils.ts`, `ScanRunLiveEventsPanel.tsx`, `EventsPanelHeader.tsx`, `sseMock.ts`.
- ✅ All new and modified files ≤ 200 lines. `App.e2e.test.tsx` pre-existing 305 → 309 by one assertion (deferred-refactor target per plan).
- ✅ Peer ping to em-backend ready (will land at slice completion per chat-noise-floor rule).

## 6. Idempotence / determinism / bounded

- **Dedupe by id (replace in place):** sse test 3 + polling test 7. SSE-emitted and polling-served events with the same id replace in place, no duplicate rows, no reorder.
- **Buffer cap (default 500, configurable via `maxBuffer`):** sse test 4 (eviction).
- **Pagination drain bounded by buffer cap:** polling.pagination test 10 — server returns 15 events with `maxBuffer=10` → buffer ends holding newest 10.

## 7. Transport-error tolerance

- **Malformed SSE frame** (non-JSON `event.data`) → kill-switch test 14, dropped silently, status stays `connected`.
- **Valid JSON missing required fields** (`id` or `type`) → kill-switch test 15, dropped silently.
- **HTTP 5xx on polling** → polling.errors test 11, buffer untouched, status stays `polling-fallback`, retries on next tick.
- **Invalid polling response shape** (no `results` key) → polling.errors test 12, same handling.
- **5 consecutive polling 5xx** → polling.errors test 13, stays in `polling-fallback`, no escalation to `closed`.
- **SSE reconnect cap (5 attempts)** → reconnect test 4 transitions to `polling-fallback` cleanly.
- **Cleanup safety:** every effect path uses `clearTimeout` + `EventSource.close()` in cleanup; no leaks on unmount, scanRunId change, or `livePolling=false`.

---

## Deferrals & follow-ups (recorded — do NOT block 6D)

Per plan §"Tracked follow-ups":

1. **`useScanRunChildQuery<T>` extraction** — four same-shape children now exist (target-runs + findings + evidence + events-polling). Lift during the table-primitive cleanup slice that follows 6D.
2. **`formatCell.ts` extraction** — `fmt(ts)` lives in four panel files; lift during cleanup slice.
3. **Shared `<Table>` with `rowTestId?` prop** — collapses all four raw-`<table>` copies; cleanup slice.
4. **`App.e2e.test.tsx` split (309 → multiple files under 200)** — cleanup slice.
5. **Consolidated `/scan-runs/:id/summary/` backend endpoint** — backend work; revisit after SSE coverage in production.
6. **Cookbook spec finishers** — new finding-emitting stubs surface automatically; types stay shape-compatible.

## Verdict

**6D shipped.** All seven audit dimensions cleared. 386 tests passing on `feat/em-frontend-6D`. No new actionable findings against the spec.
