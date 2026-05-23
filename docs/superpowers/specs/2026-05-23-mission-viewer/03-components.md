# Mission Viewer — Components

All files under `features/missions/`.  Each under 200 lines.

## Runtime files

| File | Responsibility |
|------|---------------|
| `MissionViewerPage.tsx` | Route shell: read `:sessionId`, session query via `DetailPageGuard`, SSE hook, pass data to children |
| `MissionStrip.tsx` | Sticky top strip: mission name, status pill, phase chips from `active_phases`, budget counter |
| `StoryTimeline.tsx` | Scrolling list of `TurnCard` + inline notebook entries; auto-scroll to newest unless user scrolled away |
| `TurnCard.tsx` | Single turn: status icon (green/yellow/red/blue), plain-language sentence from `describeTurn`, phase badge, relative timestamp, collapsible Details |
| `describeTurn.ts` | Pure function `(turn) => { title, result, tone }` — all plain-language mapping in one place |
| `api.ts` | React Query hooks: `useSessionQuery`, `useTurnsQuery`, `useNotesQuery`, `useCreateMissionMutation`, query keys |
| `useAgentEvents.ts` | SSE wrapper: filters `agent.*` by session, routes to invalidation, manages `optimisticBudgetSnapshot` |
| `types.ts` | `AgentSession`, `AgentTurn`, `AgentAction`, `AgentNote`, phase/status/action-type enums |

## Fixtures and tests

| File | Purpose |
|------|---------|
| `__fixtures__/mission.ts` | `makeSession()`, `makeTurn()`, `makeAction()`, `makeNote()` factories |
| `describeTurn.test.ts` | Unit tests for all action/status combinations |
| `MissionViewerPage.test.tsx` | Integration: session loads, SSE opens, turn invalidation works |
| `MissionStrip.test.tsx` | Phase chips render `active_phases`, budget degrades gracefully |
| `StoryTimeline.test.tsx` | Renders turns + inline notes, auto-scroll behaviour |
| `TurnCard.test.tsx` | Status icons, Details disclosure, timestamps |
| `api.test.ts` | Query hooks with MSW handlers |
| `useAgentEvents.test.tsx` | SSE filter, duplicate-ID guard, budget overlay, terminal close |

## Shared components reused

- `DetailPageGuard` — loading / 404 / error for session query
- `Callout` — inline error for turns/notes fetch failures (page stays up)
- `PageHeader` — not used; replaced by `MissionStrip`

## Auto-scroll behaviour

Reuse pattern from `ScanRunLiveEventsPanel`: track whether user has
manually scrolled away; if not, scroll to bottom on new turn.  Reset
scroll-lock when user scrolls back to bottom.
