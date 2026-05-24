# Operator Checkpoints

Mixed blocking + async model based on risk. Labs run freely within budget; real programs pause
at risk thresholds.

## Blocking scopes

Not just boolean halt — five granularity levels:

| Scope | Effect |
|-------|--------|
| `mission_blocking` | Everything stops |
| `phase_blocking` | Cannot enter requested phase; safe prior-phase work may continue |
| `action_blocking` | Only this action/action class waits |
| `candidate_blocking` | Finding promotion/reporting waits; scanning may continue |
| `async_notice` | No halt — operator notified |

## Checkpoint triggers

| Trigger | Scope | Notes |
|---------|-------|-------|
| enumerate → probe (real program) | `phase_blocking` | State-changing actions become available |
| Enter impact_proof / exploit-chain | `mission_blocking` | Separate from normal probe; explicit RoE approval |
| First state-changing action class | `action_blocking` | POST, account creation, password reset, upload |
| RoE ambiguity | `mission_blocking` | Cannot infer permission from silence |
| Scope edge case | `mission_blocking` | Redirect to new host, CDN boundary, private IP, tenant boundary |
| Active OSS tool profile | `action_blocking` | Unless pre-approved in mission profile |
| PII/secrets/sensitive data risk | `mission_blocking` | Before capture beyond minimal redacted evidence |
| High/critical candidate promotion | `candidate_blocking` | Agent continues safe work |
| Confirmed reportable finding | `candidate_blocking` | External/reportable state is the risky point |
| Mission budget 80% | `async_notice` | Continue within remaining budget |
| Mission budget exhausted | `mission_blocking` → stop | No more target actions |
| Repeated denials / no-progress | `async_notice` or `action_blocking` | Async if FYI; blocking if requesting broader permissions |

## Operator responses (structured)

| Response | Meaning |
|----------|---------|
| `approve_once` | This specific action/transition |
| `approve_class` | This action class for this phase, target, and mission budget window |
| `deny` | Reject; agent adjusts |
| `stop` | End mission |
| `revise_scope` | Creates a new RoE amendment record; original roe_snapshot stays immutable |

## Checkpoint timeout

If the operator does not respond within a configured window, the default is `deny` or `stop`
depending on scope. No implicit approval from silence.

## Checkpoint payload

Each checkpoint includes: proposed action, phase, reason, evidence refs, RoE clause/status,
expected target impact, budget remaining, and allowed safe-continuation actions.

## Lab mode (slice 1)

Lab mode emits async-style events/logs for would-have-checkpointed moments, but no blocking
gates. AgentCheckpoint model is deferred.
