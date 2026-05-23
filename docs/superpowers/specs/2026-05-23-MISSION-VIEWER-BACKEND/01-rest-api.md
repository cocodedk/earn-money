# REST API — Agent Session Endpoints

## New Files

- `backend/apps/agent/serializers.py` — serializers for all agent models
- `backend/apps/agent/views.py` — AgentSessionViewSet
- Registration in `backend/config/urls.py`: `router.register(r"agent/sessions", AgentSessionViewSet, basename="agent-session")`

## Endpoints

### GET /api/agent/sessions/

List agent sessions. Filters:
- `?status=running` — by session status
- `?target=<uuid>` — by target

Response: paginated list of session summaries.

### GET /api/agent/sessions/\<id\>/

Session detail. Includes:
- All AgentSession model fields
- `active_phases`: list of phase names from the mission profile (e.g. `["recon", "enumerate", "report"]`)
- `scan_run`: UUID (for SSE subscription)
- `target_base_url`: denormalized from target

### GET /api/agent/sessions/\<id\>/turns/

Paginated turn list, ordered by index ascending. Each turn nests:
- `actions[]`: array of AgentAction objects (1:1 in practice, array for correctness)
  - Each action nests `observations[]`: array of AgentObservation objects
- Turn fields: index, phase, model, input_tokens, output_tokens, cost_estimate, status, created_at, finished_at

### GET /api/agent/sessions/\<id\>/notes/

Paginated note list, ordered by created_at ascending.
Fields: note_type, content, evidence_refs, turn (index), created_at.

## Serializers

### AgentSessionSerializer

Read fields:
- id, scan_run, target, status, current_phase, mission_profile,
  autonomy_mode, mission_budget, consumed_budget, progress_counters,
  model_policy, roe_snapshot, started_at, finished_at, created_at, updated_at
- `active_phases` (SerializerMethodField): looked up from mission_profiles registry
- `target_base_url` (CharField, source="target.base_url")
- `scan_run_id` (UUIDField, source="scan_run.id")

Write fields (for POST /api/agent/sessions/): see 02-start-mission.md.

### AgentTurnSerializer

Fields: id, index, phase, model, input_tokens, output_tokens,
cost_estimate, status, created_at, finished_at.
Nested: `actions` (AgentActionSerializer, many=True, read_only=True).

### AgentActionSerializer

Fields: id, action_type, args_redacted, goal, reason, hypothesis,
validation_status, execution_status, denial_reason, executed_at, created_at.
Nested: `observations` (AgentObservationSerializer, many=True, read_only=True).

### AgentObservationSerializer

Fields: id, observation_type, data, artifact_refs, content_hash,
redactions, is_delta, created_at.

### AgentNoteSerializer

Fields: id, note_type, content, evidence_refs, turn_index
(IntegerField, source="turn.index"), created_at.

## Query Optimization

- Session list: `select_related("target", "scan_run")`
- Turns: `prefetch_related("actions__observations")` to avoid N+1
- Notes: `select_related("turn")` for turn_index denormalization
