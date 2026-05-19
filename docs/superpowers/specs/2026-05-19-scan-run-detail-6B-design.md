# Scan Run Detail — slice 6B design (target status table)

**Date:** 2026-05-19
**Owner:** agent-em-frontend
**Reviewer:** agent-em-backend (contract ACK'd in msg #1565; serializer additions landed at `8f5caec`, paused→stop enqueue fix at `e93c6f4`, both on `feat/em-backend`)
**Implements:** [`docs/superpowers/specs/2026-05-18-MVP-GUI/06-scan-run-detail.md`](2026-05-18-MVP-GUI/06-scan-run-detail.md) §Target status table
**Follows:** [`2026-05-19-scan-run-detail-6A-design.md`](2026-05-19-scan-run-detail-6A-design.md) (header + lifecycle, shipped)

## Goal

Second of four sub-slices for `/scan-runs/:id`. Lands a per-target status table below the 6A header showing where each target stands inside the run. Remaining sub-slices: 6C (findings + evidence panels), 6D (live events SSE).

## Backend (locked at `8f5caec` for serializer fields; `e93c6f4` for lifecycle parity)

Live endpoint used by 6B:

- `GET /api/scan-runs/:id/target-runs/` — DRF `@action(detail=True)` on `ScanRunViewSet`. Returns `Paginated<ScanTargetRun>`. `findings_count` + `evidence_count` annotated in the view.

**Schema additions** (landed at `8f5caec` on `feat/em-backend`, append-only, read-only, no breaking change; regression-tested by `ScanRunTargetRunsActionTests::test_row_exposes_updated_at_and_target_host`):

- `updated_at` (Iso8601) — `auto_now` from `TimestampedUUIDModel`, exposed via the serializer `fields` tuple.
- `target_host` (string) — `source="target.host"` denormalization for the primary table label.

`ip` stays internal. `scan_run` per row stays omitted (nested URL carries the relationship).

**Pagination policy:** `ScanTargetRun` list is paginated by `config.pagination.DefaultPagination` (DRF `PageNumberPagination`, `PAGE_SIZE = 50` per `backend/config/settings.py:138`). 6B fetches **page 1 only** and renders all `results` in the table — no pagination UI. When `data.next !== null`, the table footer shows `"Showing first {results.length} of {count} targets"` so the operator sees the truncation. Real pagination (page controls, virtual list, "load more") is deferred to a later slice; MVP scan runs in the canonical em stack have ≤50 targets in practice. The acceptance criterion is rephrased to match (see §Acceptance).

## Prerequisites

- Running backend stack serves the `GET /api/scan-runs/:id/target-runs/` endpoint at SHA ≥ `e93c6f4` (i.e., serializer exposes `updated_at` + `target_host` from `8f5caec`, AND PAUSED→stop enqueues the worker via the conditional `transaction.on_commit(run_scan.delay)` from `e93c6f4`). Verified by the regression tests cited in §Backend. The canonical em stack rebuilds its backend container from `feat/em-backend`, so this is satisfied once `e93c6f4` is in the running image. Earlier SHAs (`< e93c6f4` but `≥ 8f5caec`) leave PAUSED→stop deadlocked at STOPPING — the table's polling-stop branch and the parent `running → stopping → stopped` transition test will never terminate on that backend.
- For test execution (`npm test`), no backend dependency — MSW handlers mock the contract at the `8f5caec` field shape.
- 6A (header + lifecycle) shipped on `feat/em-frontend` — `ScanRunDetail`, `DetailPageGuard`, `MetaList`, `useScanRunQuery` already exist.

## Scope

**In:**

- New `useScanRunTargetRunsQuery(scanRunId, options?)` hook in `frontend/src/features/scan-runs/api.ts`.
- New `ScanTargetRun` type in `frontend/src/types/api.ts`.
- New `ScanRunTargetsTable` component rendered below the MetaList inside `ScanRunDetail`.
- MSW handlers for the target-runs endpoint.
- **Symmetric parent polling**: extend the existing `useScanRunQuery(id)` to **self-poll internally** via a `refetchInterval` callback that reads its own cached `status` — `running`/`stopping` engages polling at 2 s, terminal states stop it. Without this, worker-driven `running → done` (and `stopping → stopped`) transitions never reach the UI, and the table's `livePolling` flip-off branches are unreachable in production. **No new option on the hook signature** — polling is keyed off the hook's own query state, not a caller-provided flag, to avoid the circular dependency where the call site needs `run.status` *before* calling the hook that fetches it.
- E2E smoke extension covering the table on `/scan-runs/:id`.

**Out (deferred):**

- **Actions column** (Open target result / Open findings / Open evidence) → deferred to 6C when Findings/Evidence routes serve real data. Parent MVP spec lists the column; today `/findings` and `/evidence` are `<ComingSoon>` and per-target-result page doesn't exist. Wiring buttons to ComingSoon placeholders is worse UX than no buttons; the column slots in naturally when 6C ships its destinations. Full rationale in §Decisions.
- Findings + Evidence panels → 6C.
- Live events SSE panel → 6D. 6B uses short-interval polling as the freshness mechanism until 6D replaces it.
- `RelativeTime` shared primitive — rule-of-three threshold lands at 6B; cleaner to extract in 6C once Findings/Evidence add four more sites.

## Files

| File | State | Purpose |
|------|-------|---------|
| `frontend/src/types/api.ts` | modify | Add `ScanTargetRun` type (full shape from `8f5caec`, incl. `updated_at` + `target_host`) |
| `frontend/src/features/scan-runs/api.ts` | modify | Add `useScanRunTargetRunsQuery` + `scanRunTargetRunsKey`; extend `useScanRunQuery` with an internal `refetchInterval` callback so the parent self-polls at 2 s when its cached status is `running`/`stopping` — no new option on the hook signature |
| `frontend/src/features/scan-runs/api.target-runs.test.tsx` | new | Hook tests (happy / disabled / polling-on / polling-off / flip mid-mount / unmount mid-poll / `SCAN_RUNS_KEY` cascade). New file because `api.test.tsx` is at 134 lines and the new branches would push it over the 200 cap. |
| `frontend/src/features/scan-runs/ScanRunTargetsTable.tsx` | new | Table component |
| `frontend/src/features/scan-runs/ScanRunTargetsTable.test.tsx` | new | Component branches |
| `frontend/src/features/scan-runs/ScanRunDetail.tsx` | modify | Render `<ScanRunTargetsTable scanRunId=… livePolling=… />` below MetaList |
| `frontend/src/features/scan-runs/ScanRunDetail.target-runs.test.tsx` | new | Detail-page integration tests for the target-runs slice (table mounts, `livePolling` flip on parent-status transitions, lifecycle-mutation cascade, badge update on poll, parent-query background-error remains silent visually — page header + MetaList + table all stay mounted, no full-page guard fallback). New file because `ScanRunDetail.test.tsx` is at 155 lines and the new branches would push it over the 200 cap. |
| `frontend/src/components/DetailPageGuard/DetailPageGuard.tsx` | modify | Narrow BOTH takeover branches to gate on `!query.data` — the 404 branch (`isHttpStatus(query.error, 404)`) and the generic `query.isError` branch — so background-refetch errors of either kind with stale parent data in cache do NOT trigger a full-page takeover (§Decisions item 4) |
| `frontend/src/components/DetailPageGuard/DetailPageGuard.test.tsx` | modify | Add two new branches: "isError + has data → render children" and "404 + has data → render children". Keep the existing "isError + no data → full-page error" and "404 + no data → not-found page" tests green to lock initial-load behavior |
| `frontend/src/test/handlers.ts` (or current MSW handler file) | modify | Add target-runs handlers |
| `frontend/src/features/scan-runs/ScanRunDetail.e2e.test.tsx` | new | Focused E2E for the detail page (table renders ≥1 row, status-badge column exercised). `App.e2e.test.tsx` is already at 305 lines (over the 200 cap); 6B does **not** extend it. A separate refactor splits `App.e2e.test.tsx` later; that refactor is out of scope here. |

All new files target the 200-line cap.

## Type contract — `ScanTargetRun`

```ts
export type ScanTargetRun = {
  id: Uuid;
  target: Uuid;
  target_base_url: string;
  target_host: string;          // from `8f5caec` — primary table label
  status: ScanRunStatus;        // shared enum; future per-target states extend, not fork
  started_at: Iso8601 | null;
  finished_at: Iso8601 | null;
  updated_at: Iso8601;          // from `8f5caec` — polling freshness signal until SSE in 6D
  findings_count: number;
  evidence_count: number;
  created_at: Iso8601;
};
```

## Hook contract — `useScanRunTargetRunsQuery`

```ts
type Options = { livePolling?: boolean };

export const scanRunTargetRunsKey = (id: string) =>
  [...SCAN_RUNS_KEY, id, "target-runs"] as const;

export function useScanRunTargetRunsQuery(
  scanRunId: string | undefined,
  options?: Options,
): UseQueryResult<Paginated<ScanTargetRun>>;
```

- `enabled = Boolean(scanRunId)`.
- `refetchInterval = options?.livePolling ? 2000 : false`. Optional-chain on `options` because the parameter itself is optional; the `false` literal is TanStack Query's canonical "no polling" value (not `undefined`); the hook always sets the field explicitly so a flip from `true` → `false` mid-mount cancels the timer cleanly without relying on unmount.
- `refetchOnWindowFocus` stays at the QueryClient default so focus catches stalled transitions when polling is off (e.g., parent `queued` → `running`).
- **Terminal-flush rule:** the hook tracks `livePolling`'s previous value via a ref; whenever it transitions from `true` → `false` **and `scanRunId` is truthy**, the hook fires a **two-step flush**:

  ```ts
  await queryClient.cancelQueries({ queryKey: scanRunTargetRunsKey(scanRunId) });
  await queryClient.refetchQueries({ queryKey: scanRunTargetRunsKey(scanRunId), type: "active" });
  ```

  **Why two steps, not `invalidateQueries({ cancelRefetch: true })`:** <!-- lint:allow --> `invalidateQueries` only triggers a refetch on *active* queries that are NOT currently fetching, and its `cancelRefetch` option only cancels an in-flight *refetch* when cached data exists. It does NOT cancel an in-flight *initial* fetch (no cached data yet). Concretely: if the page mounts, the parent's first poll returns `running` quickly, the table's initial fetch goes out, and then the worker finishes and the parent's next poll returns `done` before the table's initial fetch returns — at the terminal-flush moment the table query is in its initial fetch with no cached data. `invalidateQueries` would only mark it stale; the in-flight stale response would then land and populate the cache; with polling already off, nothing ever refetches it, and the table is permanently stuck on pre-terminal rows.

  `cancelQueries` cancels in-flight requests regardless of cache state, then `refetchQueries` starts a fresh post-terminal fetch. The trade-off is one extra observable network event when an in-flight existed (the cancelled request still hits MSW; only the response is discarded), so tests assert **fresh terminal row data** in the cache, not exact network-call counts.

  This captures any worker-side `ScanTargetRun` writes that landed between the last poll (or initial fetch) and the parent's terminal observation — without it, the last per-target row could remain at `running` in the cache forever after `running → done`. Initial mount (`livePolling` starts `false`) does NOT trigger the flush; only the `true → false` edge does. The `scanRunId` truthy guard prevents `scanRunTargetRunsKey(undefined)` — which would produce the invalid key `[...SCAN_RUNS_KEY, undefined, "target-runs"]` — when the hook is disabled (no `scanRunId`) or unmounting on the edge.

**Why `livePolling: boolean` over `parentStatus: ScanRunStatus`:** the hook stays generic (any future surface can drive polling independently of ScanRun status), the test matrix collapses from 7 enum values to 2 boolean states, and the policy `status === "running" || status === "stopping"` lives once at the call site in `ScanRunDetail`. The hook does not know about `ScanRun`.

**Parent query polling (extension to `useScanRunQuery`):** the parent hook computes its own polling cadence internally — no caller-provided option, no circular dependency on its own data. TanStack Query supports `refetchInterval` as a callback that receives the current query state:

```ts
useQuery({
  queryKey: scanRunKey(id ?? ""),
  queryFn: () => http<ScanRun>(`/api/scan-runs/${id}/`),
  enabled: Boolean(id),
  refetchInterval: (q) => {
    const status = q.state.data?.status;
    return (status === "running" || status === "stopping") ? 2000 : false;
  },
});
```

This is the canonical "poll while X" pattern keyed off the query's own data. Without it, the call site would need `run.status` to compute `livePolling` *before* calling `useScanRunQuery` — a circular contract. The target-runs hook keeps its caller-provided `livePolling` option because its polling condition depends on the *parent's* status, which it can't observe through its own cache.

**Cache coordination — keys are intentional children of `SCAN_RUNS_KEY`:** 6A's `useStartScanRunMutation` / `usePause…` / `useResume…` / `useStopScanRunMutation` all invalidate `SCAN_RUNS_KEY` on success (see `frontend/src/features/scan-runs/api.ts`). Both the parent `scanRunKey(id) = [...SCAN_RUNS_KEY, id]` and the 6B target-runs key `[...SCAN_RUNS_KEY, id, "target-runs"]` are children, so a single lifecycle mutation cascades to both — the parent refetches its `status` and the table refetches its rows. This is the intentional contract; both transition tests and cascade tests are aware of it (see §Tests for how they're decoupled).

