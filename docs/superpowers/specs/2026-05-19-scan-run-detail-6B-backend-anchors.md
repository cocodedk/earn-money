# 6B backend anchors — verified file:line refs

Pass this file to codex on resumed verification. These backend facts have already been confirmed against the live `feat/em-backend` tree; codex does NOT need to re-grep them.

## Lifecycle endpoints

`backend/apps/scans/views.py:80-109` — DRF action methods (`start`, `pause`, `resume`, `stop`). All four are synchronous and side-effect-only on `ScanRun.status`. They do NOT mutate per-target rows directly.

`backend/apps/scans/views.py:106` — `stop()` action. As of em-backend SHA `e93c6f4`, this captures `was_paused = run.status == PAUSED` before `run.stop()`, and conditionally enqueues `transaction.on_commit(run_scan.delay)` when the run was PAUSED, to re-enter the worker's STOPPING→STOPPED finalization path.

`backend/apps/scans/views.py:135` — `target_runs` action. Returns paginated `ScanTargetRun` rows with `findings_count` + `evidence_count` annotated.

## Worker

`backend/apps/scans/tasks.py:45` — `run_scan` Celery task entry point. Delegates to `_execute_scan`.

`backend/apps/scans/tasks.py:57-59` — STOPPING branch inside `_execute_scan`. When the worker observes `run.status == STOPPING`, it calls `_finalize_stopped` and returns.

`backend/apps/scans/tasks.py:73` — `_process_target_run`. Writes `started_at` and flips the row to RUNNING before runner dispatch. Implication: rows in `running`/`done`/`failed`/`stopped`-from-running ALWAYS have `started_at` set.

`backend/apps/scans/tasks.py:133` — `_finalize_stopped`. Sets `finished_at` on the current target row and flips both target and run to STOPPED. **Does NOT synthesize `started_at`** — a `stopped`-from-queued row keeps null `started_at`.

`backend/apps/scans/tasks.py:165` — `_finalize_failed`. Sets `finished_at` and flips the row to FAILED. Exception path always runs after the row was flipped to RUNNING, so `started_at` is set.

`backend/apps/scans/tasks.py:189` — `_mark_run_done`. Sets `finished_at` and flips the run to DONE after all target rows are terminal.

## Serializer / contract

`backend/apps/scans/serializers.py` (`ScanTargetRunSerializer`) — row shape for `/api/scan-runs/<id>/target-runs/`. As of em-backend SHA `8f5caec` exposes `updated_at` (auto_now timestamp from `TimestampedUUIDModel`) and `target_host` (`source="target.host"` denormalization) in the serializer `fields` tuple. `ip` stays internal; `scan_run` per row stays omitted (nested URL carries the relationship).

## Pagination

`backend/config/settings.py:138` — `PAGE_SIZE = 50` on the DRF `DefaultPagination` (`config.pagination.DefaultPagination`). All paginated list endpoints (including `/api/scan-runs/<id>/target-runs/`) default to 50 rows per page.

## Frontend lookups (verified for 6A header dependencies)

`frontend/src/features/projects/api.ts:10` — `useProjectsQuery` fetches `GET /api/projects/` (list endpoint). `useProjectNameLookup` resolves names from this list query.

`frontend/src/features/stubs/api.ts:11` — `useStubsQuery` fetches `GET /api/stubs/` (list endpoint). Same pattern for stub-name lookup.

`frontend/src/components/DetailPageGuard/DetailPageGuard.tsx:24-58` — guard component with TWO error branches: line 29 (`isHttpStatus(query.error, 404)`) and line 42 (generic `query.isError`). Both currently fire regardless of `query.data` presence (§Decisions item 4 narrows both to `!query.data`).

`frontend/src/components/StatusBadge/StatusBadge.tsx:1-18` — plain `<span data-testid="status-{status}">{status}</span>`. No ARIA role. Tests target `data-testid` + text content, not `getByRole`.
