# Task 3: Controller Turn — Route click + http_request

**Files:**
- Modify: `backend/apps/agent/controller_turn.py`
- Modify: `backend/apps/agent/tests/test_controller.py`

---

- [ ] **Step 1: Write test for click execution in controller**

Add to `backend/apps/agent/tests/test_controller.py`:

```python
@pytest.mark.django_db
class TestClickExecution:
    @pytest.mark.asyncio
    async def test_click_persists_page_observation(self, db_objects):
        click_json = _action_json(
            action="click", element_id="link_0",
        )
        ctrl = _ctrl(db_objects, responses=[click_json], budget={"max_turns": 5})
        ctrl.session.current_phase = "probe"
        ctrl.session.save(update_fields=["current_phase"])
        ctrl.driver.click = AsyncMock()

        from apps.agent.controller_turn import run_turn
        await run_turn(ctrl)

        ctrl.driver.click.assert_awaited_once_with("link_0")
        from apps.agent.models import AgentObservation
        assert AgentObservation.objects.filter(
            action__turn__session=ctrl.session,
            observation_type="page",
        ).exists()
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_controller.py::TestClickExecution -v`

- [ ] **Step 3: Add click branch to _execute in controller_turn.py**

In `_execute()`, add after the `StoreNoteAction` block:

```python
    from .actions.schemas import ClickAction
    if isinstance(parsed, ClickAction):
        await ctrl.driver.click(parsed.element_id)
        obs_dict = await _execute_browser_action(
            ctrl, turn, action_rec, envelope,
        )
        _emit_and_finish_browser(ctrl, turn, action_rec, envelope, obs_dict)
        return False
```

Extract the emit/finish logic from the existing browser-action path into a helper `_emit_and_finish_browser()` to avoid duplication.

- [ ] **Step 4: Run test — expect PASS**

- [ ] **Step 5: Write test for http_request execution**

```python
@pytest.mark.django_db
class TestHttpRequestExecution:
    @pytest.mark.asyncio
    async def test_http_request_persists_http_observation(self, db_objects):
        req_json = _action_json(
            action="http_request", method="GET", path="/api/test",
        )
        ctrl = _ctrl(db_objects, responses=[req_json], budget={"max_turns": 5})
        ctrl.session.current_phase = "probe"
        ctrl.session.save(update_fields=["current_phase"])
        ctrl.driver.http_request = AsyncMock(return_value={
            "url": "https://test.example.com/api/test",
            "method": "GET", "status": 200,
            "content_type": "application/json",
            "redirected": False, "final_url": "https://test.example.com/api/test",
            "body_excerpt": '{"ok": true}', "body_truncated": False,
            "trust": "untrusted_target_content",
        })

        from apps.agent.controller_turn import run_turn
        await run_turn(ctrl)

        ctrl.driver.http_request.assert_awaited_once_with("GET", "/api/test")
        from apps.agent.models import AgentObservation
        assert AgentObservation.objects.filter(
            action__turn__session=ctrl.session,
            observation_type="http",
        ).exists()
```

- [ ] **Step 6: Add http_request branch to _execute**

```python
    from .actions.schemas import HttpRequestAction
    if isinstance(parsed, HttpRequestAction):
        http_obs = await ctrl.driver.http_request(
            parsed.method, parsed.path,
        )
        record_observation(
            action=action_rec,
            observation_type=ObservationType.HTTP,
            data=http_obs,
        )
        _mark_executed(action_rec)
        ctrl.budget.consume("http_requests")
        _emit_and_finish(ctrl, turn, action_rec, envelope, http_obs)
        return False
```

- [ ] **Step 7: Run all controller tests**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_controller.py apps/agent/tests/test_controller_edge.py -v`

- [ ] **Step 8: Commit**

```bash
git add backend/apps/agent/controller_turn.py backend/apps/agent/tests/test_controller.py
git commit -m "feat(agent): route click + http_request in controller turn"
```
