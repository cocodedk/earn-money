# Scan Run Detail 6D — Live events SSE panel

> **For agentic workers:** REQUIRED SUB-SKILLS: `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` for task orchestration; `superpowers:test-driven-development` for every implementation task (failing test first, no production code without a failing test); `superpowers:dispatching-parallel-agents` for the parallelizable scaffolding cluster in Phase 1 (Tasks 1-4). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the read-only Live events panel below the Findings + Evidence panels on `/scan-runs/:id`. The panel opens an `EventSource` against the per-scan-run SSE endpoint on mount, renders one row per event (time / level / target / event_type / message), maintains a sticky connection-status indicator visible **regardless of buffer size** (status pill always shown above an always-rendered table region so accumulated events stay visible during reconnect/closed states), supports the three required controls (auto-scroll toggle / clear local view / reconnect), and falls back to a 2 s polling loop on the REST events endpoint when the SSE connection enters a terminal error state.

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

**Backend lock (confirmed by em-backend 2026-05-20, all 4 contract answers):**
- **SSE endpoint:** `GET /sse/scan-runs/<uuid:scan_run_id>/events/` — wired in `backend/config/urls.py:38`, view at `backend/apps/events/views.py`.
- **SSE envelope:** standard 3-line SSE frame per emit: `id: <event.id>\nevent: <event.type>\ndata: <full EventSerializer JSON>\n\n`. Both `id:` and `event:` lines populated. Closing frame on terminal scan-run status (`done` / `stopped` / `failed`): `: stream-closed\n\n`.
- **Polling fallback REST:** `GET /api/scan-runs/<uuid>/events/` (DRF nested action on `ScanRunViewSet` at `backend/apps/scans/views.py:119`), DRF-paginated `EventSerializer` output per project `PAGE_SIZE = 50`.
- **`Last-Event-ID` honored:** server resolves the anchor event by ID, then resumes with `created_at > anchor.created_at`. Unknown anchor or unparseable header → fresh start (no error). Server-side poll interval is 0.5s; client polling interval is 2s (defined in Phase 1 Task 7).
- **Active-status semantics:** `isRunActive(status)` is the canonical check (`frontend/src/features/scan-runs/api.ts:15`). Currently returns `true` only for `running` or `stopping` — `paused` returns `false`, meaning the SSE connection closes on pause and reopens on resume. This is the existing 6B/6C contract and 6D follows it.

**Reservoir reference:** `origin/feat/em-frontend-slice-2` ships `useScanRunEvents` SSE hook + `LiveEventsPanel`. 6D **does not** merge or depend on that branch — we build fresh on `feat/em-frontend-6C` tip per [[project-slice-2-3-reservoirs]] non-merge rule. Reservoir is read-only inspiration; verify shapes against the current contract above before lifting any code.

## Phase index

| Phase | File | Ships |
|-------|------|-------|
| 1 | [phase-1-types-and-hook.md](phase-1-types-and-hook.md) | `Event` type + level enum; `useScanRunEvents(scanRunId, options)` hook with SSE primary + polling fallback + reconnect; MSW handlers for the SSE endpoint and the events REST endpoint |
| 2 | [phase-2-panel.md](phase-2-panel.md) | `ScanRunLiveEventsPanel` component (raw `<table>` mirroring 6B + 6C panels), per-row `data-testid`, sticky connection-status indicator, auto-scroll + clear + reconnect controls |
| 3 | [phase-3-wire-app-e2e.md](phase-3-wire-app-e2e.md) | Wire panel into `ScanRunDetail` below Findings + Evidence; integration tests for SSE happy path / disconnect-reconnect / SSE-failed-polling-fallback / terminal-status / cancel-and-clear; E2E that asserts header + target table + findings + evidence + live events all render |

## Definition of done

- 100 % line + branch coverage on new and modified files.
- `npm test`, `npm test -- --coverage`, `npm run build` all green.
- `/simplify` runs after **each** commit (per-commit gate per CLAUDE.md commit-hygiene rule). Each round's fixes are their own commit.
- No new or modified file over 200 lines. `App.e2e.test.tsx` pre-existing 305-line state is already over the 200-line cap and is the deferred-refactor target for the table-primitive cleanup slice that follows 6D. Phase 3 Task 6 extends it by **one additional case** (mirroring 6C's pattern); the file is **not split inside 6D** — split lands in the cleanup slice along with the `<Table>` primitive lift.
- Operator can open `/scan-runs/:id` and see events streaming live within ~250 ms of backend emit while the parent run is `running`. Disconnecting the network (DevTools offline) shows the disconnected status indicator and then re-streams on restore.
- SSE reconnect: exponential backoff capped at 30 s; max 5 attempts before falling back to polling.
- Polling fallback: 2 s interval, dedupe by `event.id`, **stops when parent run enters terminal status, `livePolling` flips false, or the component unmounts**. No automatic retry back to SSE — once we fall back, we stay in polling for this scan run's lifetime (revisit if/when SSE reliability needs measuring; Last-Event-ID makes mid-stream recovery cheap if we add it later).
- **Rollback kill switch:** localStorage flag `disable_live_events`. **Strict contract:** value `"1"` (string) means enabled; anything else (including `"0"`, `"true"`, `null`, missing key) means disabled-flag-is-off. Set with `localStorage.setItem("disable_live_events", "1")` and reload; remove with `localStorage.removeItem("disable_live_events")` and reload. When enabled, panel skips opening SSE / polling; status pill renders `disabled`; buffer stays empty. Settable via DevTools or operator runbook for triaging flaky deployments without a code revert. Phase 3 Task 7 spec-review verifies the kill switch path.
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
- Controls testids: `data-testid="events-autoscroll-toggle"` / `data-testid="events-clear-local"` / `data-testid="events-reconnect"`.
- Inline timestamp formatter: `fmt(ts) = ts ? new Date(ts).toLocaleTimeString() : "—"` (HH:MM:SS for the live tail; **differs from 6C's date-only** because the events panel is a real-time view).

## Naming conventions

| Concept | Identifier |
|---------|------------|
| Type for one event | `Event` (in `types/api.ts`) |
| Type for event level | `EventLevel` (in `types/api.ts`) |
| SSE hook (events, scan-run-scoped) | `useScanRunEvents(scanRunId, options)` where `options = { livePolling?: boolean; maxBuffer?: number }` |
| Polling-fallback query key | `scanRunEventsKey(scanRunId) = [...SCAN_RUNS_KEY, scanRunId, "events"]` |
| Panel component | `ScanRunLiveEventsPanel` |
| Panel file | `frontend/src/features/scan-runs/ScanRunLiveEventsPanel.tsx` |
| Hook file | `frontend/src/features/scan-runs/useScanRunEvents.ts` |
