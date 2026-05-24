---
tier: APEX
depends_on:
  - 01-action-dataclasses
  - 02-driver-fill
  - 03-dispatch
  - 04-verify-gate
  - 05-form-extraction
  - 06-mission-profile
files:
  creates: []
  modifies:
    - backend/apps/agent/tests/test_controller.py
  deletes: []
exports: []
imports:
  - FillFormAction
  - SubmitFormAction
  - PlaywrightDriver.fill
  - _has_candidate
  - juice_shop_login profile
allow_extra_files: false
---

### Task 7: End-to-end controller test — fill -> submit -> verify -> stop

**Files:**
- Modify: `backend/apps/agent/tests/test_controller.py`

- [ ] **Step 1: Write end-to-end test**

Add to `test_controller.py`:

```python
@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_full_form_flow_with_verify(db_objects):
    """Agent fills a form, submits, transitions to verify, replays, stops."""
    c = _ctrl(db_objects, [
        _action_json("navigate", path="/login"),
        _action_json("fill_form", element_id="input_0", value="admin"),
        _action_json("fill_form", element_id="input_1", value="password"),
        _action_json("submit_form", element_id="btn_0"),
        _action_json(
            "submit_candidate", category="weak_creds",
            description="default login", evidence_refs=[],
        ),
        _action_json(
            "request_phase_transition", from_phase="probe",
            to_phase="verify", evidence_refs=[],
        ),
        _action_json("navigate", path="/login"),
        _action_json("fill_form", element_id="input_0", value="admin"),
        _action_json("submit_form", element_id="btn_0"),
        _action_json("stop"),
    ], budget={
        "max_turns": 20,
        "max_llm_calls": 20,
        "max_browser_actions": 20,
        "max_form_fills": 10,
        "max_form_submits": 5,
    })
    c.session.current_phase = "probe"
    c.session.save(update_fields=["current_phase"])
    c._mission_phases = ["recon", "enumerate", "probe", "verify", "report"]
    c.driver.fill = AsyncMock()
    c.driver.click = AsyncMock()

    await c.run()
    c.session.refresh_from_db()
    assert c.session.status == "completed"
    assert c.session.current_phase == "verify"
    from apps.agent.models import AgentAction
    fills = AgentAction.objects.filter(
        turn__session=c.session, action_type="fill_form",
    )
    assert fills.count() == 3
    submits = AgentAction.objects.filter(
        turn__session=c.session, action_type="submit_form",
    )
    assert submits.count() == 2
```

- [ ] **Step 2: Run test to verify it passes**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_controller.py::test_full_form_flow_with_verify -v`
Expected: PASS (all pieces wired up from previous tasks)

- [ ] **Step 3: Run full test suite**

Run: `docker compose exec backend python -m pytest apps/agent/tests/ -v --tb=short`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add backend/apps/agent/tests/test_controller.py
git commit -m "test(agent): add end-to-end form flow with verify phase"
```
