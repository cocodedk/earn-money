# Scan Run Detail 6D — Live events SSE panel

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the read-only Live events panel below the Findings + Evidence panels on `/scan-runs/:id`. The panel opens an `EventSource` against the per-scan-run SSE endpoint on mount, renders one row per event (time / level / target / event_type / message), maintains a sticky connection-status indicator, supports the three required controls (auto-scroll toggle / clear local view / reconnect), and falls back to a 2 s polling loop on `/api/events/?scan_run=<uuid>` when the SSE connection enters a terminal error state.

**Spec source:** [`../../specs/2026-05-18-MVP-GUI/06-scan-run-detail.md`](../../specs/2026-05-18-MVP-GUI/06-scan-run-detail.md) §Live events panel (lines 59–92) and [`../../specs/2026-05-18-MVP-GUI/12-live-events.md`](../../specs/2026-05-18-MVP-GUI/12-live-events.md). **Note:** §12 documents a stale SSE message shape (`event_type`/`scan_run_id`/`target_id`); the **current backend contract is `type`/`scan_run`/`target` + adds `subject_type`/`subject_id`** per [[project-slice-2-3-reservoirs]] and 6B's existing target-runs contract.

**Event shape (current, authoritative):**

```ts
{
  id: string,
  type: string,               // event_type in spec — renamed at backend
  scan_run: string,           // uuid
  target: string | null,      // uuid, null for scan-run-scoped events
  subject_type: string,       // discriminator: "scan_run" | "scan_target_run" | …
  subject_id: string,         // uuid of the subject row
  level: "debug" | "info" | "warning" | "error",
  message: string,
  data: Record<string, unknown>,
  created_at: string,         // ISO 8601
}
```

**Backend lock:** em-backend on `main` ships:
- SSE endpoint at `/api/events/scan-runs/<uuid>/stream/` per the squash-merged Phase 1 commit `feat(events): SSE endpoint for live scan-run event streaming`. **Verify route shape in Phase 1 implementation;** correct in plan if it differs.
- REST endpoint at `/api/events/?scan_run=<uuid>` (read-only) per the squash-merged `feat(api): read-only Events / Findings / Evidence endpoints + nested actions`. DRF `PAGE_SIZE = 50` applies.

**Reservoir reference:** `origin/feat/em-frontend-slice-2` ships `useScanRunEvents` SSE hook + `LiveEventsPanel`. 6D **does not** merge or depend on that branch — we build fresh on `feat/em-frontend-6C` tip per [[project-slice-2-3-reservoirs]] non-merge rule. Reservoir is read-only inspiration; verify shapes against the current contract above before lifting any code.

## Phase index

| Phase | File | Ships |
|-------|------|-------|
| 1 | [phase-1-types-and-hook.md](phase-1-types-and-hook.md) | `Event` type + level enum; `useScanRunEvents(scanRunId)` hook with SSE primary + polling fallback + reconnect; MSW handlers for the SSE endpoint and the events REST endpoint |
| 2 | [phase-2-panel.md](phase-2-panel.md) | `ScanRunLiveEventsPanel` component (raw `<table>` mirroring 6B + 6C panels), per-row `data-testid`, sticky connection-status indicator, auto-scroll + clear + reconnect controls |
| 3 | [phase-3-wire-app-e2e.md](phase-3-wire-app-e2e.md) | Wire panel into `ScanRunDetail` below Findings + Evidence; integration tests for SSE happy path / disconnect-reconnect / SSE-failed-polling-fallback / terminal-status / cancel-and-clear; E2E that asserts header + target table + findings + evidence + live events all render |

## Definition of done

