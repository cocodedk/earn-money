# Scan Run Detail 6C — Findings + Evidence panels

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the read-only Findings + Evidence panels below the 6B target table on `/scan-runs/:id`. Both panels are scoped to one scan run via `?scan_run=<uuid>`, self-poll every 2 s while the parent run is active, perform a terminal cancel+refetch flush when the parent transitions to a terminal status, and render a truncation footer when backend paginates (`data.next !== null`).

**Spec source:** [`../../specs/2026-05-18-MVP-GUI/06-scan-run-detail.md`](../../specs/2026-05-18-MVP-GUI/06-scan-run-detail.md) §Findings panel (lines 94–109) and §Evidence panel (lines 111–126). The umbrella spec also lists a §Live events panel (lines 59–92) — that ships as 6D (SSE), not here.

**Key-cascade contract:** Both new keys are *children* of `SCAN_RUNS_KEY` (mirroring `scanRunTargetRunsKey` in `frontend/src/features/scan-runs/api.ts:66-67`). Invalidating `SCAN_RUNS_KEY` cascades to all three child keys (target-runs, findings, evidence) — lifecycle mutations on a scan run trigger automatic refetch of every panel without explicit per-key invalidation in the mutation hooks.

**Backend lock:** em-backend on `main` ships `/api/findings/?scan_run=<uuid>` and `/api/evidence/?scan_run=<uuid>` with the documented filter logic in `backend/apps/findings/views.py` and `backend/apps/evidence/views.py`. Serializer shapes match the [[slice_3_reservoir]] `Finding` and `Evidence` types verbatim (verified 2026-05-20). DRF `PAGE_SIZE = 50` from 6B continues to apply.

**Reservoir reference:** `origin/feat/em-frontend-slice-3` already implements standalone `/findings` and `/evidence` pages with the same hooks. 6C **does not** merge or depend on that branch — we build fresh scan-run-scoped variants on `feat/em-frontend`. Slice-3 is read-only inspiration.

## Phase index

| Phase | File | Ships |
|-------|------|-------|
| 1 | [phase-1-types-and-hooks.md](phase-1-types-and-hooks.md) | `Finding`, `Evidence`, `Confidence`, `FindingStatus` types; `useScanRunFindingsQuery` + `useScanRunEvidenceQuery` with polling + terminal flush; MSW handlers |
| 2 | [phase-2-panels.md](phase-2-panels.md) | `ScanRunFindingsPanel`, `ScanRunEvidencePanel` components (raw `<table>` mirror 6B), per-row `data-testid`, truncation footer, error callout |
| 3 | [phase-3-wire-app-e2e.md](phase-3-wire-app-e2e.md) | Wire both panels into `ScanRunDetail`; integration tests for transitions; E2E that asserts header + target table + findings panel + evidence panel all render |

## Definition of done

- 100 % line + branch coverage on new and modified files.
- `npm test`, `npm test -- --coverage`, `npm run build` all green.
- `/simplify` rounds clean after each commit (per-commit gate; fix → re-run until quiet).
- No new or modified file over 200 lines. `App.e2e.test.tsx` stays untouched (deferred refactor).
- Operator can open `/scan-runs/:id` and see one row per finding and one row per evidence record for that run, both updating within 2 s while the parent run is `running`.
- Truncation footer renders when backend returns `next !== null` (mirrors 6B target-table behaviour).
- Single peer ping to em-backend at slice completion (chat-noise-floor rule).

## Out of scope for 6C

- **Filter UI** — Findings/Evidence panels are scan-run-scoped only. No project/target/severity dropdowns. Filter UI is part of the standalone `/findings` and `/evidence` pages that ship separately from the slice-3 reservoir.
- **Detail page navigation** — Title cells render as plain text (no `<Link to="/findings/:id">`). The `/findings/:id` and `/evidence/:id` routes don't exist on `feat/em-frontend` yet; wiring dead links would fail E2E.
- **Actions column** — The MVP umbrella spec lists "Actions" on both panels without defining them; deferred to the slice that ships detail-page routes.
- **Live events panel (SSE)** — 6D.

## TDD rules

- Strict TDD on every step: failing test first, then implementation. No production code without a failing test.
- 100 % line + branch coverage on the production code path (frontend `src/`). Coverage gates measured by `npm test -- --coverage`.
- House style: per-row `data-testid="finding-row-{id}"` and `data-testid="evidence-row-{id}"` (same convention as 6B's `target-run-row-{id}`).
- Truncation footer testid: `data-testid="findings-truncation"` and `data-testid="evidence-truncation"`.
- Inline timestamp formatter: `fmt(ts) = ts ? ts.slice(0, 10) : "—"` (date only for `created_at`, matching slice-3 reservoir style).

## Naming conventions

| Concept | Identifier |
|---------|------------|
| Type for one finding | `Finding` (in `types/api.ts`) |
| Type for one evidence record | `Evidence` (in `types/api.ts`) |
| Query hook (findings, scan-run-scoped) | `useScanRunFindingsQuery(scanRunId, livePolling)` |
| Query hook (evidence, scan-run-scoped) | `useScanRunEvidenceQuery(scanRunId, livePolling)` |
| Query key (findings) | `scanRunFindingsKey(scanRunId) = [...SCAN_RUNS_KEY, scanRunId, "findings"]` |
| Query key (evidence) | `scanRunEvidenceKey(scanRunId) = [...SCAN_RUNS_KEY, scanRunId, "evidence"]` |
| Findings panel component | `ScanRunFindingsPanel` |
| Evidence panel component | `ScanRunEvidencePanel` |
| Findings panel file | `frontend/src/features/scan-runs/ScanRunFindingsPanel.tsx` |
| Evidence panel file | `frontend/src/features/scan-runs/ScanRunEvidencePanel.tsx` |
