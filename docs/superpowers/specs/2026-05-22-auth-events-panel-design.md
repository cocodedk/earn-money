# Auth events panel — target result page

Slice: `feat/em-frontend-auth-events-panel`
Decided with: agent-em-backend (chat-bus brainstorm, 2026-05-22)

## Summary

The target result page (`/targets/:targetId/results`) lists all events for the target in
`TargetEventsTable` (paginated, page size 50). Three `EventType`s emitted by the Phase 2
auth runners — `auth.probe_refused`, `auth.fixture_required`, `auth.finding_candidate` —
need a dedicated triage surface so the operator can see them at a glance even after the
event feed has scrolled them off page 1.

This slice adds `TargetAuthEventsPanel`, rendered above `TargetEventsTable`. It pulls auth
events through a dedicated paginated query, renders each as a coloured expand-in-place pill,
and stays out of the way when the target has none.

## Scope

In:
- One new component `TargetAuthEventsPanel` rendered on `TargetResult`.
- One new query hook `useTargetAuthEventsQuery(targetId)`.
- One backend-coupled change: depends on `EventViewSet` accepting multi-value `?type=`
  (em-backend ships this on main before the query hook lands — confirmed 2026-05-22).
- Tests: unit tests for the panel, integration tests through `TargetResult`, e2e smoke
  via `App.e2e.target-result.test.tsx`.

Out:
- No new backend endpoint (multi-value `?type=` is already in flight on em-backend's side).
- No deep-link from pills (`auth.fixture_required` → fixture page, etc.). Expand-in-place
  is the only interaction. Deep-links are a future slice once those destination pages exist.
- No second-page navigation. "+N more" is a text-link to the full events feed below.
- No SSE / live updates for the panel. React Query refetch matches the rest of the page.

## Canonical event types

From `backend/apps/events/test_types.py` on origin/main:

| Enum                            | Value                       | Severity |
|---------------------------------|-----------------------------|----------|
| `AUTH_PROBE_REFUSED`            | `"auth.probe_refused"`      | warning  |
| `AUTH_FIXTURE_REQUIRED`         | `"auth.fixture_required"`   | info     |
| `AUTH_FINDING_CANDIDATE`        | `"auth.finding_candidate"`  | alert    |

The values are the strings used in the `?type=` query parameter.

## Page placement

`TargetResult.tsx` body becomes:

```
PageHeader
MetaList
TargetScanRunsTable
TargetFindingsPanel
TargetEvidencePanel
TargetAuthEventsPanel    ← new, between Evidence and Events
TargetEventsTable
```

The new panel sits immediately above the full events table — the operator's eye lands on
it before the long table below. When the panel is empty (see below) it omits itself and
the page collapses back to the current layout.

## Data fetching

```ts
function useTargetAuthEventsQuery(targetId: string) {
  return useQuery({
    queryKey: ["target", targetId, "auth-events"],
    queryFn: () => api.get<Paginated<Event>>(
      `/api/events/?target=${targetId}`
      + `&type=auth.probe_refused`
      + `&type=auth.fixture_required`
      + `&type=auth.finding_candidate`
    ),
    staleTime: 30_000,
  });
}
```

Single call, multi-value `?type=`. Backend collapses the 3 types into `type__in` on the
queryset.

Response is paginated `{ count, next, previous, results: Event[] }`, page size 50.

The endpoint (`EventViewSet`, commit `663ff52` on origin/main) returns results in
**oldest-first** `created_at` order. The query hook reverses the `results` array
client-side so the panel renders newest-first (see UI surface below). The hook returns
the reversed list — consumers don't re-sort.

## UI surface

`TargetAuthEventsPanel`:

- If `count === 0` → render nothing. The whole `<section>` is omitted.
- Otherwise render a `TargetSection`-style heading ("Auth events for target — N total")
  and a flex-wrapped list of `AuthEventPill` rows, in `created_at` descending order
  (newest first).
- Below the list, if `next !== null`, render a footer hint: `+{count - results.length} more in the full events feed below.` (Plain text, no scroll target — `TargetEventsTable` is directly below the panel, the operator can see it. Adding an HTML `id` to the existing `TargetSection` would expand scope.)

`AuthEventPill`:

- Three visual variants driven by `event.type`:
  - `auth.probe_refused` → amber (warning) — RoE / policy refusal.
  - `auth.fixture_required` → blue (info) — needs operator config.
  - `auth.finding_candidate` → red (alert) — possible vuln pending verify.
- Collapsed: type-coloured chip, type label (humanised — e.g. `Probe refused`), timestamp.
- Click / Enter / Space toggles `expanded`. Expanded state reveals `event.message`
  and a `<details>`-style payload view (pretty-printed JSON of `event.payload`).
- Reuses tokens from `StatusBadge.module.css` and CSS vars for the colour variants.
  No new colour values — picks from existing severity tokens.
- ARIA: pill is a `button` (`aria-expanded`), expanded region is `aria-hidden` when
  collapsed. Keyboard reachable; focus visible.

## Empty state

If `count === 0`, the panel renders nothing — `TargetResult` simply doesn't show a section.
This matches `TargetFindingsPanel` / `TargetEvidencePanel` behaviour: no surface when
nothing to triage.

The empty case is exercised by an integration test (target with no auth events → panel
not in DOM).

## Acceptance criteria

- A target with at least one auth event renders `TargetAuthEventsPanel` above
  `TargetEventsTable` on `/targets/:id/results`.
- A target with zero auth events does NOT render the panel; the page looks identical to
  the pre-slice layout.
- Pills are coloured per the severity table above.
- Click / Enter / Space on a pill toggles expand, showing `event.message` and payload.
- When `next !== null`, the "+N more in the full events feed below." footer hint is
  present (plain text, no scroll behaviour).
- 100% line + branch coverage on the new files (panel, pill, query hook).
- No new lints, no tsc errors, no a11y regressions.

## TDD checklist (test files to write first)

- `frontend/src/features/targets/TargetResult/TargetAuthEventsPanel.test.tsx`
  - renders nothing when query returns `count: 0`
  - renders N pills when query returns N results
  - newest-first ordering
  - "+N more" footer hint when `next !== null`, hidden when `null`
  - each event type renders the correct severity variant
- `frontend/src/features/targets/TargetResult/AuthEventPill.test.tsx`
  - collapsed shows type label + timestamp
  - click toggles expanded
  - keyboard: Enter and Space both toggle
  - expanded reveals `event.message` and payload
  - `aria-expanded` reflects state
- `frontend/src/features/targets/api.test.ts`
  - `useTargetAuthEventsQuery` builds the correct URL with three `?type=` params
  - reverses the backend's oldest-first results to newest-first (idempotent on
    single-item and empty results)
- `frontend/src/features/targets/TargetResult.test.tsx`
  - integration: panel appears between Evidence and Events sections when populated
- `frontend/src/App.e2e.target-result.test.tsx`
  - e2e: navigate to a target with auth events, verify pill is present and expandable

## Out of scope / followups

- Multi-value `?type=` extension on `EventViewSet` — em-backend's stack.
- Deep-link routing from pills — needs destination pages (RoE editor, fixture config,
  finding draft). Tracked separately.
- Live updates via SSE — current refetch-on-focus is enough; add later if operators
  report stale-pills annoyance.
- Bulk dismiss / mark-acknowledged — not yet a product concept.

## Open questions

None — all resolved with em-backend on 2026-05-22.
