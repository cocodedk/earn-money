---
slug: slice-1-scoreboard
status: done         # draft | in-progress | done
date: 2026-05-23
implemented: 2026-05-23
---

# Slice 1 — Juice Shop Scoreboard Mission

Minimal proof of loop with real contracts. Proves the LLM can drive Playwright, reason over
structured observations, and find something automation alone cannot.

## Scope

### In scope

- **Models**: AgentSession, AgentTurn, AgentAction, AgentObservation, AgentNote
- **Controller loop** with three phases: recon → enumerate → report/stop
- **7 actions**: `observe_page`, `navigate`, `inspect_asset`, `store_note`, `submit_candidate`,
  `request_phase_transition`, `stop`
- **PageObservation** with a11y snapshot, elements (with `aria_role`, `accessible_name`),
  standalone inputs, discovered routes/assets, network, cookies (no values), console
- **`inspect_asset`** for same-origin JS/CSS — controller fetches/truncates/returns excerpts
- **Basic mission budget** (turns, wall-clock, HTTP requests, asset inspections) + phase budgets
  for recon and enumerate
- **Plateau detection** (no new routes/elements after N turns)
- **Single frontier model**, prompt/response artifact refs on every turn
- **Events**: `agent.session_started`, `agent.action_executed`, `agent.action_denied`,
  `agent.phase_changed`, `agent.note_created`, `agent.mission_finished`
- **Strict JSON schema validation** on all actions
- **Controller-assigned element/URL/asset IDs** throughout
- **`submit_candidate`** writes `AgentNote(note_type="candidate")` in slice 1 and emits
  `agent.note_created`. `agent.candidate_created` is deferred with Finding promotion.
- **Lab mode only** (`autonomy_mode=lab_free_run`)

### Out of scope (deferred)

- AgentCheckpoint, operator gates (lab mode logs would-have-checkpointed moments)
- AgentPhaseTransition table
- probe/verify phases
- v2 stub integration (`run_stub`)
- OSS tool integration (`run_tool`)
- `click`, `fill_form`, `submit_form`, `http_request`, `request_verify`
- Finding promotion from candidates
- Multi-provider routing, cheap/frontier escalation
- Delta observations (full observations only in slice 1)
- RoE amendment records
- Celery task integration

## Acceptance criteria

```gherkin
Given  Juice Shop at target.cocode.dk or juiceshop.cocode.dk
When   V3 agent mission runs with profile juice_shop_scoreboard
Then   it observes the page and discovers assets
And    inspects a JS bundle and identifies a route containing "score-board"
And    navigates to the scoreboard view (path or hash route)
And    records a submit_candidate with category hidden_route_discovered
And    supporting observations and actions are persisted as AgentObservation rows
And    mission completes within budget
And    all turns have prompt/response artifact refs and token counts
```

## Mission profile

```yaml
juice_shop_scoreboard:
  target: juiceshop.cocode.dk
  objective: "Find the hidden admin scoreboard page"
  success_category: hidden_route_discovered
  phases: [recon, enumerate, report]
  model_policy:
    primary_model: <frontier>
  budget:
    max_turns: 25
    max_runtime_seconds: 300
    max_llm_calls: 30
    max_http_requests: 60
    max_browser_actions: 40
    max_asset_inspections: 10
  phase_budgets:
    recon:
      max_turns: 6
      max_http_requests: 20
      max_asset_inspections: 5
    enumerate:
      max_turns: 14
      max_http_requests: 35
      max_asset_inspections: 5
    report:
      max_turns: 3
      max_http_requests: 0
      max_asset_inspections: 0
```

## What this proves

- LLM can read, infer, remember, and follow clues that pattern-matching stubs cannot
- Controller mediates all execution — LLM never touches Playwright directly
- Typed actions + strict schema validation work end to end
- PageObservation is rich enough for the LLM to reason but lean enough to stay in budget
- Persistence spine (Session → Turn → Action → Observation) captures everything for replay
- Budget and plateau detection prevent runaway sessions
