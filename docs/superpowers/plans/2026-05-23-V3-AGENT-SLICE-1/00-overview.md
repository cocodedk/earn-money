# V3 Agent Slice 1 — Juice Shop Scoreboard Mission

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the minimal V3 agent loop that can find Juice Shop's hidden scoreboard page
by reasoning over structured PageObservations and driving Playwright through a controller.

**Architecture:** Single Django app `backend/apps/agent/` with internal subpackages. The
controller mediates all execution: LLM proposes typed actions → controller validates against
phase/budget/scope → executor runs Playwright → observation builder normalizes results.
Three phases for this slice: recon → enumerate → report/stop.

**Tech Stack:** Django 5.x, Playwright (async), Anthropic SDK for slice 1, pytest,
pydantic v2 for action schemas.

**Spec:** `docs/superpowers/specs/2026-05-23-V3-AGENT-ARCHITECTURE/`

---

## Task files

Execute in the dependency order below. File number prefixes are stable task IDs; the table
order is authoritative when a later-numbered task is a prerequisite.

| File | Topic |
|------|-------|
| [tasks/01-session-turn-models.md](tasks/01-session-turn-models.md) | AgentSession + AgentTurn models |
| [tasks/02-action-obs-note-models.md](tasks/02-action-obs-note-models.md) | AgentAction + AgentObservation + AgentNote |
| [tasks/03-migrations.md](tasks/03-migrations.md) | App registration + migrations |
| [tasks/04-action-schemas.md](tasks/04-action-schemas.md) | Typed action schemas + validation |
| [tasks/05-phase-matrix.md](tasks/05-phase-matrix.md) | Phase-action matrix enforcement |
| [tasks/06-budget-tracker.md](tasks/06-budget-tracker.md) | Dual-layer budget accounting |
| [tasks/07-plateau-detection.md](tasks/07-plateau-detection.md) | Plateau detection |
| [tasks/08-page-observation.md](tasks/08-page-observation.md) | PageObservation dataclass |
| [tasks/09-asset-observation.md](tasks/09-asset-observation.md) | AssetObservation dataclass |
| [tasks/10-observation-builder.md](tasks/10-observation-builder.md) | Playwright → PageObservation |
| [tasks/11-playwright-driver.md](tasks/11-playwright-driver.md) | Thin Playwright adapter |
| [tasks/12-llm-provider.md](tasks/12-llm-provider.md) | LLM provider interface |
| [tasks/13-system-prompt.md](tasks/13-system-prompt.md) | System prompt + observation formatting |
| [tasks/14-persistence.md](tasks/14-persistence.md) | Persistence layer |
| [tasks/15-event-logging.md](tasks/15-event-logging.md) | Event types + emission helpers |
| [tasks/17-phase-transitions.md](tasks/17-phase-transitions.md) | Phase transition validation |
| [tasks/16-controller-loop.md](tasks/16-controller-loop.md) | Mission controller loop |
| [tasks/18-mission-profiles.md](tasks/18-mission-profiles.md) | Juice Shop mission profile |
| [tasks/19-integration-test.md](tasks/19-integration-test.md) | Full integration test |
| [tasks/20-live-run.md](tasks/20-live-run.md) | Live Juice Shop verification |

## Execution guardrails

- Do not start a task until all preceding dependency-order tasks pass their stated tests.
- Treat commit steps as checkpoints. If git is unavailable, complete the task only after the
  same file set is cleanly implemented and tested.
- Roll back a failed task by undoing only the files named in that task's **Files** section.
  For Task 3 migration failures in a disposable dev database, migrate the `agent` app back to
  the previous migration before regenerating.
- Do not proceed to Task 20 until the unit tests, controller tests, and Task 19 integration
  test pass.

## Supporting files

- [file-structure.md](file-structure.md) — target file layout and modifications
- [out-of-scope.md](out-of-scope.md) — deferred items

## Modify (existing files)

- `backend/config/settings.py` — add `"apps.agent"` to INSTALLED_APPS (Task 3)
- `backend/apps/events/types.py` — add agent event types (Task 15)