The lifecycle POST endpoints (`backend/apps/scans/views.py:80-109`) are synchronous and side-effect-only on `ScanRun.status` — they do NOT mutate per-target rows directly (em-backend confirmed in msg #1580). Actual `ScanTargetRun` row transitions (`queued → running → done|failed`, stop-finalization) happen asynchronously in the Celery worker (`backend/apps/scans/tasks.py:45 run_scan`) after `transaction.on_commit` enqueues `run_scan.delay()`. This holds for **both** RUNNING→stop and PAUSED→stop as of em-backend SHA `e93c6f4`: `views.stop()` (`views.py:106`) now captures the previous status before `run.stop()` and, when the run was PAUSED, conditionally enqueues `run_scan.delay()` to re-enter the worker's STOPPING→STOPPED finalization path (`tasks.py:57-59`). Without that conditional enqueue, PAUSED→stop would deadlock at STOPPING — no worker would ever pick the run back up. Both transitions now return `200 {status: "stopping"}` immediately and the worker flips to STOPPED asynchronously, so 6B's polling design treats them identically. So the cascade refetch returns pre-worker state; the 2 s polling is what surfaces the real per-target transitions until SSE in 6D. The cascade test asserts cascade *behavior* (refetch fires) — not row content — so it stays correct.

## Column layout

| Column | Source | Cell render |
|--------|--------|-------------|
| Target | `target_host` (primary) + `target_base_url` (secondary, dim) | Two-line cell |
| Status | `status` | Existing `<StatusBadge>` from `features/scan-runs/StatusBadge.tsx` |
| Started at | `started_at` | `slice(0, 19)` matching 6A's inline formatter, `—` when null |
| Finished at | `finished_at` | Same as Started |
| Findings | `findings_count` | Right-aligned numeric |
| Evidence | `evidence_count` | Right-aligned numeric |

No Actions column — see "Out".

**Per-row test-id:** each rendered `<tr>` gets `data-testid="target-run-row-{id}"` (where `{id}` is `ScanTargetRun.id`) so tests can scope assertions to a specific row via `within(row)` — see §Tests for why scoping is required to disambiguate from the 6A header's parent `StatusBadge`.

## Render integration inside `ScanRunDetail`

```tsx
// At the top of ScanRunDetail:
const { id } = useParams();
const query = useScanRunQuery(id);  // self-polling via internal callback (see Hook contract)
const run = query.data;

// Inside DetailBody (after the existing MetaList):
const livePolling = run.status === "running" || run.status === "stopping";
<ScanRunTargetsTable scanRunId={run.id} livePolling={livePolling} />
```

Order of execution is now linear: parent hook runs first and polls itself when active; once `run` is available, `livePolling` is derived from the *resolved* `run.status` and passed to the table. No circular dep.

**Worker-driven flow end-to-end:**
1. Page mounts. Parent hook fetches once, gets `running`. Internal callback sees `running` → polls at 2 s.
2. Each parent poll produces a fresh `run.status`. While `running`/`stopping`, `livePolling` derived for the table is `true` → table polls at 2 s.
3. Worker eventually flips parent to `done` (or `stopped`/`failed`). Next parent poll catches that. Internal callback sees terminal status → stops polling. Re-render derives `livePolling = false`.
4. Table hook sees the `livePolling` flip and fires **one final terminal flush** — a two-step `cancelQueries` + `refetchQueries` pair (see Hook contract — terminal-flush rule) to capture any worker writes that landed between the last poll (or in-flight initial fetch) and the parent's terminal observation. Without this, the last per-target row could remain at `running` in the cache forever.

**Initial-load:** on first render `run === undefined`. The render snippet's `DetailBody` only runs once `run` is defined (guarded by `DetailPageGuard`), so the `livePolling` derivation never sees `undefined`. The parent's internal callback also sees `undefined` on the first render and returns `false` — no polling fires until the first response lands.

`ScanRunTargetsTable` owns its own loading / empty / error states scoped to the section — page header + MetaList stay visible. Error renders inline `<Callout>` (not `BackendUnreachableCallout`) because the parent run already loaded.

## Tests

**`api.target-runs.test.tsx`** (new file):

- `useScanRunTargetRunsQuery("r-1")` fetches `/api/scan-runs/r-1/target-runs/` and returns paginated rows.
- `useScanRunTargetRunsQuery(undefined)` is disabled — no network call.
- `livePolling: true` → MSW intercepts ≥2 calls within 2.5 s on fake timers.
- `livePolling: false` (and `livePolling` undefined) → MSW intercepts exactly 1 call within the same window.
- **Live-flag flip mid-mount with terminal flush — no in-flight poll branch**: re-render the hook with `livePolling: true` → `false` while no poll is in flight (advance fake timers to just after the last poll response settles, then flip). MSW is scripted so the flush response carries a *different* row state than the last poll did (e.g. last poll returned the row as `running`, flush response returns `done`). Assert (a) one network refetch fires after the flip, and (b) the cache's row state matches the flush response (not the prior poll's response). Locks "fresh terminal data is committed", which is the actual contract — not the network-call count.
- **Live-flag flip mid-mount with terminal flush — in-flight poll branch (cancel-restart, cached data exists)**: re-render the hook with `livePolling: true` → `false` *during* an in-flight target-runs poll, AFTER at least one successful response has populated the cache (let polling stabilize first, then trigger the next poll with MSW `delay` so the response is pending when the flip happens). Script MSW so the in-flight response carries pre-terminal stale rows and the post-flush response carries fresh terminal rows. Assert (a) the cache ends with the fresh terminal rows (the in-flight stale response is discarded by `cancelQueries`), and (b) no further polling fires after the flush settles.
- **Live-flag flip mid-mount with terminal flush — no-cached-data in-flight branch (the round-5 edge case)**: render the hook with `livePolling: true` and MSW `delay` set high enough that the *initial* fetch is still pending when the test flips `livePolling` → `false`. At the flip moment the table query has NO cached data, only an in-flight initial fetch. Script MSW so the initial response (still pending) carries stale pre-terminal rows; the post-flush response carries fresh terminal rows. Assert the cache ends with fresh terminal rows — the initial fetch's stale response is discarded by `cancelQueries` and `refetchQueries` starts a fresh fetch. **Without this branch the spec would not lock the very edge case that broke `invalidateQueries({ cancelRefetch: true })`** <!-- lint:allow --> — only `cancelQueries` + `refetchQueries` handles a no-cached-data in-flight at the terminal edge.
- **All three flush branches together cover timer cancellation without unmount AND the flush rule under all contention regimes** (no in-flight; in-flight with cached data; in-flight without cached data). All three assert *cache content*, not network-call counts, because the cancel-restart pattern produces an extra observable network event whose presence is implementation detail, not contract.
- **No flush on initial false → flush only on true → false edge**: render the hook with `livePolling: false` from the start; assert exactly one initial fetch fires, no extra invalidation. Lock the edge-detection logic so initial mount doesn't double-fetch.
- **Unmount mid-poll**: unmount the hook while `livePolling: true` and assert no MSW calls fire after unmount.
- **Cache cascade from `SCAN_RUNS_KEY`** — uses paused parent to isolate cascade from polling: render the hook with `livePolling: false` (simulating a parent in `paused`, where `Stop` is still a valid transition), trigger `queryClient.invalidateQueries({ queryKey: SCAN_RUNS_KEY })`, and assert the target-runs query refetches exactly once. Timers stay engaged but `refetchInterval: false` means no polling ticks compete — the single refetch must come from the cascade. Locks the contract documented above without timing races.

