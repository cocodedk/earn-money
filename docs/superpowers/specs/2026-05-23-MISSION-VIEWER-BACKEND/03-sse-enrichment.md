# SSE & Event Enrichment

## Generic SSE Frames (Breaking Change)

### Current behavior

`_format()` in `backend/apps/events/views.py` emits named SSE events:

```
id: <uuid>
event: agent.session_started
data: {"type": "agent.session_started", ...}
```

Browser `EventSource.onmessage` only fires for unnamed frames. The
frontend currently uses `onmessage`, so named events are invisible
unless it registers `addEventListener("agent.session_started", ...)`.

### New behavior

Drop the `event:` line from ALL SSE frames (not just agent events).
The event type is already in `data.type` — consumers key off that.

```
id: <uuid>
data: {"type": "agent.session_started", ...}
```

### Changes Required

1. `backend/apps/events/views.py` — remove `event:` line from `_format()`
2. Update SSE tests in `backend/apps/events/test_streaming.py` that
   assert `event: system.test` or similar named-event patterns
3. No frontend changes needed — existing `onmessage` handler already
   reads `data.type`

## Agent Event Enrichment

Enrich event payloads at emit time in `backend/apps/agent/event_log.py`.
The SSE stream serializes `Event.data` as-is — richer data at write
time means richer SSE frames automatically.

### agent.session_started (unchanged)

```json
{
  "session_id": "<uuid>",
  "mission_profile": "juice_shop_scoreboard",
  "autonomy_mode": "lab_free_run",
  "current_phase": "recon"
}
```

### agent.action_executed (enriched)

```json
{
  "session_id": "<uuid>",
  "turn_index": 3,
  "action_type": "observe_page",
  "goal": "Inspect the main page structure",
  "reason": "Need to find navigation links and JS bundles",
  "hypothesis": "Score-board link may be hidden in client-side routing",
  "budget_snapshot": {
    "turns": {"used": 4, "max": 25},
    "llm_calls": {"used": 4, "max": 30},
    "http_requests": {"used": 12, "max": 60}
  },
  "observation_summary": {
    "url": "https://juiceshop.cocode.dk/",
    "title": "OWASP Juice Shop",
    "route_count": 5,
    "asset_count": 3,
    "element_count": 22,
    "network_count": 8
  }
}
```

Changes to `emit_action_executed()`: accept `goal`, `reason`,
`hypothesis`, `budget_snapshot`, and `observation_summary` as
parameters. The caller (`controller_turn._execute`) passes them
after the action completes.

### agent.action_denied (enriched)

```json
{
  "session_id": "<uuid>",
  "turn_index": 2,
  "action_type": "http_request",
  "reason": "Denied by phase: http_request not allowed in recon",
  "goal": "Send crafted request to /api/Users",
  "budget_snapshot": { ... }
}
```

Changes to `emit_action_denied()`: accept `goal` and `budget_snapshot`.

### agent.phase_changed (enriched)

```json
{
  "session_id": "<uuid>",
  "from_phase": "recon",
  "to_phase": "enumerate",
  "reason": "auto-advance: plateau detected",
  "budget_snapshot": { ... }
}
```

Changes to `emit_phase_changed()`: accept `budget_snapshot`.

### agent.note_created (unchanged)

```json
{
  "session_id": "<uuid>",
  "note_type": "route",
  "turn_index": 5
}
```

### agent.mission_finished (enriched)

```json
{
  "session_id": "<uuid>",
  "status": "completed",
  "reason": "stop_action",
  "mission_profile": "juice_shop_scoreboard",
  "budget_snapshot": { ... }
}
```

Changes to `emit_mission_finished()`: accept `budget_snapshot`.

## Observation Summary Builder

New helper function in `event_log.py` or a small utility:

```python
def summarize_observation(obs_dict: dict) -> dict:
    """Compact summary of a page observation for SSE payloads."""
    return {
        "url": obs_dict.get("url", ""),
        "title": obs_dict.get("title", ""),
        "route_count": len(obs_dict.get("discovered", {}).get("routes", [])),
        "asset_count": len(obs_dict.get("discovered", {}).get("assets", [])),
        "element_count": (
            len(obs_dict.get("elements", {}).get("links", []))
            + len(obs_dict.get("elements", {}).get("buttons", []))
            + len(obs_dict.get("elements", {}).get("forms", []))
        ),
        "network_count": len(obs_dict.get("network", [])),
    }
```

Called from `controller_turn._execute_browser_action()` after building
the observation, passed to `emit_action_executed()`.
