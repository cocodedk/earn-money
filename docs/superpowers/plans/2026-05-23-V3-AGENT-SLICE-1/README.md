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

## Plan files

Execute tasks in order. Each file is one logical unit.

| File | Tasks | Topic |
|------|-------|-------|
| [phase-1-models.md](phase-1-models.md) | 1-3 | Django models + migrations + event types |
| [phase-2-actions.md](phase-2-actions.md) | 4-5 | Action schemas + phase matrix |
| [phase-3-budgets.md](phase-3-budgets.md) | 6-7 | Budget accounting + plateau detection |
| [phase-4-observations.md](phase-4-observations.md) | 8-10 | PageObservation + AssetObservation + builder |
| [phase-5-browser.md](phase-5-browser.md) | 11 | Playwright driver adapter |
| [phase-6-llm.md](phase-6-llm.md) | 12-13 | LLM provider + prompt formatting |
| [phase-7-persistence.md](phase-7-persistence.md) | 14-15 | Persistence layer + event logging |
| [phase-8-controller.md](phase-8-controller.md) | 16-18 | Controller loop + mission profiles |
| [phase-9-integration.md](phase-9-integration.md) | 19-20 | Integration test + live Juice Shop run |

## File map

```
backend/apps/agent/
  __init__.py
  apps.py
  models.py                    # Task 1-2
  migrations/                  # Task 3

  actions/
    __init__.py
    schemas.py                 # Task 4
    matrix.py                  # Task 5

  budgets.py                   # Task 6
  plateau.py                   # Task 7

  observations/
    __init__.py
    page.py                    # Task 8
    assets.py                  # Task 9
    builder.py                 # Task 10

  browser/
    __init__.py
    driver.py                  # Task 11

  llm/
    __init__.py
    providers.py               # Task 12
    prompts.py                 # Task 13

  persistence.py               # Task 14
  event_log.py                 # Task 15

  controller.py                # Task 16
  phases.py                    # Task 17
  mission_profiles.py          # Task 18

  tests/
    __init__.py
    test_models.py             # Task 1-2
    test_actions.py            # Task 4-5
    test_budgets.py            # Task 6
    test_plateau.py            # Task 7
    test_page_observation.py   # Task 8
    test_asset_observation.py  # Task 9
    test_builder.py            # Task 10
    test_driver.py             # Task 11
    test_providers.py          # Task 12
    test_prompts.py            # Task 13
    test_persistence.py        # Task 14
    test_event_log.py          # Task 15
    test_controller.py         # Task 16
    test_phases.py             # Task 17
    test_mission_profiles.py   # Task 18
    test_integration.py        # Task 19
```

Modify:
- `backend/config/settings.py` — add `"apps.agent"` to INSTALLED_APPS (Task 3)
- `backend/apps/events/types.py` — add agent event types (Task 15)
