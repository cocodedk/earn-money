# V3 Agent Architecture — Design Spec

**Date**: 2026-05-23
**Status**: Draft
**Owner**: Babak Bandpey (cocode.dk)

## Overview

V3 adds an LLM-driven agent layer above the existing v2 scanner spine. The v2 stubs remain
available as deterministic pre-pass checks and allowlisted tools.

The LLM reasons and proposes typed actions; a controller validates against phase, budget, RoE,
scope, and checkpoint policy; tool adapters (Playwright, stubs, OSS tools) execute; normalized
observations return to the LLM.

**Core invariant**: LLM proposes, policy decides, tool layer executes. The LLM never touches
Playwright, HTTP, or tools directly — the controller mediates everything.

## Spec files

| File | Topic |
|------|-------|
| [01-architecture.md](01-architecture.md) | System architecture and component diagram |
| [02-state-machine.md](02-state-machine.md) | Phase definitions, transitions, progress counters |
| [03-actions.md](03-actions.md) | 14 typed actions, constraints, phase-action matrix |
| [04-page-observation.md](04-page-observation.md) | PageObservation schema and inclusion policy |
| [05-data-model.md](05-data-model.md) | Django models and persistence strategy |
| [06-budgets.md](06-budgets.md) | Mission and per-phase budget model |
| [07-checkpoints.md](07-checkpoints.md) | Operator checkpoint model and blocking scopes |
| [08-llm-policy.md](08-llm-policy.md) | Model selection, routing, escalation |
| [09-repo-structure.md](09-repo-structure.md) | File layout for backend/apps/agent/ |
| [10-slice-1.md](10-slice-1.md) | Juice Shop scoreboard mission — scope and acceptance |
| [11-slice-b-plus-probe.md](11-slice-b-plus-probe.md) | Narrow probe phase + minimal evidence contract |
