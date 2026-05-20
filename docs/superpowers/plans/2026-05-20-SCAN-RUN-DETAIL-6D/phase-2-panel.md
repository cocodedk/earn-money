# Phase 2 — `ScanRunLiveEventsPanel` component

**Goal:** Ship the read-only events panel that consumes `useScanRunEvents` and renders the SSE tail with connection-status indicator, auto-scroll toggle, clear, and reconnect controls. Raw `<table>` mirror of 6B + 6C panels (the shared-`<Table>` primitive lift is deferred to a follow-up slice).

**Reference patterns:**
- `ScanRunFindingsPanel` and `ScanRunEvidencePanel` (shipped in 6C) are the structural template.
- Connection-status indicator is **new** — design follows the `ConnectionPill` pattern from `frontend/src/components/ConnectionPill.tsx` (status-coloured chip with text label).

---

### Task 1: Component skeleton + connection-status indicator

**Files:**
- Create: `frontend/src/features/scan-runs/ScanRunLiveEventsPanel.tsx` (~120 lines target; cap 200)
- Test: `frontend/src/features/scan-runs/ScanRunLiveEventsPanel.status.test.tsx`

**Surface:**

```tsx
type Props = { scanRunId: string; livePolling: boolean };

export function ScanRunLiveEventsPanel({ scanRunId, livePolling }: Props): JSX.Element;
```

**Behaviour:**
- Header: title "Live events" + `<span data-testid="events-connection-status">{status}</span>` (one of `connecting | connected | reconnecting | polling-fallback | closed`).
- Empty state: `<p>No events yet</p>` when `events.length === 0` and status is `connected | polling-fallback`.
- Status-only states render their own messages (no table): `connecting` → "Connecting…", `reconnecting` → "Reconnecting…", `closed` → "Disconnected".

**Test matrix:**
1. Renders title + status pill.
2. `connecting` shows spinner-style message, no table.
3. `connected` + empty buffer → "No events yet".
4. `connected` + 1 event → table renders with one row.
5. `reconnecting` shows "Reconnecting…", no table.
6. `polling-fallback` + events → table renders, status pill shows fallback label.
7. `closed` shows "Disconnected".

**Commit:** `feat(frontend): ScanRunLiveEventsPanel skeleton + status indicator`.

---

### Task 2: Event rows + per-row testid

**Files:**
- Modify: `frontend/src/features/scan-runs/ScanRunLiveEventsPanel.tsx`
- Test: `frontend/src/features/scan-runs/ScanRunLiveEventsPanel.rows.test.tsx`

**Behaviour:**
- One `<tr data-testid="event-row-{id}">` per event in buffer order (oldest at top, newest at bottom).
- Columns: time / level / target / event_type / message.
- `fmt(ts) = ts ? new Date(ts).toLocaleTimeString() : "—"` (HH:MM:SS for the live tail).
- `target` column: `target` UUID short form (first 8 hex) or "—" when null (scan-run-scoped events).
- `level` column: text + colour (debug=gray, info=blue, warning=amber, error=red). Use Tailwind utility classes.

**Test matrix:**
1. 3 events render in order with correct columns.
2. Null `target` → "—".
3. Each level renders with expected colour class.
4. `event-row-{id}` testid on every row.
5. Buffer cap eviction: emit 501 events with `maxBuffer=500` → 500 rows render, oldest evicted.

**Commit:** `feat(frontend): ScanRunLiveEventsPanel event rows + level colours`.

---

### Task 3: Auto-scroll toggle

**Files:**
- Modify: `frontend/src/features/scan-runs/ScanRunLiveEventsPanel.tsx`
- Test: `frontend/src/features/scan-runs/ScanRunLiveEventsPanel.autoscroll.test.tsx`

**Behaviour:**
- `data-testid="events-autoscroll-toggle"` button: text alternates "Auto-scroll: on" / "Auto-scroll: off". Default `on`.
- When `on` and new events arrive: scroll the scrollable container to the bottom (use `scrollIntoView({ block: 'end' })` on the last row).
- When the user scrolls up manually (detect `scrollTop < scrollHeight - clientHeight - threshold`): toggle to `off` automatically.
- When `off`: no auto-scroll on new events.

**Test matrix:**
1. Toggle button click flips state and label.
2. With `on` and new event → `scrollIntoView` called on last row.
3. With `off` and new event → no scroll.
4. Manual scroll up → toggle flips to `off` automatically.

**Commit:** `feat(frontend): ScanRunLiveEventsPanel auto-scroll toggle`.

---

### Task 4: Clear + Reconnect controls

**Files:**
- Modify: `frontend/src/features/scan-runs/ScanRunLiveEventsPanel.tsx`
- Test: `frontend/src/features/scan-runs/ScanRunLiveEventsPanel.controls.test.tsx`

**Behaviour:**
- `data-testid="events-clear-local"` button → calls `clear()` from the hook; buffer empties; backend events untouched per umbrella spec line 92.
- `data-testid="events-reconnect"` button → calls `reconnect()` from the hook; status flips back through `connecting → connected`.
- Both buttons rendered regardless of status (the hook itself no-ops when not applicable).

**Test matrix:**
1. `clear` button → `clear()` called once, buffer emptied in next render.
2. `reconnect` button → `reconnect()` called once, status transitions.
3. Both buttons present in all status states.

**Commit:** `feat(frontend): ScanRunLiveEventsPanel clear + reconnect controls`.

---

### Phase 2 exit criteria

- [ ] `npm test -C frontend -- --run` green (Phase-2 tests + Phase-1 + 311 pre-existing).
- [ ] `npm test -C frontend -- --coverage --run` 100 % on `ScanRunLiveEventsPanel.tsx`.
- [ ] Component file under 200 lines (split helpers into `ScanRunLiveEventsPanel/EventRow.tsx` + `ScanRunLiveEventsPanel/StatusIndicator.tsx` if needed).
- [ ] `/simplify` round clean after each of the 4 commits.
