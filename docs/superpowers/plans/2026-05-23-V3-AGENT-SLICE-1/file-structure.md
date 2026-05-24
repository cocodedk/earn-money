# File Structure

## New files (backend/apps/agent/)

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

## Modified files

- `backend/config/settings.py` — add `"apps.agent"` to INSTALLED_APPS (Task 3)
- `backend/apps/events/types.py` — add agent event types (Task 15)
