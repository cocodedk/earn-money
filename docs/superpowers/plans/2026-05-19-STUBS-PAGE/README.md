# Stubs page — slice 1 implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `/stubs` (list) and `/stubs/:slug` (detail) so the operator can browse the cookbook tree from the dashboard. Replaces `<ComingSoon name="Stubs" />` in `App.tsx`.

**Architecture:** Mirror of the Projects/Targets feature shape with two adaptations: hooks return a bare array (the stubs endpoint is not paginated), and a per-id detail query is added. Markdown body is rendered as `<pre>` — no markdown-renderer dep.

**Spec:** [`../../specs/2026-05-19-stubs-page-design.md`](../../specs/2026-05-19-stubs-page-design.md)
**Page spec:** [`../../specs/2026-05-18-MVP-GUI/04-stubs.md`](../../specs/2026-05-18-MVP-GUI/04-stubs.md)
**API contract:** [`../../specs/2026-05-18-MVP-GUI/11-api.md`](../../specs/2026-05-18-MVP-GUI/11-api.md) — `GET /api/stubs/` (bare array, no pagination) and `GET /api/stubs/<phase.spec>/` (includes `body`).
**Backend (live):** `backend/apps/stubs/views.py`, `backend/apps/stubs/registry.py`. Peer agent-em-backend confirmed shape is stable.

**Branch:** Commit on `refactor/archive-v1`. Peer ping at slice completion only per the chat-noise-floor rule.

**Conventional commits:** `feat(frontend):`, `test(frontend):`, `docs(frontend):`, `refactor(frontend):`. `commit-msg` hook enforces.

## Phase index

| Phase | File | Task | Ships |
|-------|------|------|-------|
| 1 | [phase-1-types-routes.md](phase-1-types-routes.md) | A | `StubStatus`, `StubSummary`, `Stub` types; `ROUTES.stubDetail` |
| 2 | [phase-2-api-client.md](phase-2-api-client.md) | B | `useStubsQuery`, `useStubQuery`, `STUBS_KEY`, `withBareArray` helper |
| 3 | [phase-3-stubs-list.md](phase-3-stubs-list.md) | C | `StubsList` page with status-badge palette and slug-as-link |
| 4 | [phase-4-stub-detail.md](phase-4-stub-detail.md) | D | `StubDetail` page with markdown body + 404 branch |
| 5 | [phase-5-app-wire-e2e.md](phase-5-app-wire-e2e.md) | E | Swap `App.tsx` ComingSoon → real; extend E2E list → detail → back |

## Definition of done

- All five phases shipped on `refactor/archive-v1`.
- `cd frontend && npm test -- --coverage && npm run build` all green; coverage 100/100/100/100.
- `/simplify` returns no actionable findings after final commit.
- Operator can: open `/stubs` → click any slug → see detail with markdown body → click back → return to list.
- Peer pinged once on slice completion (not per phase, per chat-noise-floor).