**`api.test.tsx`** — adds (only) parent self-polling branches keyed off the internal callback, staying under 200 lines:

- **Parameterized across both polling-active statuses (`running` + `stopping`):** for each of `status: "running"` and `status: "stopping"`, `useScanRunQuery(id)` with MSW returning that status → MSW intercepts ≥2 calls within 2.5 s on fake timers. Both branches of the internal callback's `status === "running" || status === "stopping"` predicate must be exercised; testing only `"running"` would leave the `"stopping"` branch unverified, and a regression that drops `"stopping"` from the predicate would silently land.
- **Parameterized across all non-polling statuses (`queued` / `paused` / `done` / `failed` / `stopped`):** for each, `useScanRunQuery(id)` with MSW returning that status → MSW intercepts exactly 1 call within 2.5 s on fake timers. Locks the inverse of the `status === "running" || status === "stopping"` predicate — a regression that engages polling for `queued`/`paused` (e.g. accidentally widening the predicate) would fail.
- `useScanRunQuery(id)` mid-fetch transition: first poll returns `running`, second returns `done`. Assert polling fires through the `running` poll, then stops after the response containing `done` lands.

If adding these pushes `api.test.tsx` over 200, the parent-polling tests move into a new `api.scan-run-polling.test.tsx`.

**`ScanRunTargetsTable.test.tsx`**:

