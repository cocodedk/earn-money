# Phase 2 — `ScanRunLiveEventsPanel` component

**Goal:** Ship the read-only events panel that consumes `useScanRunEvents` and renders the SSE tail with connection-status indicator, auto-scroll toggle, clear, and reconnect controls. Raw `<table>` mirror of 6B + 6C panels (the shared-`<Table>` primitive lift is deferred to a follow-up slice).

**Reference patterns:**
- `ScanRunFindingsPanel` and `ScanRunEvidencePanel` (shipped in 6C) are the structural template.
- Connection-status indicator is **new** — design follows the `ConnectionPill` pattern from `frontend/src/components/ConnectionPill/ConnectionPill.tsx` (folder layout: `ConnectionPill.tsx` + `ConnectionPill.module.css` + `ConnectionPill.test.tsx` + `index.ts` barrel). Mirror this layout for the new status indicator if it grows beyond a single file.

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
- Header: title "Live events" + sticky `<span data-testid="events-connection-status">{status}</span>` always visible above the table region (one of `connecting | connected | reconnecting | polling-fallback | closed | disabled`).
- **Buffer visibility:** the table region is **always rendered** when the buffer is non-empty, regardless of `status`. Accumulated events stay visible during `reconnecting` or `closed` (codex revision: `reconnecting/closed` must not hide already-received events).
- Empty-buffer hints (rendered above the table region, never replacing the table when it has rows):
  - `connecting` + empty: "Connecting…" hint.
  - `reconnecting` + empty: "Reconnecting…" hint.
  - `polling-fallback` + empty: "SSE unavailable — polling for events." hint.
  - `connected` + empty: "No events yet" hint.
  - `closed` + empty: "Disconnected" hint.
  - `disabled` (localStorage kill switch active): "Live events disabled (set `localStorage.disable_live_events=0` and reload to re-enable)." hint.

**Test matrix:**
1. Renders title + status pill in every status (including `disabled` via localStorage kill switch).
2. `connecting` + empty buffer → "Connecting…" hint, status pill present, no table.
3. `connected` + empty → "No events yet" hint.
4. `connected` + 1 event → table renders with one row + status pill present, no hint.
5. `reconnecting` + 3 events → **table still renders with those 3 rows**, status pill shows `reconnecting`, no hint (table not hidden by status).
6. `closed` + 3 events → **table still renders with those 3 rows**, status pill shows `closed`, no hint.
7. `polling-fallback` + events → table renders, status pill shows fallback label.
8. `disabled` + empty → kill-switch hint shown, no table, status pill `disabled`.

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
3. Non-null `target` → first 8 hex chars rendered (asserts the truncation format from the §Behaviour bullet).
4. Each level renders with expected colour class.
5. `event-row-{id}` testid on every row.
6. Buffer cap eviction: emit 501 events with `maxBuffer=500` → 500 rows render, oldest evicted.
7. Ordering across `clear()` + re-emit: emit 3 events → clear → emit 2 more → 2 new events render at the top of the now-empty table (no carry-over from before clear).

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

**JSDOM note:** JSDOM does not implement `Element.prototype.scrollIntoView`. Tests must stub it via `vi.spyOn(Element.prototype, 'scrollIntoView').mockImplementation(() => {})` in `beforeEach`, restored in `afterEach`. Without the stub the test will throw `TypeError: el.scrollIntoView is not a function`. Same applies to `scrollTop`/`scrollHeight`/`clientHeight` reads for the "user scrolled up" detection — assert via direct property write rather than user-event simulation.

**Test matrix:**
1. Toggle button click flips state and label.
2. With `on` and new event → `scrollIntoView` spy called on last row.
3. With `off` and new event → spy not called.
4. Manual scroll up (simulated via setting `scrollTop` and dispatching `scroll`) → toggle flips to `off` automatically; spy not called on subsequent emit.

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
