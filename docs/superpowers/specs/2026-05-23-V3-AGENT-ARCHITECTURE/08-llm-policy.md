# LLM & Model Policy

Frontier-first for MVP. Fixed routing profile per mission — no live model roulette per turn.

## Model policy (stored on AgentSession)

```yaml
model_policy:
  primary_model:     # default for most turns
  cheap_model:       # observation compression, summarization
  frontier_model:    # escalation target for risky decisions
  verifier_model:    # candidate verification turns
  fallback_models:   # ordered list, operational failure path only
  routing_profile_snapshot:
    structured_output: json_schema | tool_call | json_mode | none
    vision: true | false
    max_context_tokens: int
    pricing: object
    selected_at: datetime
```

## Routing rules

| Turn type | Model tier |
|-----------|-----------|
| Routine observe/enumerate | Primary (cheaper post-MVP) |
| Phase transitions | Frontier |
| Probe actions that mutate state | Frontier |
| Verify / candidate promotion | Frontier |
| Report drafting | Frontier or strong mid-tier |
| Observation compression / summarization | Cheap model or deterministic code |

## Escalation triggers (cheap → frontier)

- Invalid JSON/action emitted twice
- Repeated policy denials
- No progress for N turns
- Entering probe, verify, or impact_proof
- Creating or promoting medium/high/critical candidates
- Checkpoint request/response handling
- Prompt-injection or sensitive-data risk detected
- Complex or contradictory PageObservation

## Fallback policy

Fallback models are used only on provider/model outage, rate limit, or timeout — not for
quality-based rerouting. The controller explicitly escalates when quality is the issue.

## Provider routing

- Direct Anthropic/OpenAI for frontier production paths
- OpenRouter for cheaper lab runs, model scouting, and controlled fallback
- OpenRouter scout produces a pre-mission routing profile, not per-turn selection

## Per-turn audit

Every AgentTurn records: model used, provider, version, input/output tokens, cost estimate,
prompt/response hashes, and artifact refs.

A model that cannot reliably return strict JSON is not acceptable even if cheap. The
`structured_output` field in the routing profile gates model eligibility.

## Slice 1

Single frontier model, no routing logic. `model_policy` fields exist on AgentSession but only
`primary_model` is used. Prompt/response artifact refs stored from day one.
