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

**Tech Stack:** Django 5.x, Playwright (async), OpenAI/Anthropic SDK, pytest, pydantic for
action schemas.

**Spec:** `docs/superpowers/specs/2026-05-23-V3-AGENT-ARCHITECTURE/`

---

## Task files

Execute in order. Each file is one logical unit.

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
| [tasks/16-controller-loop.md](tasks/16-controller-loop.md) | Mission controller loop |
| [tasks/17-phase-transitions.md](tasks/17-phase-transitions.md) | Phase transition validation |
| [tasks/18-mission-profiles.md](tasks/18-mission-profiles.md) | Juice Shop mission profile |
| [tasks/19-integration-test.md](tasks/19-integration-test.md) | Full integration test |
| [tasks/20-live-run.md](tasks/20-live-run.md) | Live Juice Shop verification |

## Supporting files

- [file-structure.md](file-structure.md) — target file layout and modifications
- [out-of-scope.md](out-of-scope.md) — deferred items

## Modify (existing files)

- `backend/config/settings.py` — add `"apps.agent"` to INSTALLED_APPS (Task 3)
- `backend/apps/events/types.py` — add agent event types (Task 15)
