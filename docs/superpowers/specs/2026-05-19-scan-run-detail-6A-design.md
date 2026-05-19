# Scan Run Detail — slice 6A design (header + lifecycle)

**Date:** 2026-05-19
**Owner:** agent-em-frontend
**Reviewer:** agent-em-backend (ACK on 4-slice decomposition; pending ACK on this doc)
**Implements:** [`docs/superpowers/specs/2026-05-18-MVP-GUI/06-scan-run-detail.md`](2026-05-18-MVP-GUI/06-scan-run-detail.md) §Header

## Goal

First of four sub-slices that build the "most important MVP page" at `/scan-runs/:id`. This slice ships the page shell + header (Scan run ID, Project, Stub, Status, Started at, Finished at) and the lifecycle action buttons (Start/Pause/Resume/Stop). Closes the existing `<ComingSoon name="Scan Run Detail" />` route. Remaining sub-slices (6B target table, 6C findings + evidence panels, 6D SSE events panel) layer on top.

## Backend (no changes)

Live endpoints used by 6A:
- `GET /api/scan-runs/:id/` — `RetrieveModelMixin` already wired in `backend/apps/scans/views.py`. Returns the annotated `ScanRun` shape (with `target_run_count` + `findings_count`).
- `POST /api/scan-runs/:id/{start,pause,resume,stop}/` — already wired and consumed by `ScanRunsList`.

No backend changes for 6A.

## Scope

**In:**
- New route component at `/scan-runs/:id` showing the header + lifecycle buttons.
- A reusable `useScanRunActions(run)` hook extracted from `ScanRunsList.tsx`'s `ActionButtons` (peer micro-nit b — lift now, save churn in 6B).
- A new `useScanRunQuery(id)` hook for the single-record fetch.

**Out (deferred to 6B/6C/6D):**
- Target status table → 6B.
- Findings + Evidence panels → 6C.
- Live events SSE panel → 6D.
- The Open-target-result / Open-findings / Open-evidence actions on the per-target rows (those live inside 6B).

## Files

| File | State | Purpose |
|------|-------|---------|
| `frontend/src/features/scan-runs/api.ts` | modify | Add `useScanRunQuery(id)` for single-record fetch |
| `frontend/src/features/scan-runs/api.test.tsx` | modify | Cover the new hook |
| `frontend/src/features/scan-runs/useScanRunActions.ts` | new | Hook returning `{ visibleActions, handlers, isPending }` from the row's status |
| `frontend/src/features/scan-runs/useScanRunActions.test.tsx` | new | Per-status branch coverage |
| `frontend/src/features/scan-runs/ScanRunDetail.tsx` | new | The page (header + action buttons) |
| `frontend/src/features/scan-runs/ScanRunDetail.test.tsx` | new | Loading / 404 / error / per-status happy paths |
| `frontend/src/features/scan-runs/ScanRunsList.tsx` | modify | Replace inline `ActionButtons` with the lifted hook |
| `frontend/src/App.tsx` | modify | Swap `<ComingSoon name="Scan Run Detail" />` for `<ScanRunDetail />` |
| `frontend/src/App.e2e.test.tsx` | modify | Extend the scan-runs E2E with a `click Open → detail page renders header` step |

All new files target the 200-line cap.

## Hook contract — `useScanRunActions`

```ts
type Handlers = Record<LifecycleAction, () => void>;
type Result = {
  visibleActions: readonly LifecycleAction[];
  handlers: Handlers;
  isPending: boolean;  // true while any lifecycle mutation is in flight
};
export function useScanRunActions(run: ScanRun): Result;
```

The hook owns the four lifecycle mutation hook instances, the `VALID_ACTIONS[run.status]` lookup, and the per-action click handlers. `ScanRunsList`'s `ActionButtons` and `ScanRunDetail`'s header buttons consume the same return shape.

The `VALID_ACTIONS` + `ACTION_LABEL` tables live alongside the hook (currently inline in `ScanRunsList.tsx`). They become exports if a third consumer ever needs them.

## ScanRunDetail render shape

```tsx
const { id } = useParams();
const query = useScanRunQuery(id);

if (isHttpStatus(query.error, 404)) → "Scan run not found" + back-link
if (query.isError)                   → BackendUnreachableCallout
if (!query.data)                     → loading header

// happy:
const actions = useScanRunActions(query.data);
return (
  <>
    <PageHeader title={`Scan run · ${id.slice(0, 8)}`} action={<ActionButtonRow actions={actions} />} />
    <dl>
      ID short / Project (joined) / Stub (joined) / Status badge / Started at / Finished at
    </dl>
    {/* 6B, 6C, 6D land below this */}
  </>
);
```

Project + Stub joins reuse the existing cached `useProjectsQuery` + `useStubsQuery` + the `byKey` helper.

Reuses primitives: `PageHeader`, `BackendUnreachableCallout`, `Callout`, `Link`, `StatusBadge` (the scan-runs feature wrapper), `isHttpStatus`.

## Tests

**`api.test.tsx`** — adds:
- `useScanRunQuery(id)` resolves the ScanRun by id.
- `useScanRunQuery(undefined)` is disabled — no network call.

**`useScanRunActions.test.tsx`** — for each `ScanRunStatus`:
- `visibleActions` matches `VALID_ACTIONS[status]`.
- `handlers[action]` fires the corresponding mutation when called.
- `isPending` flips true while a mutation is in flight, false after.

**`ScanRunDetail.test.tsx`** — branches:
- loading header (no data yet) → "Loading…" PageHeader title.
- 404 → "Scan run not found" + back-link to `/scan-runs`.
- transport error → `BackendUnreachableCallout`.
- happy queued → header populated + Start button visible, Pause/Resume/Stop not visible.
- happy running → Pause + Stop visible; Start + Resume hidden.
- click Start (queued) → mutation fires + row data refetches to running on refresh.
- 400 illegal-transition on a lifecycle action → inline detail surfaced (`parseApiError`'s 400+detail path).

**`ScanRunsList.test.tsx`** — no logic change; tests stay green since `useScanRunActions` returns the same shape.

**E2E extension:** after the existing scan-run created → "Open" button click → detail page renders the queued header.

## Acceptance criteria

- 100% line + branch coverage on the new files.
- `npm test`, `npm run build` green.
- Operator can open `/scan-runs/:id`, see the header populated, click the right lifecycle button for the row's status, and watch the badge flip.
- `/simplify` rounds clean.
- No file over 200 lines.

## Out of scope (6A)

Spec §Target-status table → 6B. Spec §Live events panel → 6D. Spec §Findings panel + Evidence panel → 6C. Open-* actions on per-target rows → 6B.