- Happy: rows render `target_host`, `target_base_url`, status badge, counts, timestamps.
- Empty (`count: 0`): empty-state copy renders, no table headers without a body.
- Loading: skeleton or spinner placeholder before resolve.
- Mixed statuses + timestamp variants matching the backend's finalize-write paths:
  - `queued` row: null `started_at` + null `finished_at` → both cells render `—`.
  - `running` row: set `started_at` + null `finished_at` → `finished_at` cell renders `—`.
  - `paused` row: set `started_at` + null `finished_at` → same cell rendering as `running` (paused-from-running keeps `started_at`).
  - `done` row: both `started_at` + `finished_at` set per `_process_target_run` (`backend/apps/scans/tasks.py:73`) which writes `started_at` before runner dispatch. Both cells render `slice(0, 19)` values.
  - `failed` row: both `started_at` + `finished_at` set per `_process_target_run` → `_finalize_failed` (`backend/apps/scans/tasks.py:165`); the worker exception path always runs after the row is flipped to RUNNING, so `started_at` is set. Both cells render `slice(0, 19)` values.
  - `stopped`-from-running row: both `started_at` (written by `_process_target_run` at `tasks.py:73`) + `finished_at` (written by `_finalize_stopped` at `tasks.py:133`) populated. Both cells render `slice(0, 19)` values.
  - `stopped`-from-queued row: null `started_at` + set `finished_at` (per `_finalize_stopped` at `tasks.py:133` which sets `finished_at` regardless of prior state — the row was about to be picked up but stop arrived first, so `started_at` was never written). `started_at` cell renders `—`, `finished_at` cell renders `slice(0, 19)`.
  - Together these lock the worker's per-state timestamp contract.
