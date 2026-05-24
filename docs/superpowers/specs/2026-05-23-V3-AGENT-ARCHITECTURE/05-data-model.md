---
slug: data-model
status: done         # draft | in-progress | done
---

# Data Model

V3 agent tables live under the existing scan-run spine. Agent working memory is separate from
the durable Finding/Evidence security-result layer.

## Relationship

```
ScanRun → ScanTargetRun → AgentSession (1:1)
                              ├── AgentTurn
                              │     └── AgentAction
                              │           └── AgentObservation
                              ├── AgentCheckpoint (future)
                              └── AgentNote
```

Not every thought, page snapshot, or weak hypothesis is a Finding/Evidence row.
Finding/Evidence stays the durable security-result layer. Agent tables hold working memory
and replay/debug traces.

## Models

### AgentSession

| Field | Type | Notes |
|-------|------|-------|
| `scan_target_run` | 1:1 FK | Links to existing spine |
| `scan_run` | FK | Denormalized for querying |
| `target` | FK | Denormalized for querying |
| `autonomy_mode` | enum | `lab_free_run` \| `real_checkpointed` |
| `current_phase` | enum | recon \| enumerate \| probe \| verify \| report |
| `status` | enum | pending \| running \| paused \| completed \| failed \| stopped |
| `mission_profile` | string | e.g. `juice_shop_scoreboard` |
| `model_policy` | JSON | primary/cheap/frontier/verifier model refs + routing snapshot |
| `roe_snapshot` | JSON | Frozen RoE at mission start (immutable) |
| `mission_budget` | JSON | All budget dimensions |
| `consumed_budget` | JSON | Current consumption |
| `progress_counters` | JSON | Routes, forms, endpoints, params, auth states, candidates discovered |
| `started_at` | datetime | |
| `finished_at` | datetime | nullable |

### AgentTurn

| Field | Type | Notes |
|-------|------|-------|
| `session` | FK | |
| `index` | int | Sequential turn number; unique together with session |
| `phase` | enum | Phase at time of turn |
| `model` | string | Which model was used |
| `prompt_artifact_ref` | string | Reference to stored prompt |
| `response_artifact_ref` | string | Reference to stored response |
| `prompt_hash` | string | For replay/dedup |
| `response_hash` | string | For replay/dedup |
| `input_tokens` | int | |
| `output_tokens` | int | |
| `cost_estimate` | decimal | nullable |
| `status` | enum | started \| action_proposed \| action_denied \| action_executed \| completed \| error |
| `created_at` | datetime | |
| `finished_at` | datetime | nullable |

Turn status lifecycle: `started` → `action_proposed` (LLM returned a typed action) →
`action_denied` (validation failed) or `action_executed` (tool ran) → `completed` (observation
persisted, turn finalized) or `error` (unrecoverable failure). Every turn reaches a terminal
state (`completed`, `action_denied`, `error`). `action_executed` is transient — the turn
moves to `completed` after observation persistence.

### AgentAction

| Field | Type | Notes |
|-------|------|-------|
| `turn` | FK | |
| `action_type` | enum | One of the 14 typed actions |
| `args_redacted` | JSON | Action args with sensitive values stripped |
| `goal` | text | Freeform LLM reasoning |
| `reason` | text | Freeform LLM reasoning |
| `hypothesis` | text | Freeform LLM reasoning |
| `validation_status` | enum | valid \| invalid_schema \| denied_phase \| denied_roe \| denied_budget \| denied_scope |
| `execution_status` | enum | pending \| skipped \| executed \| failed |
| `denial_reason` | text | nullable |
| `executed_at` | datetime | nullable |

### AgentObservation

| Field | Type | Notes |
|-------|------|-------|
| `action` | FK | |
| `observation_type` | enum | page \| http \| stub \| tool \| asset |
| `data` | JSON | Normalized PageObservation or tool summary |
| `artifact_refs` | JSON | Screenshots, larger logs (external) |
| `content_hash` | string | |
| `redactions` | JSON | List of what was stripped |
| `is_delta` | bool | Whether this is delta or full observation |
| `created_at` | datetime | |

### AgentNote

| Field | Type | Notes |
|-------|------|-------|
| `session` | FK | |
| `turn` | FK | |
| `note_type` | enum | hypothesis \| gap \| credential_label \| route \| parameter \| candidate |
| `content` | JSON | Structured note body |
| `evidence_refs` | JSON | Links to observations/actions |
| `created_at` | datetime | |

### AgentCheckpoint (future — not in slice 1)

| Field | Type | Notes |
|-------|------|-------|
| `session` | FK | |
| `phase` | enum | |
| `checkpoint_type` | string | |
| `scope_of_block` | enum | mission \| phase \| action \| candidate \| async |
| `status` | enum | pending \| approved \| denied \| expired |
| `request_payload` | JSON | Action, reason, evidence, budget, RoE status |
| `operator_decision` | enum | approve_once \| approve_class \| deny \| stop \| revise_scope |
| `timeout_at` | datetime | |
| `decided_at` | datetime | nullable |

## Event integration

Every important state change emits an Event row. Events are the audit/streaming trail, not the
source of truth for agent state.

Event types: `agent.session_started`, `agent.action_executed`, `agent.action_denied`,
`agent.phase_changed`, `agent.candidate_created`, `agent.note_created`,
`agent.checkpoint_created`, `agent.checkpoint_approved`, `agent.mission_finished`.

`agent.candidate_created` means Finding(status=candidate) was created. Use
`agent.note_created` for weaker working-memory notes.
