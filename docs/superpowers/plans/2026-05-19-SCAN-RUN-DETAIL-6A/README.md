# Scan Run Detail 6A — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `/scan-runs/:id` header + lifecycle buttons. Closes `<ComingSoon name="Scan Run Detail" />`. Lifts the per-row action shape into a `useScanRunActions(run)` hook reused by `ScanRunsList`.

**Spec:** [`../../specs/2026-05-19-scan-run-detail-6A-design.md`](../../specs/2026-05-19-scan-run-detail-6A-design.md)

## Phase index

| Phase | File | Ships |
|-------|------|-------|
| 1 | [phase-1-hooks.md](phase-1-hooks.md) | `useScanRunQuery(id)` + lift `useScanRunActions(run)` from ScanRunsList |
| 2 | [phase-2-detail-page.md](phase-2-detail-page.md) | `ScanRunDetail` component + tests |
| 3 | [phase-3-app-wire-e2e.md](phase-3-app-wire-e2e.md) | App.tsx wiring + E2E extension |

## Definition of done

- 100% line + branch coverage on new files; `ScanRunsList` tests still green after the hook lift.
- `npm test`, `npm run build` green.
- `/simplify` rounds clean.
- Operator can open `/scan-runs/:id` and drive the lifecycle from the header.
- Single peer ping at slice completion (chat-noise-floor).
