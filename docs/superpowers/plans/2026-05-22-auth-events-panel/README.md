# Auth events panel implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Each `task-N-*.md` file is self-contained and uses checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface the three Phase 2 auth events (`AUTH_PROBE_REFUSED`, `AUTH_FIXTURE_REQUIRED`, `AUTH_FINDING_CANDIDATE`) on the target result page as colour-coded expand-in-place pills, so the operator can triage them at a glance even after the full events feed has paginated.

**Architecture:** New `TargetAuthEventsPanel` slot above `TargetEventsTable` on `TargetResult`. Dedicated `useTargetAuthEventsQuery(targetId)` issues a single paginated request with multi-value `?type=` and reverses the backend's oldest-first results client-side. Reuses existing component patterns: `TargetSection` for the wrapper feel, a new `AuthEventPill` for the per-event row.

**Tech Stack:** React + TypeScript + Vite + Vitest + Testing Library + MSW + React Query. CSS Modules for styling. Tokens from existing CSS variables.

**Spec:** `docs/superpowers/specs/2026-05-22-auth-events-panel-design.md`

---

## File structure

**Create:**
- `frontend/src/features/targets/api.auth-events.ts` — query hook
- `frontend/src/features/targets/api.auth-events.test.tsx` — hook unit tests
- `frontend/src/features/targets/TargetResult/AuthEventPill.tsx`
- `frontend/src/features/targets/TargetResult/AuthEventPill.module.css`
- `frontend/src/features/targets/TargetResult/AuthEventPill.test.tsx`
- `frontend/src/features/targets/TargetResult/TargetAuthEventsPanel.tsx`
- `frontend/src/features/targets/TargetResult/TargetAuthEventsPanel.module.css`
- `frontend/src/features/targets/TargetResult/TargetAuthEventsPanel.test.tsx`

**Modify:**
- `frontend/src/features/targets/TargetResult.tsx` — render `TargetAuthEventsPanel` between `TargetEvidencePanel` and `TargetEventsTable`
- `frontend/src/features/targets/TargetResult.test.tsx` — extend happy-path test to assert the new panel slot
- `frontend/src/App.e2e.target-result.test.tsx` — extend the e2e to land on a target with one auth event

## Tasks (execute in order)

1. [Task 1 — query hook: URL + reverse](task-1-query-hook.md)
2. [Task 2 — `AuthEventPill` component](task-2-pill-component.md)
3. [Task 3 — `TargetAuthEventsPanel` component](task-3-panel-component.md)
4. [Task 4 — mount panel on `TargetResult`](task-4-mount.md)
5. [Task 5 — e2e smoke](task-5-e2e.md)
6. [Task 6 — spec-review + code-review + PR](task-6-finalize.md)

## Self-review

- **Spec coverage:** every section of the spec maps to at least one task (hook in T1, pill in T2, panel + empty + +N in T3, page mount in T4, e2e in T5, spec-review in T6).
- **No placeholders:** all code blocks contain real code. Each test asserts behaviour, not implementation.
- **Type consistency:** `useTargetAuthEventsQuery`, `AuthEventPill`, `TargetAuthEventsPanel`, `AUTH_EVENT_TYPES`, the `event.data` field, and the three `data-variant` strings (`warning`/`info`/`alert`) are consistent across every task.
- **TDD:** each task starts with a failing test, then minimal code, then more tests.
- **File sizes:** every new code/test file is well under the 200-line cap.
