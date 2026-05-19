# Scan Runs page — slice 1 design

**Date:** 2026-05-19
**Owner:** agent-em-frontend
**Reviewer:** agent-em-backend (ACCEPT + shipped `findings_count` annotation as commit `5fe2944`; two micro-nits folded in)
**Status:** approved by peer; operator delegated approval
**Implements:** [`docs/superpowers/specs/2026-05-18-MVP-GUI/05-scan-runs.md`](2026-05-18-MVP-GUI/05-scan-runs.md)

## Goal

Build `/scan-runs` (list) and `/scan-runs/new` (create form) so the operator can create scan runs, see their status, and drive the lifecycle state machine (start / pause / resume / stop). Replaces the `<ComingSoon name="Scan Runs" />` route in `App.tsx`. The detail page (`/scan-runs/:id`, spec 06) stays as `<ComingSoon />` for this slice.

## Backend (confirmed by peer)

`backend/apps/scans/{serializers.py, views.py}` already implements every endpoint this slice needs:

- `GET /api/scans-runs/` — paginated; row shape (after peer's `5fe2944`):
  ```
  id, project (uuid), stub_slug (composite "<phase>.<spec>"),
  status, started_at, finished_at,
  target_run_count, findings_count,
  created_at, updated_at
  ```
  Filters: `?project=`, `?status=`, `?stub_slug=`.
- `POST /api/scan-runs/` — body `{project, stub_slug, target_ids[]}`. `min_length=1` on `target_ids`. Validates stub_slug against the cookbook registry; validates target_ids belong to the named project. Returns 201 with the annotated row.
- `POST /api/scan-runs/:id/{start,pause,resume,stop}/` — empty body; returns the updated `ScanRun`. Illegal transitions surface as `400 {"detail": "..."}`.

No backend changes required for this slice.

## Scope

**In:** list page + create page + the four lifecycle mutations + status-conditional action buttons.

**Out:** scan-run detail page (`/scan-runs/:id`, spec 06 — separate slice). The "Open" button on each list row routes to `/scan-runs/:id` which remains `<ComingSoon />` so the navigation feels real to the operator from day one (peer's UX framing).

## Architecture

Mirror of the Targets/Stubs slice shape with three new wrinkles:

1. **Multiple mutations sharing the same cache key.** Five mutation hooks (`create`, `start`, `pause`, `resume`, `stop`) all invalidate `SCAN_RUNS_KEY` on success so the list refetches once.
2. **Two-leg "Create and start" submit.** The form's primary action POSTs the scan run; on success it chains POST `/start/`. If the start leg fails (illegal transition / 5xx), keep the queued ScanRun and surface the start-leg error inline rather than rolling back the create — operator can retry via the Start button on the resulting row (peer's micro-nit). The "Create" button alone leaves the run in `queued`.
3. **Status state machine.** Action buttons render only for valid transitions:

   | Status | Buttons |
   |--------|---------|
   | `queued` | Start |
   | `running` | Pause, Stop |
   | `paused` | Resume, Stop |
   | `stopping` | (none) |
   | `stopped` | (none) |
   | `failed` | (none) |
   | `done` | (none) |

   `failed` and `stopped` are terminal — explicitly no Resume (peer's micro-nit). Open button is always present.

## Files

| File | State | Purpose |
|------|-------|---------|
| `frontend/src/types/api.ts` | modify | Add `ScanRun`, `CreateScanRunBody`, `LifecycleAction` types |
| `frontend/src/app/routes.ts` | modify | Add `scanRunsNew: "/scan-runs/new"` |
| `frontend/src/App.tsx` | modify | Swap `<ComingSoon name="Scan Runs" />` for real list + new routes |
| `frontend/src/features/scan-runs/api.ts` | new | `useScanRunsQuery({filters?})`, `useCreateScanRunMutation`, `useStartScanRunMutation`, `usePauseScanRunMutation`, `useResumeScanRunMutation`, `useStopScanRunMutation`, `SCAN_RUNS_KEY` |
| `frontend/src/features/scan-runs/ScanRunsList.tsx` | new | List page with status badge + conditional action buttons |
| `frontend/src/features/scan-runs/CreateScanRun.tsx` | new | Form: project → stub → target picker → two submit buttons |
| `frontend/src/features/scan-runs/StatusBadge.tsx` | new | Wrapper passing `ScanRunStatus` palette to the generic primitive (mirrors Stubs/Targets pattern) |
| `frontend/src/features/scan-runs/__fixtures__/scan-run.ts` | new | `makeScanRun(overrides?)` factory (mirrors stubs fixture) |
| `frontend/src/features/scan-runs/*.test.tsx` | new | Vitest + MSW per feature file |
| `frontend/src/App.e2e.test.tsx` | modify | Extend with a scan-run create → list flow |

## Types

```ts
export type ScanRun = {
  id: Uuid;
  project: Uuid;
  stub_slug: string;           // composite "<phase>.<spec>"
  status: ScanRunStatus;       // existing union
  started_at: Iso8601 | null;
  finished_at: Iso8601 | null;
  target_run_count: number;
  findings_count: number;      // peer-added in 5fe2944
  created_at: Iso8601;
  updated_at: Iso8601;
};

export type CreateScanRunBody = {
  project: Uuid;
  stub_slug: string;
  target_ids: Uuid[];          // at least one
};

export type LifecycleAction = "start" | "pause" | "resume" | "stop";
```

## `features/scan-runs/api.ts`

```ts
export const SCAN_RUNS_KEY = ["scan-runs"] as const;

export function useScanRunsQuery() {
  return useQuery({
    queryKey: SCAN_RUNS_KEY,
    queryFn: () => http<Paginated<ScanRun>>("/api/scan-runs/"),
  });
}

export function useCreateScanRunMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateScanRunBody) =>
      http<ScanRun>("/api/scan-runs/", { method: "POST", body }),
    onSuccess: () => void client.invalidateQueries({ queryKey: SCAN_RUNS_KEY }),
  });
}

// A single factory for the four lifecycle mutations. Each returns the
// updated ScanRun; all invalidate SCAN_RUNS_KEY.
function makeLifecycleHook(action: LifecycleAction) {
  return function useLifecycleMutation() {
    const client = useQueryClient();
    return useMutation({
      mutationFn: (id: Uuid) =>
        http<ScanRun>(`/api/scan-runs/${id}/${action}/`, { method: "POST" }),
      onSuccess: () => void client.invalidateQueries({ queryKey: SCAN_RUNS_KEY }),
    });
  };
}
export const useStartScanRunMutation = makeLifecycleHook("start");
export const usePauseScanRunMutation = makeLifecycleHook("pause");
export const useResumeScanRunMutation = makeLifecycleHook("resume");
export const useStopScanRunMutation = makeLifecycleHook("stop");
```

Slice 1 reads the unfiltered page; query-param filters land when the Findings/Evidence pages need them.

## `ScanRunsList.tsx`

**Columns:** ID short (first 8 chars of UUID) · Project · Stub · Status · Targets · Findings · Started at · Finished at · Actions.

**Project + Stub join:** cached `useProjectsQuery` and `useStubsQuery`. Same lookup pattern as Targets' project-name resolver. Fall back to the short UUID / raw slug when the related row isn't in the cached list.

**Status badge:** `<StatusBadge status={run.status} />` — the local feature wrapper passes a `Record<ScanRunStatus, string>` palette matching 14-styling.md:
- `queued = gray`
- `running = blue`
- `paused = yellow`
- `stopping = orange`
- `stopped = gray`
- `failed = red`
- `done = green`

**Actions cell:** a render helper maps the row's `status` to the visible buttons. Open is always rendered as a `<ButtonLink to={\`/scan-runs/${id}\`}>`. The four lifecycle buttons each fire their hook's mutation and rely on cache invalidation to re-render the row in its new state.

**Branches:** loading → skeleton; empty → EmptyState with a Create-scan-run button; error → `BackendUnreachableCallout` with Retry; happy → table.

## `CreateScanRun.tsx`

**Fields:**

1. **Project** — `<select>` from `useProjectsQuery`. Disabled when projects-query is loading / errored / empty. Empty list shows the same `<Callout>` linking to `/projects/new` as `CreateTarget` does.
2. **Stub** — `<select>` from `useStubsQuery`. Options render as `<option value={s.slug}>{s.slug} · {s.title}</option>`. Same loading/error/empty branches.
3. **Target picker** — depends on selected project. Two modes:
   - **All active** (default radio): client-side filter `useTargetsQuery().data?.results.filter(t => t.project === projectId && t.status === "active")`. The picker shows the count ("3 active targets will be scanned") and pre-computes `target_ids` from that list at submit time.
   - **Selected only** (radio): reveals a checkbox list of the same active-targets set; user picks N≥1.
   - Validation: at least one target_id at submit.

**Submit buttons:**

- **Create scan run** — POST `/api/scan-runs/`; on 201, `navigate(ROUTES.scanRuns)`.
- **Create and start** — POST `/api/scan-runs/`; on 201, chain POST `/start/` on the resulting `id`. If the create succeeds but start fails, keep the run in `queued`, surface the start-leg error inline, and still `navigate(ROUTES.scanRuns)` so the operator sees the queued row with a Start button (peer's micro-nit).
- **Cancel** — `navigate(ROUTES.scanRuns)`.

Server errors flow through `parseApiError` → `applyParsedError`.

## Tests

**`api.test.tsx`** — five hooks:
- `useScanRunsQuery` fetches and pages a list.
- `useCreateScanRunMutation` POSTs the body and invalidates `SCAN_RUNS_KEY`.
- One test per lifecycle hook (start / pause / resume / stop) — POSTs the right URL, invalidates the cache.

**`ScanRunsList.test.tsx`** — branches:
- loading → skeleton
- empty → EmptyState with Create action
- error → `BackendUnreachableCallout` with Retry
- happy → rows with project name + stub join + status badge + correct buttons per state
- one test per row state (queued, running, paused, stopping, stopped, failed, done) confirming the right button set
- clicking Start fires the mutation and the row re-renders in the new state (MSW returns the updated ScanRun; SCAN_RUNS_KEY invalidation triggers refetch)
- 400 from an illegal transition → inline error surfaced

**`CreateScanRun.test.tsx`** — branches:
- projects-query loading / error / empty
- happy create → navigates to `/scan-runs`
- create + start: success path; create succeeds but start fails (queued run kept + inline error)
- validation: project / stub / target_ids required
- target-picker: default "all active" computes correct id list; switching to "selected only" reveals checkboxes; deselecting all → validation error

**E2E extension:** create-project → create-target → create-scan-run → see the queued row → click Start → row flips to running.

## Acceptance criteria

- All branches covered by tests; 100% line + branch coverage on new files.
- `npm test`, `npm run build` green.
- Operator can: open `/scan-runs` → click Create scan run → pick project + stub + all-active targets → click "Create and start" → land on the list with the run in `queued` (or `running` if the worker has picked it up). Action buttons match the state.
- `/simplify` returns no actionable findings after final commit.
- No file exceeds 200 lines.

## Out of scope

- Scan-run detail page (`/scan-runs/:id`) — spec 06, separate slice.
- SSE events stream (`/sse/scan-runs/:id/events/`) — slice 06 territory.
- Filtering / search UI on the list — defer.
- Per-target retry, individual target stop, target-runs UI — defer.
- Bulk-cancel / bulk-restart — defer.
