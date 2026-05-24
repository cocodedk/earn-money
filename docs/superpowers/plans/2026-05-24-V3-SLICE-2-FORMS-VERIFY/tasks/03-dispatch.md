---
tier: CAPABLE
depends_on:
  - 01-action-dataclasses
  - 02-driver-fill
files:
  creates: []
  modifies:
    - backend/apps/agent/controller_dispatch.py
    - backend/apps/agent/tests/test_controller.py
  deletes: []
exports: []
imports:
  - FillFormAction
  - SubmitFormAction
  - PlaywrightDriver.fill
allow_extra_files: false
---

### Task 3: Dispatch fill_form and submit_form actions

**Files:**
- Modify: `backend/apps/agent/controller_dispatch.py`
- Modify: `backend/apps/agent/tests/test_controller.py`

- [ ] **Step 1: Write failing tests for fill_form dispatch**

Add to `test_controller.py`:

```python
@pytest.mark.django_db(transaction=True)
class TestFillFormExecution:
    @pytest.mark.asyncio
    async def test_fill_form_calls_driver_fill(self, db_objects):
        fill_json = _action_json(
            action="fill_form", element_id="input_0", value="admin",
        )
        ctrl = _ctrl(
            db_objects,
            responses=[fill_json],
            budget={
                "max_turns": 5,
                "max_browser_actions": 5,
                "max_form_fills": 5,
            },
        )
        ctrl.session.current_phase = "enumerate"
        ctrl.session.save(update_fields=["current_phase"])
        ctrl.driver.fill = AsyncMock()

        from apps.agent.controller_turn import run_turn
        await run_turn(ctrl)

        ctrl.driver.fill.assert_awaited_once_with("input_0", "admin")
        from apps.agent.models import AgentObservation
        assert AgentObservation.objects.filter(
            action__turn__session=ctrl.session,
            observation_type="page",
        ).exists()


@pytest.mark.django_db(transaction=True)
class TestSubmitFormExecution:
    @pytest.mark.asyncio
    async def test_submit_form_calls_driver_click(self, db_objects):
        submit_json = _action_json(
            action="submit_form", element_id="btn_0",
        )
        ctrl = _ctrl(
            db_objects,
            responses=[submit_json],
            budget={
                "max_turns": 5,
                "max_browser_actions": 5,
                "max_form_submits": 5,
            },
        )
        ctrl.session.current_phase = "probe"
        ctrl.session.save(update_fields=["current_phase"])
        ctrl.driver.click = AsyncMock()

        from apps.agent.controller_turn import run_turn
        await run_turn(ctrl)

        ctrl.driver.click.assert_awaited_once_with("btn_0")
        from apps.agent.models import AgentObservation
        assert AgentObservation.objects.filter(
            action__turn__session=ctrl.session,
            observation_type="page",
        ).exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_controller.py::TestFillFormExecution apps/agent/tests/test_controller.py::TestSubmitFormExecution -v`
Expected: FAIL — no dispatch branch for fill_form/submit_form

- [ ] **Step 3: Implement dispatch branches**

In `controller_dispatch.py`, add imports at the top:

```python
from .actions.schemas import (
    ClickAction, FillFormAction, HttpRequestAction, NavigateAction,
    RequestPhaseTransitionAction, StopAction, StoreNoteAction, SubmitFormAction,
)
```

Add dispatch branches in `dispatch()` after the `ClickAction` branch:

Implementation invariant: each branch must make exactly one Playwright call and emit exactly one page observation. If the existing `_execute_browser_action` helper already performs the driver call for browser actions, extend that helper for `FillFormAction`/`SubmitFormAction` instead of calling the driver before it.

```python
if isinstance(parsed, FillFormAction):
    ctrl.budget.consume("form_fills")
    await ctrl.driver.fill(parsed.element_id, parsed.value)
    obs_dict = await _execute_browser_action(ctrl, turn, action_rec, envelope)
    _emit_and_finish_browser(ctrl, turn, envelope, obs_dict)
    return False

if isinstance(parsed, SubmitFormAction):
    ctrl.budget.consume("form_submits")
    await ctrl.driver.click(parsed.element_id)
    obs_dict = await _execute_browser_action(ctrl, turn, action_rec, envelope)
    _emit_and_finish_browser(ctrl, turn, envelope, obs_dict)
    return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_controller.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/controller_dispatch.py backend/apps/agent/tests/test_controller.py
git commit -m "feat(agent): dispatch fill_form and submit_form actions"
```
