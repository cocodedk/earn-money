# Mission Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a real-time Mission Viewer page at `/missions/:sessionId` that shows the V3 LLM agent working turn-by-turn in a chat-style story timeline.

**Architecture:** Single-page read-only viewer with a sticky MissionStrip header and a scrolling StoryTimeline body. REST queries (session, turns, notes) are the source of truth; SSE events trigger React Query invalidation and provide an optimistic budget overlay. All components under `features/missions/`, each under 200 lines.

**Tech Stack:** React, TypeScript, React Query, Vitest, MSW, Tailwind CSS

**Spec:** [docs/superpowers/specs/2026-05-23-mission-viewer/](../../specs/2026-05-23-mission-viewer/01-overview.md)

---

## Table of Contents

### Foundation

| Task | File | Description |
|------|------|-------------|
| 1 | [tasks/01-types.md](tasks/01-types.md) | TypeScript types for session, turn, action, observation, note |
| 2 | [tasks/02-fixtures.md](tasks/02-fixtures.md) | Test fixture factories (`makeSession`, `makeTurn`, etc.) |

### Routing and Data

| Task | File | Description |
|------|------|-------------|
| 3 | [tasks/03-route.md](tasks/03-route.md) | Add `/missions/:sessionId` route and `missionDetailPath` helper |
| 4 | [tasks/04-api-hooks.md](tasks/04-api-hooks.md) | React Query hooks: `useSessionQuery`, `useTurnsQuery`, `useNotesQuery` |

### Pure Logic

| Task | File | Description |
|------|------|-------------|
| 5 | [tasks/05-describe-turn.md](tasks/05-describe-turn.md) | `describeTurn()` — plain-language mapper for turn cards |

### UI Components

| Task | File | Description |
|------|------|-------------|
| 6 | [tasks/06-turn-card.md](tasks/06-turn-card.md) | `TurnCard` — status icon, text, phase badge, collapsible Details |
| 7 | [tasks/07-mission-strip.md](tasks/07-mission-strip.md) | `MissionStrip` — sticky header with phases and budget counter |
| 8 | [tasks/08-story-timeline.md](tasks/08-story-timeline.md) | `StoryTimeline` — scrolling turn list with inline notes + auto-scroll |

### SSE Integration

| Task | File | Description |
|------|------|-------------|
| 9 | [tasks/09-use-agent-events.md](tasks/09-use-agent-events.md) | `useAgentEvents` — SSE filter, query invalidation, budget overlay |

### Page Wiring

| Task | File | Description |
|------|------|-------------|
| 10 | [tasks/10-mission-viewer-page.md](tasks/10-mission-viewer-page.md) | `MissionViewerPage` — route shell, `DetailPageGuard`, App.tsx wiring |

## File Structure

```
frontend/src/features/missions/
  types.ts                  — all TypeScript types
  api.ts                    — React Query hooks and keys
  describeTurn.ts           — pure plain-language mapper
  describeTurn.test.ts      — unit tests for describeTurn
  useAgentEvents.ts         — SSE wrapper with invalidation
  useAgentEvents.test.tsx   — SSE hook tests
  TurnCard.tsx              — single turn card component
  TurnCard.test.tsx         — turn card tests
  MissionStrip.tsx          — sticky header component
  MissionStrip.test.tsx     — header tests
  StoryTimeline.tsx         — scrolling timeline component
  StoryTimeline.test.tsx    — timeline tests
  MissionViewerPage.tsx     — route shell page
  MissionViewerPage.test.tsx — integration tests
  __fixtures__/
    mission.ts              — factory functions
```

Modified files:
- `frontend/src/app/routes.ts` — add `missionDetail` route
- `frontend/src/app/routes.test.ts` — add route tests
- `frontend/src/App.tsx` — add `<Route>` entry

## Dependencies

Tasks 1-2 are independent. Tasks 3-4 depend on Task 1. Task 5 depends on Task 1. Task 6 depends on Tasks 1-2 and 5. Task 7 depends on Tasks 1-2. Task 8 depends on Task 6. Task 9 depends on Task 4 and the existing scan-run SSE hook. Task 10 depends on all previous tasks.

## Implementation Guardrails

- Preserve existing app conventions for route helpers, `http`, `DetailPageGuard`, `Callout`, React Query wrappers, MSW server setup, and scan-run SSE events. If a referenced helper has a different local API, adapt the mission code to that existing API and keep the tests proving the behavior in these tasks.
- Keep every new component under 200 lines. If a component grows, extract a local helper component in `frontend/src/features/missions/` and add or update the matching test.
- Route helper output must path-encode the `sessionId` segment. The app will normally pass UUIDs, but the helper should still be safe for arbitrary route-param strings.
- Timeline ordering must not rely on backend default ordering. Render turns ascending by `turn.index`; notes remain attached by `turn_index`.
- SSE handling must tolerate unknown future `agent.*` events. Unknown matching events may update the optimistic budget overlay, but only the known event sets should trigger targeted query invalidation.

## Verification And Rollback

- Each task includes a narrow failing-test step before implementation and a passing-test step after implementation. Do not skip the failing step unless the target code already exists; in that case, record that the test unexpectedly passed and continue.
- Final verification is the mission feature tests, route tests, full Vitest run, and TypeScript check.
- Roll back a failed task by reverting only the files listed in that task, then rerun the previous task's passing test command to confirm the earlier checkpoint is still intact.
