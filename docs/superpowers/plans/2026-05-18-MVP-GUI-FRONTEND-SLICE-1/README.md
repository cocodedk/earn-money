# MVP-GUI Frontend Slice 1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the smallest end-to-end vertical slice of the scanner dashboard — app shell with sidebar + top bar + connection status pill, a working Projects list page (`/projects`), and a Create Project page (`/projects/new`) — all wired to the contract locked with `agent-em-backend` in `docs/superpowers/specs/2026-05-18-MVP-GUI/11-api.md`. Other nav items route to a `ComingSoon` placeholder so the shell is end-to-end testable today and each subsequent slice swaps one placeholder for a real page.

**Architecture:** Feature-first folder layout under `frontend/src/`. React Router v6 owns navigation. TanStack Query v5 owns server state + cache invalidation. Tailwind v3 utilities compose into CSS-Module classes via `@apply` so JSX stays clean and styles stay scoped to each component file. MSW (Mock Service Worker) backs every test against the locked API shape; the same handlers also serve as a runtime fallback when the real backend is unreachable in dev. Strict TDD — every component, hook, and page lands behind a failing test; Vitest enforces 100% line + branch + function + statement coverage.

**Tech Stack:**
- React 18, Vite 8, TypeScript (strict, `noUnusedLocals`, `noUnusedParameters`)
- React Router v6 (`react-router-dom`)
- TanStack Query v5 (`@tanstack/react-query`)
- Tailwind CSS v3 (`tailwindcss`, `postcss`, `autoprefixer`)
- Self-hosted fonts: `@fontsource/inter` + `@fontsource/jetbrains-mono`
- Vitest 4, `@vitest/coverage-v8`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, `jsdom`
- MSW v2 (`msw`) for network mocking

(Vite + Vitest bumped from 5/2 to 8/4 mid-execution to clear the `esbuild` dev-server CORS advisory. React, Router, Tailwind, TS held at their original majors to keep slice-1 stable.)

**Branch:** Commit on `refactor/archive-v1` (same branch peer is using). Do NOT merge to main until 1.1 framework-detection runs end-to-end against `target.cocode.dk` fixtures — slice 1 is just the dashboard chassis.

**Conventional commits:** every task ends with a single commit using `feat(frontend):`, `test(frontend):`, `chore(frontend):`, or `docs(frontend):` as appropriate. The `commit-msg` hook enforces this.

## Phase index

| Phase | File | Tasks | Ships |
|-------|------|-------|-------|
| 0 | [phase-0-foundation.md](phase-0-foundation.md) | A–D | Deps, Tailwind, Vitest, MSW scaffolding |
| 1 | [phase-1-lib.md](phase-1-lib.md) | E–F | API DTO types, `http` client, `parseApiError` |
| 2 | [phase-2-primitives.md](phase-2-primitives.md) | G–L | Button, Callout, EmptyState, PageHeader, Table, FormField/TextInput/Textarea |
| 3 | [phase-3-app-shell.md](phase-3-app-shell.md) | M–O | Providers, Layout shell, ComingSoon placeholder |
| 4 | [phase-4-health-pill.md](phase-4-health-pill.md) | P–Q | `useConnectionStatus`, `ConnectionPill` |
| 5 | [phase-5-projects.md](phase-5-projects.md) | R–T | Projects API client, ProjectsList page, CreateProject page |
| 6 | [phase-6-current-project.md](phase-6-current-project.md) | U–V | `useCurrentProject`, `CurrentProjectChip` |
| 7 | [phase-7-integration.md](phase-7-integration.md) | W–Y | App wiring, sidebar active highlight, E2E happy path |

## Acceptance for slice 1

When the entire plan is green:

- `cd frontend && npm run test -- --coverage` shows 100/100/100/100 on `src/**/*.{ts,tsx}` except the documented exclusions.
- `docker compose up --build` brings the stack up; `http://localhost/` shows the dashboard with the sidebar, top bar, and Projects page.
- Creating a project via the form invalidates the list query and routes back to `/projects` with the new row visible.
- Sidebar items for Targets / Stubs / Scan Runs / Findings / Evidence / Settings each route to a `ComingSoon` page with the page name + "Not built yet." text.
- Top-bar connection pill is green when `/api/health/` returns `{status: "ok", db: true}`, red otherwise.
- Refreshing the page on any route preserves the route.