- 100 % line + branch coverage on new and modified files.
- `npm test`, `npm test -- --coverage`, `npm run build` all green.
- `/simplify` runs after **each** commit (per-commit gate per CLAUDE.md commit-hygiene rule). Each round's fixes are their own commit.
- No new or modified file over 200 lines. `App.e2e.test.tsx` pre-existing 217-line state stays untouched (deferred refactor — to be addressed in the table-primitive cleanup slice that follows 6D).
- Operator can open `/scan-runs/:id` and see events streaming live within ~250 ms of backend emit while the parent run is `running`. Disconnecting the network (DevTools offline) shows the disconnected status indicator and then re-streams on restore.
- SSE reconnect: exponential backoff capped at 30 s; max 5 attempts before falling back to polling.
- Polling fallback: 2 s interval, dedupe by `event.id`, stops when SSE reconnects or parent run enters terminal status.
- Newest event at **bottom** (matching natural log-tail reading order); auto-scroll defaults to **on** but disables automatically when the user scrolls up.
- Single peer ping to em-backend at slice completion (chat-noise-floor rule).

## Out of scope for 6D

- **Event detail modal / drill-down** — rows are read-only; no `<Link to="/events/:id">`. Deferred to a future slice if/when event-detail routes exist.
- **Filter UI** (by level, target, type) — local view is full unfiltered tail; filter dropdowns ship with the future standalone events page.
- **Backend persistence of "cleared" state** — `Clear local view` zeros the in-component buffer only; backend events are untouched per umbrella spec line 92.
- **Table primitive lift (`<Table>` with `rowTestId?` prop)** — deferred to a follow-up slice (`6E-table-primitive-cleanup`) so the refactor lands once across all four panels in one PR. This **changes** the 6C follow-up note that said "defer until 6D"; 6D ships the SSE panel only.

### Tracked follow-ups (do NOT do in 6D — record only)

- **Extract `useScanRunChildQuery<T>` for the polling-fallback path** — once 6D ships, the events polling-fallback hook is the fourth same-shape `useScanRun*Query` (target-runs + findings + evidence + events-polling). Right moment to extract is during the table-primitive cleanup slice. SSE primary path is a different hook signature and not part of the extraction.
- **Extract `formatCell.ts`** — `fmt(ts)` will now exist in four panel files. Lift to `frontend/src/lib/formatCell.ts` during the cleanup slice.
- **Extend shared `<Table>` with `rowTestId?: (row: T) => string`** — collapse all four raw-`<table>` copies into one primitive during the cleanup slice.
- **Consolidated `/scan-runs/:id/summary/` endpoint** — backend work to reduce poll-storm during running. Revisit after SSE coverage is verified in production.
- **Cookbook spec finishers** — 6D unblocks the per-finding live-event UX. Once a new cookbook stub lands on backend's side and emits Findings/Evidence/Events, frontend prep work is automatic (types stay shape-compatible).

## TDD rules

- Strict TDD on every step: failing test first, then implementation. No production code without a failing test.
- 100 % line + branch coverage on the production code path (frontend `src/`). Coverage gates measured by `npm test -- --coverage`.
- House style: per-row `data-testid="event-row-{id}"` (same convention as 6B + 6C).
- Connection-status indicator testid: `data-testid="events-connection-status"` with values `connecting` | `connected` | `reconnecting` | `polling-fallback` | `closed`.
- Controls testids: `data-testid="events-autoscroll-toggle"` / `events-clear-local"` / `events-reconnect"`.
- Inline timestamp formatter: `fmt(ts) = ts ? new Date(ts).toLocaleTimeString() : "—"` (HH:MM:SS for the live tail; **differs from 6C's date-only** because the events panel is a real-time view).

## Naming conventions

| Concept | Identifier |
|---------|------------|
| Type for one event | `Event` (in `types/api.ts`) |
| Type for event level | `EventLevel` (in `types/api.ts`) |
| SSE hook (events, scan-run-scoped) | `useScanRunEvents(scanRunId, livePolling)` |
| Polling-fallback query key | `scanRunEventsKey(scanRunId) = [...SCAN_RUNS_KEY, scanRunId, "events"]` |
| Panel component | `ScanRunLiveEventsPanel` |
| Panel file | `frontend/src/features/scan-runs/ScanRunLiveEventsPanel.tsx` |
| Hook file | `frontend/src/features/scan-runs/useScanRunEvents.ts` |