- **Scoped inline error** (the branch `DetailPageGuard` does NOT own): 500 / network error from the target-runs endpoint with the parent run successfully loaded → inline `<Callout>` inside the section, page header + MetaList stay mounted, no full-page guard fallback. This is the only place this branch is exercised — `DetailPageGuard`'s error branches only cover parent-query failures.

**`ScanRunDetail.target-runs.test.tsx`** (new file — keeps `ScanRunDetail.test.tsx` at its current 155 lines):

- Happy detail render includes the table beneath the MetaList.
- **Parent-status transition while table is mounted** — three branches. **All three use a mutable MSW handler backed by a `ref`/closure variable** for the parent `/api/scan-runs/:id/` endpoint: the test holds a `currentParentRun` variable that the MSW resolver reads on every request, and the test mutates it to drive transitions. **Why mutable MSW, not just `setQueryData`:** `useScanRunQuery` now self-polls via the internal `refetchInterval` callback (2 s while `running`/`stopping`); `staleTime` does NOT suppress `refetchInterval` (they're independent TanStack Query knobs), so a naive `setQueryData(scanRunKey(id), newRun)` test would race against the next polling tick — the poll would hit MSW, get back whatever stale handler returns, and clobber the seeded value before the assertion fires. With mutable MSW the handler is always consistent with what the test wants the cache to hold; `setQueryData` is no longer needed (the next poll within 2 s naturally syncs the cache from MSW). For the cascade-driven branch (lifecycle mutation), `invalidateQueries({ queryKey: SCAN_RUNS_KEY })` still triggers the refetch and the MSW resolver returns the updated state — clean isolation. The three transition branches drive `currentParentRun` from `queued → running`, `running → done`, and `running → stopping → stopped`; fake timers advance the 2 s polling window after each mutation; assertions read the rendered output once the next poll lands.
  - `queued` → `running`: set `currentParentRun.status = "queued"`, render. With `queued`, the parent's `refetchInterval` callback returns `false` (no polling); confirm no target-runs poll fires in the first 2.5 s of fake timers. Then mutate `currentParentRun.status = "running"`, fire one `queryClient.invalidateQueries({ queryKey: scanRunKey(id) })` to trigger the next parent fetch (otherwise the `false` interval stays in effect), assert `livePolling` flips on and at least one target-runs poll fires within the next 2.5 s.
  - `running` → `done`: set `currentParentRun.status = "running"`, render, let the polling stabilize (≥2 polling cycles), advance fake timers to a moment **between** target-runs polls (just after a poll response settles), mutate `currentParentRun.status = "done"`, wait for the parent's next 2 s tick so the cache observes `done`. Script MSW so the post-flush response carries fresh terminal rows different from the last poll's payload. Assert `livePolling` flips off, the cache ends with the fresh terminal rows from the flush response (no further polling fires after the flush settles). Cache-content assertion — not network-call count — matches the §Hook contract terminal-flush contract.
  - `running` → `stopping` → `stopped`: same MSW-mutation pattern; `livePolling` stays on through `stopping` (poll counts increase across both statuses), flips off only on `stopped`. As with the `running → done` branch, time the `stopped` mutation to a moment when no target-runs poll is in flight, so the terminal flush's fresh-fetch path is the only event in play (no in-flight cancel happens here). Assert the cache ends with fresh terminal rows on the `stopped` edge — same cache-content assertion shape as the `running → done` branch.
  - **In-flight flush cancel-restart branch — cached data exists** (separate test, proves the cache ends fresh under in-flight contention with established data): set `currentParentRun.status = "running"`, render, let polling stabilize (≥1 successful target-runs response cached), mutate `currentParentRun.status = "done"` *during* an in-flight target-runs poll. Script MSW so the in-flight response carries pre-terminal stale rows and the post-flush response carries fresh terminal rows. Assert the cache ends with fresh terminal rows; the in-flight stale response is discarded by `cancelQueries`. Locks "fresh terminal data is committed even under in-flight contention".
  - **No-cached-data in-flight branch** (round-5 edge case — the terminal flip races the initial fetch): set `currentParentRun.status = "running"`, render with MSW `delay` high enough that the *initial* target-runs fetch is still pending when the parent flips to terminal. Mutate `currentParentRun.status = "done"` before the initial response returns. Script MSW so the initial response (still pending) carries stale pre-terminal rows; the post-flush response carries fresh terminal rows. Assert the cache ends with fresh terminal rows — `cancelQueries` cancels the pending initial fetch regardless of cache state, and `refetchQueries` starts a fresh fetch. This is the branch that would silently break under `invalidateQueries({ cancelRefetch: true })` alone <!-- lint:allow --> — without it, the spec doesn't lock the actual contract.
- **Lifecycle-mutation refresh path** (uses paused parent — same trick as the hook cascade test): render with parent in `paused` so polling is off; fire `useStopScanRunMutation` (valid transition from `paused`); assert exactly one target-runs refetch fires immediately after the mutation invalidates `SCAN_RUNS_KEY`. No polling competes for the assertion.
- **Visible badge update on poll** (closes the acceptance criterion's "within 2 s" claim): render with `running` parent and one target row initially `queued`; MSW returns the same row as `running` on the second poll; advance fake timers by 2 s; locate the table row by its `data-testid="target-run-row-{targetRunId}"` (added to each `<tr>` for scoping — see §Column layout), then use `within(row).getByTestId(/^status-/)` to assert the rendered badge's `data-testid` flips from `status-queued` to `status-running` AND its visible text flips correspondingly, both without remount. **Row scoping is required**: the 6A header also renders a parent `StatusBadge` with `data-testid="status-{parentStatus}"`, so an unscoped `getByTestId("status-running")` would be ambiguous and could match the header badge or any other row's badge. The badge is a plain `<span data-testid="status-{status}">{status}</span>` (`frontend/src/components/StatusBadge/StatusBadge.tsx`) with no ARIA role, so the assertion targets `data-testid` + text content (via `within(row)`), not `getByRole`. Asserts the rendered output, not just the network call count.
- **Parent background-error stays silent with stale data** (closes §Decisions item 4 — integration coverage): render with `running` parent successfully loaded (table visible). Two sub-branches:
  - (a) Generic background error: switch MSW's `GET /api/scan-runs/:id/` handler to respond with a 500 / network error on subsequent polls; advance fake timers past one polling cycle; assert (i) page header + MetaList + table all stay mounted, (ii) no full-page guard fallback renders (no "backend unreachable" callout takes over), (iii) the table itself continues to render its last-known rows since its own query is unaffected.
  - (b) Transient 404 background error: same shape but MSW returns 404 on subsequent polls; assert no 404 "not-found" page takes over; same three sub-assertions.
  These exercise the narrowed `DetailPageGuard` branches end-to-end through `ScanRunDetail`, complementing the unit-level branches in `DetailPageGuard.test.tsx`.

**E2E (`ScanRunDetail.e2e.test.tsx`, new file):** navigate to `/scan-runs/:id`, assert the 6A header renders, assert ≥1 target row renders below it. **MSW handlers required for the test to pass** (the global setup uses `onUnhandledRequest: "error"`, so any missing handler fails the test):

- `GET /api/scan-runs/:id/` — returns the parent run with a `running` status (drives the table's `livePolling`).
- `GET /api/scan-runs/:id/target-runs/` — returns one `queued` row and one `done` row so the status-badge column is exercised.
- `GET /api/projects/` — list endpoint, returns the project the 6A header looks up by id (the `useProjectNameLookup` hook resolves names from this list query, not a detail endpoint).
- `GET /api/stubs/` — list endpoint, returns the stub the 6A header looks up by slug (mirrors the project pattern — name resolution is list-side, not detail-side).

Also asserts the "Showing first N of M targets" footer is **absent** when `next === null`, present when `next !== null` (pagination policy from §Backend).

## Acceptance criteria

- 100% line + branch coverage on the new and modified files, measured by `npm test -- --coverage` (vitest's `--coverage` flag invokes the configured coverage provider). A dedicated `test:coverage` script may be added to `frontend/package.json` if a one-shot command is preferred.
- `npm test`, `npm test -- --coverage`, `npm run build` all green.
- Operator can open `/scan-runs/:id` and see one row per target in `data.results` (up to the backend's `PAGE_SIZE = 50` cap; truncation footer shown when `data.next !== null`), status badge updating within 2 s while the parent run is `running`.
- `/simplify` rounds clean.
- No new or modified file over 200 lines. (`App.e2e.test.tsx` stays untouched; its existing 305-line size is a separate deferred refactor and not 6B's problem.)

## Decisions

Operator-deferred items resolved by the design owner (per the "decide and ship, only ask when irreversible" rule). All four are reversible doc/UX choices; revisit when 6C lands or operator redirects.

1. **Actions column** — **omitted in 6B**, ships in 6C alongside Findings/Evidence destinations. Two alternatives considered and rejected:
   - *Disabled buttons with "Available in 6C" tooltip* — adds three dead affordances per row; visual clutter without function.
   - *Single conditional "Open" affordance dispatching by counts* (e.g., `findings_count > 0 ? /findings?target=… : /evidence?target=…`) — same destination problem (both routes are `ComingSoon` in `App.tsx`, no target-result route exists in `app/routes.ts`), plus the dispatch rule has no operator-validated semantics yet and would need a re-design when 6C lands. Cleaner to ship the column whole in 6C against real destinations.
2. **Polling interval — 2 s.** SSE in 6D replaces it; under-polling here only delays per-target row transitions by ≤2 s, no correctness impact.
3. **`RelativeTime` primitive — defer to 6C.** Rule-of-three lands at 6B's third site, but 6C adds four more (Findings/Evidence date columns), making 6C the cleaner extraction point. 6B uses the same inline `slice(0, 19)` formatter 6A uses.
4. **Background-refetch error handling.** The existing `DetailPageGuard` has two takeover branches: a 404 branch (`isHttpStatus(query.error, 404)`) and a generic `query.isError` branch. Both currently fire regardless of whether `query.data` is present, so with 6B's self-polling a transient network blip OR a transient 404 from the parent endpoint during a background poll would surface as a full-page takeover even when stale parent data is still good — a regression in UX. 6B narrows **both** takeover branches to gate on `!query.data`: when stale parent data exists in the cache, neither the 404 page nor the generic-error page renders; the guard keeps the children mounted (header + MetaList + table all stay visible), and any inline error state belongs to whichever section's query failed. The table section already owns its own inline `<Callout>` for table-query failures (see §Render integration); parent-query background errors (both 404 and generic) become silent visually — the only signal is the stale-time indicator if/when one is added (out of scope for 6B). New tests in `DetailPageGuard.test.tsx` cover both narrowed branches: (a) `query.isError + has data` → render children, no full-page takeover; (b) `isHttpStatus(query.error, 404) + has data` → render children, no 404 takeover. Existing tests for "isError + no data" and "404 + no data" stay green to lock the original initial-load behavior.

**Em-backend ratified (resolved):** schema additions (`updated_at`, `target_host`) landed at `8f5caec`, wired in §Backend above. Lifecycle endpoints are sync side-effect-only on `ScanRun` with async Celery rollout for `ScanTargetRun` rows (msg #1580).

## Out of scope (6B)

Spec §Live events panel → 6D. Spec §Findings panel + Evidence panel → 6C. Open-target-result / Open-findings / Open-evidence per-row actions → 6C.

## Review state

In mutual-acceptance loop with codex (gpt-5.5 xhigh). After rounds 1-5 codex returned 20 issues; all addressed in this revision.

**Stable since round 4 — do not re-litigate:** §Type contract, §Column layout (incl. per-row test-id), §Files (all rows), §Decisions items 1-4, §Acceptance criteria, §Out of scope, §Backend pagination policy (`PAGE_SIZE = 50` at `backend/config/settings.py:138`), §Prerequisites SHA pin (`e93c6f4`), §Tests row-timestamp split (stopped-from-queued vs stopped-from-running).

**Changed in response to codex round 5 (BLOCKER):**
- §Hook contract terminal-flush rule: replaced `invalidateQueries({ cancelRefetch: true })` with a two-step `cancelQueries` + `refetchQueries` pattern. <!-- lint:allow --> `invalidateQueries({ cancelRefetch: true })` only cancels in-flight *refetches* (cached data exists); it does NOT cancel an in-flight *initial* fetch. <!-- lint:allow --> The no-cached-data edge would let a stale pre-terminal response land after polling is off.
- §Tests `api.target-runs.test.tsx`: split the in-flight flush test into two branches — "cached data exists" (existing) and "no cached data (initial fetch in flight)" (new, round-5 edge case).
- §Tests `ScanRunDetail.target-runs.test.tsx`: added the matching no-cached-data branch at the integration level.

**Changed in response to codex round 6 (contradiction cleanup):**
- §Render integration worker-driven flow step 4: dropped the "invalidate-and-refetch" wording (leftover from pre-round-5 contract); <!-- lint:allow --> now reads "two-step `cancelQueries` + `refetchQueries` pair" matching §Hook contract.
- §Tests `ScanRunDetail.target-runs.test.tsx` — `running → done` and `running → stopping → stopped` bullets: dropped "exactly one refetch fires" / "no-op'd by `cancelRefetch: false`" wording (also leftover); <!-- lint:allow --> both now assert cache content (fresh terminal rows committed) consistent with the §Hook contract terminal-flush rule.

**For codex round 7 (cleanup verification — past the 6-round cap per protocol):** validate the round-6 cleanup landed; spot any remaining `invalidate`/`cancelRefetch` leftovers. Stable sections unchanged from prior rounds.
