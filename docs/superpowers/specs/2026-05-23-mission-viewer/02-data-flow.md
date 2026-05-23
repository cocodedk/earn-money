# Mission Viewer — Data Flow

## REST queries

| Query | Endpoint | Key | Notes |
|-------|----------|-----|-------|
| Session detail | `GET /api/agent-sessions/:id/` | `["missions", id]` | Includes `scan_run`, `active_phases`, `consumed_budget` |
| Turns | `GET /api/agent-sessions/:id/turns/?page_size=200` | `["missions", id, "turns"]` | Ascending by `index`; each turn nests `actions[]` |
| Notes | `GET /api/agent-sessions/:id/notes/` | `["missions", id, "notes"]` | Each note includes `turn_index` for grouping |

Session detail polls every 2 s while status is non-terminal.
Turns and notes use `refetchInterval` gated on live-polling flag.

## SSE live updates

1. Session response provides `scan_run` UUID.
2. `useScanRunEvents(scanRunId, { livePolling: !isTerminal })` opens the
   existing SSE stream at `/sse/scan-runs/:id/events/`.
3. `useAgentEvents` wrapper filters to `agent.*` events where
   `data.session_id === sessionId`.
4. Processed event IDs tracked in a `useRef<Set<string>>()` to prevent
   duplicate invalidation on re-render.

### Invalidation map

| SSE event | Invalidates |
|-----------|-------------|
| `agent.action_executed` | turns query |
| `agent.action_denied` | turns query |
| `agent.phase_changed` | session detail |
| `agent.mission_finished` | session detail |
| `agent.note_created` | notes query |

## Budget snapshot

SSE events carry a `budget_snapshot` in their data.  Stored as a local
overlay (`optimisticBudgetSnapshot`), cleared when:

- `sessionId` changes
- Session query refetches with equal-or-newer budget state
- Terminal status arrives

Rendered as `optimisticBudgetSnapshot ?? session.consumed_budget`.
Never written to React Query cache.

## Terminal states

`completed`, `failed`, `stopped` → close SSE, stop polling, show final
status in header.
