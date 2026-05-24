---
slug: budgets
status: done         # draft | in-progress | done
---

# Budget Model

Dual-layer: mission budget is the hard safety envelope; per-phase budgets control behavior and
trigger transitions. Traffic budgets are the real safety boundary — tokens are cost/context
control.

## Mission budget (hard caps)

| Dimension | Default |
|-----------|---------|
| `max_turns` | 60 |
| `max_runtime_seconds` | 600 |
| `max_llm_calls` | 60 |
| `max_input_tokens` | 300,000 |
| `max_output_tokens` | 60,000 |
| `max_browser_actions` | 120 |
| `max_http_requests` | 200 |
| `max_post_requests` | 20 |
| `max_tool_runs` | 10 |
| `max_stub_runs` | 20 |
| `max_asset_inspections` | 20 |

## Per-phase budgets

| Dimension | Recon | Enumerate | Probe | Verify | Report |
|-----------|-------|-----------|-------|--------|--------|
| `max_turns` | 10 | 20 | 20 | 6 | 2 |
| `max_runtime_seconds` | 90 | 180 | 200 | 90 | 30 |
| `max_http_requests` | 30 | 80 | 50 | 20 | 0 |
| `max_post_requests` | 0 | 0 | 10 | 5 | 0 |
| `max_asset_inspections` | 5 | 8 | 5 | 0 | 0 |

Per-phase sums are intentionally below mission caps to leave headroom. The mission budget is
the hard ceiling; per-phase budgets are soft guides. If a phase exhausts its allocation, the
mission cap still applies independently.

For real programs, POST/form-submit budgets default to zero unless the RoE profile enables
them.

No silent carry-over between phases on real programs. Lab mode may relax this for read-only
recon/enumeration.

## Plateau thresholds

Separate from hard budgets — trigger early phase advancement:

```yaml
plateau:
  max_turns_without_new_route: 3
  max_turns_without_new_interactive_element: 3
  max_repeated_denials: 3
  max_invalid_actions: 2
```

## Turn accounting

Denied turns (AgentTurn with status `action_denied`, which includes schema-validation
failures) count against phase and mission turn budgets. They consume a turn slot but do not count as progress.
This prevents the LLM from exploiting invalid actions to extend a phase indefinitely, and
ensures plateau detection (`max_invalid_actions`, `max_repeated_denials`) can trigger early
advancement.

## Enforcement behavior

- Phase budget exhausted + useful candidates → advance to next phase
- Phase budget exhausted + no candidates → report gap / stop
- Mission budget exhausted → stop regardless of phase
- Repeated denials or no progress → controller advances or stops
- Verify budget exhausted → report as confirmed/refuted/unverified based on verifier state

## Tracked progress counters

Beyond budgets, these drive phase-transition decisions:

- New routes discovered
- New forms discovered
- New API endpoints discovered
- New parameters discovered
- New auth/session states discovered
- New candidates created
- Existing candidates got stronger evidence
- Existing candidates verified/refuted
