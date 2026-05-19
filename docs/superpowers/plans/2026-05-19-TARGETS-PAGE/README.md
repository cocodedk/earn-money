# Targets page — slice 1 implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `/targets` (list) and `/targets/new` (create) so the operator can add and view scan targets through the dashboard. Replaces the two `<ComingSoon name="Targets" />` routes in `App.tsx`.

**Architecture:** Mirror of the existing Projects feature at `frontend/src/features/projects/`. Two route components, one new feature directory, no new component primitives. The Project column on the list page joins target.project (UUID) → project.name via the cached `useProjectsQuery` — zero extra fetches in the common case. Create form has a tight base_url validation pipeline (trim → scheme + authority regex → WHATWG URL parse backstop) vetted by codex:rescue across two REJECT rounds.

**Tech Stack:** Same as slice 1 — React 18 + Vite 8 + TS strict, React Router v6, TanStack Query v5, Tailwind v3, Vitest 4 + MSW v2, 100% line+branch coverage threshold.

**Spec:** [`../../specs/2026-05-19-targets-page-design.md`](../../specs/2026-05-19-targets-page-design.md)
**API contract:** [`../../specs/2026-05-18-MVP-GUI/11-api.md`](../../specs/2026-05-18-MVP-GUI/11-api.md) — `/api/targets/` GET/POST/GET-by-id
**Page spec:** [`../../specs/2026-05-18-MVP-GUI/03-targets.md`](../../specs/2026-05-18-MVP-GUI/03-targets.md)
**Backend serializer (live):** `backend/apps/targets/serializers.py` at commit `6b9802d` — host/ip optional; host derives from `urlsplit(base_url).hostname`; blank ip → null.

**Branch:** Commit on `refactor/archive-v1` (current branch). No push without operator authorisation — the [Notify before push](../../../../.claude-personal/projects/-home-cocodedk-0-projects-earn-money/memory/feedback_notify_before_push.md) rule still applies. Quote SHAs when requesting auth.

**Conventional commits:** every task ends with a single commit using `feat(frontend):`, `test(frontend):`, `chore(frontend):`, or `docs(frontend):`. The `commit-msg` hook enforces this.

**Per-commit `/simplify`:** after each commit, run `/simplify` and iterate until the three review agents return no actionable findings. Each fixup is its own commit.

## Phase index

| Phase | File | Task | Ships |
|-------|------|------|-------|
| 1 | [phase-1-types-routes.md](phase-1-types-routes.md) | A | `Target` + `CreateTargetBody` types; `ROUTES.targetsNew` |
| 2 | [phase-2-api-client.md](phase-2-api-client.md) | B | `useTargetsQuery`, `useCreateTargetMutation`, cache invalidation |
| 3 | [phase-3-targets-list.md](phase-3-targets-list.md) | C | `TargetsList` page with project-name join, loading / empty / error branches |
| 4 | [phase-4-create-target.md](phase-4-create-target.md) | D | `CreateTarget` page with full validation pipeline + 12 test cases |
| 5 | [phase-5-app-wire-e2e.md](phase-5-app-wire-e2e.md) | E | Swap `App.tsx` ComingSoon → real components; extend E2E happy path |

## Definition of done

- All five phases shipped on `refactor/archive-v1`.
- `cd frontend && npm run typecheck && npm run lint && npm test -- --coverage` all green; coverage 100/100/100/100.
- `npm run build` produces a green production bundle.
- `/simplify` returns no actionable findings after the final commit.
- Manual smoke against live backend: operator can open `/targets` → click Create target → pick a project → enter `https://dvwa.cocode.dk` (host/ip blank) → submit → see the row with host `dvwa.cocode.dk` and ip `—`.
- Peer (`agent-em-backend`) notified on the bus at: plan committed; phase 5 green; final commit.

## Acceptance criteria (per spec)

Pulled forward from `2026-05-19-targets-page-design.md` § Acceptance criteria. Each maps to a step in this plan:

- All branches covered by tests → Phase 4 (12 CreateTarget cases) + Phase 3 (5 TargetsList cases).
- 100% line + branch coverage → enforced in every phase's commit script.
- No file exceeds 200 lines → Projects analogs are 60–90 lines; this plan's targets are similar.
- `/simplify` clean → applied per-commit, not deferred.

## Out of scope (verified — do NOT add)

- Edit / Retire / Delete target → backend has no PATCH/DELETE.
- Target-result page (`07-target-result.md`) → still ComingSoon for now.
- Server-side filter / search / sort, pagination UI, bulk add, project denormalisation onto Target.
