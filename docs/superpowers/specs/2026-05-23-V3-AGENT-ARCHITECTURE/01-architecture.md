# Architecture Overview

V3 adds an LLM-driven agent layer above the existing v2 scanner spine. The v2 stubs remain
available as deterministic pre-pass checks and allowlisted tools.

## Component diagram

```
┌─────────────────────────────────────────────────────┐
│                   Mission Loop                       │
│                                                      │
│  ┌──────┐  typed    ┌─────────────┐  approved  ┌──────────┐
│  │ LLM  │ ───────→  │  Controller │ ─────────→ │ Executor │
│  │      │  action    │             │  action     │          │
│  │      │           │ • phase      │            │ • browser│
│  │      │           │ • budget     │            │ • stubs  │
│  │      │           │ • RoE/scope  │            │ • tools  │
│  │      │  ←─────── │ • checkpoint │  ←──────── │          │
│  │      │  obs       │             │  raw        │          │
│  └──────┘           └─────────────┘  result     └──────────┘
│                          │                                  │
│                     ┌────┴─────┐                            │
│                     │ Persist  │                            │
│                     │ + Event  │                            │
│                     └──────────┘                            │
└─────────────────────────────────────────────────────┘
          │
     ScanRun → ScanTargetRun → AgentSession
```

## Component responsibilities

**LLM**: proposes one typed action per turn with freeform reasoning fields (`goal`, `reason`,
`hypothesis`). Never executes directly.

**Controller**: owns the state machine, validates actions against phase/budget/RoE/scope/
checkpoint policy, decides phase transitions, manages operator gates. The single authority over
what runs.

**Executor**: thin adapters for Playwright, v2 stubs, and OSS tools. Returns raw results to the
controller. No policy decisions.

**Observation builder**: transforms raw executor results into normalized `PageObservation` or
tool summaries. Redacts sensitive values, assigns controller-owned IDs, marks target content as
untrusted.

**Persistence**: writes AgentTurn, AgentAction, AgentObservation, AgentNote rows. Emits Event
rows for the audit/streaming trail.

## V2 stub integration

V2 stubs serve two roles in V3:

- **Pre-pass**: cheap deterministic stubs run before the agent loop to seed baseline facts
  (routes, forms, auth behavior, headers, known candidates).
- **LLM-invokable tools**: selected stubs exposed as `run_stub` actions during agent phases.
  The controller offers only stubs allowed for the current phase/RoE — the LLM cannot call
  arbitrary stubs by slug.

The LLM orchestrates hypotheses; it does not replace stub logic.
