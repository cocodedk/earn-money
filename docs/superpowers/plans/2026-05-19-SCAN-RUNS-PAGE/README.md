# Scan Runs page — slice 1 implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `/scan-runs` (list with status-conditional action buttons) and `/scan-runs/new` (create form with two-leg "Create and start" submit). Replaces `<ComingSoon name="Scan Runs" />`.

**Architecture:** Mirror of the Targets/Stubs slice shape with three additions: five mutation hooks (one create + four lifecycle), a render helper that maps status → visible buttons, and a chained-submit for "Create and start" that keeps the queued run on partial failure.

**Spec:** [`../../specs/2026-05-19-scan-runs-page-design.md`](../../specs/2026-05-19-scan-runs-page-design.md)
**Page spec:** [`../../specs/2026-05-18-MVP-GUI/05-scan-runs.md`](../../specs/2026-05-18-MVP-GUI/05-scan-runs.md)
**Backend (live):** `backend/apps/scans/{serializers.py, views.py}`. `findings_count` annotation landed in peer commit `5fe2944` (next push).

**Branch:** Commit on `refactor/archive-v1`. Single peer ping at slice completion (chat-noise-floor).

**Conventional commits:** `feat(frontend):`, `test(frontend):`, `docs(frontend):`, `refactor(frontend):`.

## Phase index

| Phase | File | Task | Ships |
|-------|------|------|-------|
| 1 | [phase-1-types-routes.md](phase-1-types-routes.md) | A | `ScanRun`, `CreateScanRunBody`, `LifecycleAction` types; `ROUTES.scanRunsNew` |
| 2 | [phase-2-api-client.md](phase-2-api-client.md) | B | api hooks (query + 5 mutations) + fixture factory |
| 3 | [phase-3-scan-runs-list.md](phase-3-scan-runs-list.md) | C | `ScanRunsList` with state-machine action buttons |
| 4 | [phase-4-create-scan-run.md](phase-4-create-scan-run.md) | D | `CreateScanRun` form with two-leg submit |
| 5 | [phase-5-app-wire-e2e.md](phase-5-app-wire-e2e.md) | E | `App.tsx` wiring + E2E extension |

## Definition of done

- All phases shipped; 100% line + branch coverage; build green.
- Operator can: create project → create target → /scan-runs/new → pick project + stub + all-active targets → Create and start → see queued/running row with the correct action button set.
- `/simplify` clean.
- Single peer ping after slice completion.
