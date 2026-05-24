# Mission Viewer — Data Flow

## REST queries

| Query | Endpoint | Key | Notes |
|-------|----------|-----|-------|
| Session detail | `GET /api/agent-sessions/:id/` | `["missions", id]` | Canonical session state; includes `scan_run`, `active_phases`, `mission_budget`, `consumed_budget` |
| Turns | `GET /api/agent-sessions/:id/turns/?page_size=200` | `["missions", id, "turns"]` | Paginated; ascending by `index`; each turn nests `actions[]` |
| Notes | `GET /api/agent-sessions/:id/notes/?page_size=200` | `["missions", id, "notes"]` | Paginated; each note includes `turn_index` for grouping |

Session detail may poll every 2 s while status is non-terminal as a
safety net.  Turns and notes do not poll unconditionally; they refetch
from SSE-driven invalidation, manual retry, and normal React Query
focus/reconnect behaviour.  If `next !== null` on turns or notes, render
a truncation hint instead of silently hiding rows.

## SSE live updates

1. Session response provides `scan_run` UUID.
2. `useScanRunEvents(scanRunId, { livePolling: !isTerminal })` opens the
   existing SSE stream at `/sse/scan-runs/:id/events/`.
3. Backend sends unnamed SSE message frames; `type` remains inside JSON
   `data`, so the existing `onmessage` hook receives all events.
4. `useAgentEvents` wrapper filters to `agent.*` events where
   `data.session_id === sessionId`.
5. Processed event IDs tracked in a `useRef<Set<string>>()` to prevent
   duplicate invalidation on re-render.

### Invalidation map

| SSE event | Invalidates |
|-----------|-------------|
| `agent.session_started` | session detail |
| `agent.action_executed` | turns query |
| `agent.action_denied` | turns query |
| `agent.phase_changed` | session detail |
| `agent.mission_finished` | session detail |
| `agent.note_created` | notes query |

## Budget snapshot

SSE events carry a `budget_snapshot` in their data.  Stored as a local
overlay (`optimisticBudgetSnapshot`), cleared when:

- `sessionId` changes
- Session query refetches successfully
- Terminal status arrives

Rendered as `optimisticBudgetSnapshot ?? session.consumed_budget`.
Never written to React Query cache.

## Terminal states

`completed`, `failed`, `stopped` → close SSE, stop polling, show final
status in header.  If `agent.mission_finished` includes a reason, show it
until the next session refetch; session detail remains canonical.

## Out of scope

`POST /api/agent-sessions/` belongs to the Start Mission flow on another
page.  The Mission Viewer slice consumes existing sessions only.
