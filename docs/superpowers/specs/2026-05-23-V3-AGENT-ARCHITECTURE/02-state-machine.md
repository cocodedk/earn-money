---
slug: state-machine
status: done         # draft | in-progress | done
---

# State Machine & Phases

The controller owns a forward-progressing state machine. The LLM cannot mutate phase directly —
it submits `request_phase_transition` with reason and evidence refs; the controller approves
only if exit criteria are met.

## Phase flow

Normal path: recon → enumerate → probe → verify → report/stop.

Any phase may transition to report/stop on budget exhaustion, safety stop, no progress,
operator stop, or completed objective.

Backwards transitions (e.g. verify → enumerate) are allowed in narrow controller-decided cases
when replay reveals missing context. Guards: maximum one backward transition per mission,
backward transitions do not reset phase budgets (the target phase keeps its already-consumed
counts), and each backward transition emits an `agent.phase_changed` event with
`direction: backward` and `reason`. Normal path is forward-only.

## Phase definitions

**Recon**: passive discovery — page identity, baseline routes/assets, stub pre-pass. No clicks,
no form fills, read-only HTTP only (GET/HEAD).

**Enumerate**: active discovery — follow links, inspect forms/fields/APIs, map auth flows. Safe
navigation and clicks, no form submission.

**Probe**: hypothesis testing — submit forms, mutating HTTP, targeted stubs, RoE-gated tools.
State-changing actions become available, but impact proof / exploit chaining is a separate
RoE-gated submode.

**Verify**: replay-only — reproduce a candidate finding along a narrow known path, attach
evidence. No new exploration, no fresh stub/tool sweeps.

**Report/Stop**: summarize results, emit final events. No target actions.

## Phase transitions

Transitions are triggered by explicit progress counters — not vibes:

- New route discovered
- New form discovered
- New API endpoint discovered
- New parameter discovered
- New auth/session state discovered
- New candidate finding created
- Existing candidate got stronger evidence
- Existing candidate was verified/refuted

### Transition triggers

| Transition | LLM may request when | Controller forces when |
|---|---|---|
| recon → enumerate | Initial page/app identity known; baseline routes/assets collected | Passive recon budget done; no new signals after N turns |
| enumerate → probe | Concrete candidates: forms, params, auth flows, APIs, interesting routes | Discovery plateaued; max enumerate turns reached |
| probe → verify | A candidate finding has evidence worth replaying | Candidate threshold met; probe budget near exhaustion |
| verify → report | Candidate confirmed/refuted enough to summarize | Verification attempts exhausted; verifier produced terminal result |
| any → report/stop | No productive next step | Budget/RoE/scope failure, repeated denials, no progress, operator pause, safety stop |

### Transition request schema

```
request_phase_transition:
  from_phase: enum
  to_phase: enum
  reason: string
  evidence_refs: [ref]
  remaining_questions: [string]
```

Controller approves only if: target phase is a legal next phase, minimum exit criteria for
current phase are met, required evidence_refs exist, RoE/budget/operator checkpoint allows it.
