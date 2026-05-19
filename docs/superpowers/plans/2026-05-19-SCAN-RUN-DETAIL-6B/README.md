# Scan Run Detail 6B — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the per-target status table below the 6A header on `/scan-runs/:id`. Adds parent-run self-polling (worker-driven transitions reach the UI), per-target row polling (table refreshes within 2 s during running/stopping), and a terminal-flush that locks fresh cache content even when the parent terminal flip races the table's initial fetch.

**Spec:** [`../../specs/2026-05-19-scan-run-detail-6B-design.md`](../../specs/2026-05-19-scan-run-detail-6B-design.md)

**Backend lock:** em-backend SHA `e93c6f4` on `feat/em-backend` (serializer additions `8f5caec` + paused→stop enqueue parity `e93c6f4`). Verified backend file:line refs in [`../../specs/2026-05-19-scan-run-detail-6B-backend-anchors.md`](../../specs/2026-05-19-scan-run-detail-6B-backend-anchors.md).

## Phase index

| Phase | File | Ships |
|-------|------|-------|
| 1 | [phase-1-hooks.md](phase-1-hooks.md) | `ScanTargetRun` type, `useScanRunQuery` self-polling, `useScanRunTargetRunsQuery` + terminal flush, MSW handlers |
| 2 | [phase-2-table-page.md](phase-2-table-page.md) | `ScanRunTargetsTable` component, `DetailPageGuard` narrowing (both 404 + generic branches gate on `!query.data`) |
| 3 | [phase-3-app-wire-e2e.md](phase-3-app-wire-e2e.md) | Wire `ScanRunTargetsTable` into `ScanRunDetail`, integration tests, E2E |

## Definition of done

- 100% line + branch coverage on new and modified files.
- `npm test`, `npm test -- --coverage`, `npm run build` all green.
- `/simplify` rounds clean after each commit (per-commit gate; fix → re-run until quiet).
- No new or modified file over 200 lines (`App.e2e.test.tsx` stays untouched; its existing 305-line size is a separate deferred refactor).
- Operator can open `/scan-runs/:id` and see one row per target in `data.results` (up to backend `PAGE_SIZE = 50`; truncation footer when `data.next !== null`), status badge updating within 2 s while the parent run is `running`.
- Single peer ping to em-backend at slice completion (chat-noise-floor rule).

## TDD rules

- Strict TDD on every step: failing test first, then implementation. No production code without a failing test.
- 100% line + branch coverage on the production code path (frontend `src/`). Coverage gates measured by `npm test -- --coverage`.
- House style: `frontend/src/components/StatusBadge/StatusBadge.tsx` for the badge primitive — plain `<span data-testid="status-{status}">{status}</span>`, no ARIA role. Per-row test scoping uses `data-testid="target-run-row-{id}"` (see §Column layout in the spec).
