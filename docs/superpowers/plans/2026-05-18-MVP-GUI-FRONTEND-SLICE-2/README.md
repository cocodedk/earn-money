# MVP-GUI Frontend Slice 2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the demo-ready end-to-end scan workflow from `15-workflow-seed.md`: Add Targets → Open Stubs → Create Scan Run → Start → Watch live SSE events → Pause/Resume/Stop. Plus the slice-1.1 follow-up to make the `CurrentProjectChip` switch link actually switch. After slice 2, the operator can drive a full Juice Shop / DVWA / WebGoat scan against peer's `/api/scan-runs/<id>/start/` end-to-end.

**Architecture:** Same as slice 1 — feature-first folders under `frontend/src/`, TanStack Query v5 for server state, React Router v6 for routes, Tailwind v3 via CSS-Module `@apply`, Vitest + RTL + MSW for tests with 100% line + branch + function + statement coverage. New for slice 2:
- `useScanRunEvents(scanRunId)` hook wrapping native `EventSource` with reconnect + `Last-Event-ID` resume + polling fallback (per `12-live-events.md`).
- `StatusBadge` gains a `failed` variant with tooltip rendering `error` class name + `message` from `scan_target_run.failed` SSE payloads (per peer's `923f5a0`).
- New primitives: `SeverityBadge`, `EventList` (rolling log with level filter + auto-scroll toggle).
- Feature-local component: `MultiTargetSelect` for the Create Scan Run form (checkbox list over the project's active targets).

**Branch:** `feat/em-frontend-slice-2` in the worktree at `/home/cocodedk/0-projects/earn-money-frontend-slice-2/`. Cut from `refactor/archive-v1` at `3c6dc34`. Periodically rebase onto `refactor/archive-v1` to pull peer's backend updates (stub 1.2-1.7 land there). Merge back to `refactor/archive-v1` once slice 2 is green or for compose smokes.

**Conventional commits:** every task ends with a single commit using `feat(frontend):`, `test(frontend):`, `chore(frontend):`, or `docs(frontend):`. The post-commit hook reminder kicks in after each commit — run `/simplify` until clean before moving to the next task.

## Out of scope for slice 2 (defer to slice 3+)

- `/projects/:id` project detail page
- `/targets/:id/results` target result page
- `/findings/` list + `/findings/:id` detail
- `/evidence/` list + `/evidence/:id` detail
- `/settings/` system status page (needs peer's extended `/api/health/`)
- Seed-data button

The operator can see findings + evidence rows on the scan-run detail page in slice 2, so the standalone list/detail pages are a separate slice, not a blocker.

## Phase index

| Phase | File | Tasks | Ships |
|-------|------|-------|-------|
| 0 | [phase-0-primitives.md](phase-0-primitives.md) | A–C | StatusBadge with failed variant + tooltip; SeverityBadge; EventList |
| 1 | [phase-1-current-project-action.md](phase-1-current-project-action.md) | D | Set-as-current row action on ProjectsList |
| 2 | [phase-2-targets.md](phase-2-targets.md) | E–G | Targets API client; TargetsList page; AddTarget form |
| 3 | [phase-3-stubs.md](phase-3-stubs.md) | H–J | Stubs API client; StubsList page; StubDetail page |
| 4 | [phase-4-scan-runs.md](phase-4-scan-runs.md) | K–N | ScanRuns API client; ScanRunsList page; CreateScanRun form; lifecycle action API |
| 5 | [phase-5-sse.md](phase-5-sse.md) | O–P | `useScanRunEvents` hook; wire to EventList |
| 6 | [phase-6-scan-run-detail.md](phase-6-scan-run-detail.md) | Q–S | ScanRunDetail page (header + lifecycle + target table + live events + findings panel + evidence panel) |
| 7 | [phase-7-integration.md](phase-7-integration.md) | T–V | Route swaps in App.tsx, slice-2 e2e test |
| 8 | [phase-8-final-pass.md](phase-8-final-pass.md) | — | Full coverage, vite build, compose smoke vs real backend |

## Acceptance for slice 2

When the entire plan is green:

- `cd frontend && npm run test:coverage` shows 100/100/100/100 on `src/**/*.{ts,tsx}` minus the documented exclusions.
- Five sidebar items previously routing to `<ComingSoon/>` now route to real pages: Targets, Stubs, Scan Runs, plus the Create Scan Run sub-route, plus the Scan Run detail sub-route.
- `CurrentProjectChip` switch link no longer goes to a dead end — clicking it lands on `/projects` and each row exposes a "Set as current" action.
- Compose smoke (real backend on `refactor/archive-v1`): full operator path runs end-to-end — create project → add three targets → open stubs → pick `1.1` → create scan run → start → see live events streaming → see Findings + Evidence populate → stop / let it complete.
