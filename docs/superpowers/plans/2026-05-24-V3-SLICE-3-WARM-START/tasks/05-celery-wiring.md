---
tier: CAPABLE
depends_on:
  - 01-target-intel
  - 04-controller-wiring
files:
  creates: []
  modifies:
    - backend/apps/agent/tasks.py
    - backend/apps/agent/tests/test_tasks.py
  deletes: []
exports: []
imports:
  - backend/apps/agent/target_intel.py
allow_extra_files: false
---

### Task 5: Wire target intel in Celery task

**Files:**
- Modify: `backend/apps/agent/tasks.py`
- Modify: `backend/apps/agent/tests/test_tasks.py`

- [ ] **Step 1: Add test asserting target_intel is forwarded**

Add to `test_tasks.py` before implementation. This requires `build_target_intel` to be imported at module scope in `apps.agent.tasks` so the patch target exists.

```python
@patch("apps.agent.tasks._build_driver")
@patch("apps.agent.tasks._build_provider")
@patch("apps.agent.tasks.build_target_intel", return_value=None)
def test_target_intel_passed_to_controller(
    mock_intel, mock_provider, mock_driver,
):
    session, target_run, scan_run = _create_session_for_task()
    mock_provider.return_value = MagicMock()
    driver = MagicMock()
    driver.stop = AsyncMock()
    mock_driver.return_value = driver

    with patch("apps.agent.tasks.MissionController") as MockCtrl:
        ctrl_instance = MockCtrl.return_value

        async def _set_completed():
            from asgiref.sync import sync_to_async
            await sync_to_async(
                AgentSession.objects.filter(pk=session.pk).update
            )(status=SessionStatus.COMPLETED)

        ctrl_instance.run = AsyncMock(side_effect=_set_completed)
        run_agent_session(str(session.id))

    mock_intel.assert_called_once_with(
        session.target,
        stale_after_days=7,
        exclude_session_id=session.pk,
    )
    call_kwargs = MockCtrl.call_args.kwargs
    assert "target_intel" in call_kwargs
    assert call_kwargs["target_intel"] is None  # mock returns None
```

- [ ] **Step 2: Implement prior session query in _execute_agent_session**

In `tasks.py`, add a module-level import:

```python
from .target_intel import build_target_intel
```

After `profile = get_profile(...)` (line 72), add:

```python
target_intel = build_target_intel(
    session.target,
    stale_after_days=7,
    exclude_session_id=session.pk,
)
```

Pass to MissionController:

```python
ctrl = MissionController(
    session=session,
    provider=provider,
    driver=driver,
    objective=profile.objective,
    mission_budget=profile.mission_budget,
    phase_budgets=profile.phase_budgets,
    model_name=session.model_policy.get("model", "mock"),
    mission_phases=profile.phases,
    target_intel=target_intel,
)
```

- [ ] **Step 3: Run full test suite**

Run: `docker compose exec backend python -m pytest apps/agent/tests/ -v --tb=short`
Expected: ALL PASS (existing tests use mock sessions that have no prior completed sessions, so target_intel is None)

- [ ] **Step 4: Commit**

```bash
git add backend/apps/agent/tasks.py backend/apps/agent/tests/test_tasks.py
git commit -m "feat(agent): query prior session and pass target_intel to controller"
```
