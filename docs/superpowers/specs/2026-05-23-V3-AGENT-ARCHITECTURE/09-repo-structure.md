# Repo Structure

Single Django app at `backend/apps/agent/` with internal subpackages. Locality over premature
abstraction — browser/llm/observations promoted to shared packages only if a second consumer
appears.

## Full layout (target)

```
backend/apps/agent/
  apps.py
  models.py                # AgentSession, AgentTurn, AgentAction, AgentObservation, AgentNote
  migrations/
  tasks.py                 # Celery entrypoint for agent missions
  event_log.py             # Event emission helpers
  persistence.py           # write Turn/Action/Observation/Note rows

  controller.py            # main mission loop
  actions.py               # 14 typed action schemas + validation
  phases.py                # phase enum, phase/action matrix, transition logic
  budgets.py               # mission + phase budget accounting + plateau detection
  mission_profiles.py      # juice_shop_scoreboard, future profiles

  observations/
    __init__.py
    page.py                # PageObservation schema
    builder.py             # Playwright state → PageObservation
    assets.py              # JS/CSS asset inspection + excerpt extraction
    redaction.py           # strip sensitive values, mark untrusted content

  browser/
    __init__.py
    playwright_driver.py   # thin Playwright adapter

  llm/
    __init__.py
    router.py              # fixed per-mission model policy + escalation
    providers.py           # provider interface/adapters
    prompts.py             # system prompt, observation formatting, delta compression

  tests/
```

## Slice 1 minimal set

```
backend/apps/agent/
  apps.py
  models.py
  migrations/
  controller.py
  actions.py
  phases.py
  budgets.py
  persistence.py
  event_log.py
  mission_profiles.py

  observations/
    page.py
    builder.py
    assets.py

  browser/
    playwright_driver.py

  llm/
    providers.py
    prompts.py

  tests/
```

Deferred for post-slice-1: `observations/redaction.py` (basic redaction inline in builder),
`llm/router.py` (single model, no routing), `tasks.py` (direct invocation, no Celery).
