# V3 Slice 3 — Warm-Start Target Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a mission runs against a previously-probed target, seed the LLM with compact prior intel and the plateau detector with known routes — accelerating exploration without fabricating evidence.

**Architecture:** New `target_intel.py` module builds a `TargetIntel` dataclass from the most recent completed session. The system prompt gets an optional `## Prior Target Intel` section. PlateauDetector accepts an optional `known_routes` baseline. The Celery task queries prior sessions and wires intel through to the controller.

**Tech Stack:** Django ORM, Python dataclasses, pytest

---

## Execution guardrails

- Do tasks in order. Task 2 changes the `PlateauDetector.record_turn()` contract; Task 6 depends on that new optional `route_paths` parameter.
- Do not let the currently running session become its own warm-start source. `build_target_intel()` must support `exclude_session_id`, and the Celery task must pass the current session id.
- Treat all prior intel as untrusted, bounded hints. Sanitize text before prompt insertion, cap every list, and require re-observation before any candidate is treated as current evidence.
- Rollback is per task: each task ends with a commit. If a task fails after implementation, revert only that task's commit or discard only the files listed in that task before retrying.
- Stop at the first failing verification step. Do not continue to downstream wiring until the current task's focused tests pass.

## File structure

See [file-structure.md](file-structure.md) for the full file map.

## Tasks

| # | Task | File |
|---|------|------|
| 1 | TargetIntel dataclasses + build_target_intel() | [tasks/01-target-intel.md](tasks/01-target-intel.md) |
| 2 | PlateauDetector baseline routes | [tasks/02-plateau-baseline.md](tasks/02-plateau-baseline.md) |
| 3 | Prior intel section in system prompt | [tasks/03-prompt-intel.md](tasks/03-prompt-intel.md) |
| 4 | Wire target intel through MissionController | [tasks/04-controller-wiring.md](tasks/04-controller-wiring.md) |
| 5 | Wire target intel in Celery task | [tasks/05-celery-wiring.md](tasks/05-celery-wiring.md) |
| 6 | Pass route_paths through dispatch to plateau | [tasks/06-dispatch-routes.md](tasks/06-dispatch-routes.md) |
