# Task 5: Controller — Profile-Driven Phase List

**Files:**
- Modify: `backend/apps/agent/controller.py`
- Modify: `backend/apps/agent/tests/test_controller.py`
- Modify: `backend/apps/agent/tests/test_controller_edge.py`

---

- [ ] **Step 1: Write test for profile-driven auto-advance**

Add to `backend/apps/agent/tests/test_controller_edge.py`:

```python
@pytest.mark.django_db
class TestProbePhaseAutoAdvance:
    @pytest.mark.asyncio
    async def test_plateau_advances_enumerate_to_probe(self, db_objects):
        responses = [_action_json(action="observe_page")] * 8
        ctrl = _ctrl(
            db_objects, responses=responses,
            budget={"max_turns": 20},
        )
        ctrl.session.current_phase = "enumerate"
        ctrl.session.save(update_fields=["current_phase"])
        # Override the controller's phase list to include probe
        ctrl._mission_phases = ["recon", "enumerate", "probe", "report"]

        await ctrl.run()

        ctrl.session.refresh_from_db()
        # Should have advanced past enumerate (plateau)
        assert ctrl.session.current_phase in ("probe", "report", "stopped")
```

- [ ] **Step 2: Run test — expect FAIL**

The controller uses `SLICE_1_PHASES` which doesn't include probe.

- [ ] **Step 3: Make controller use profile-driven phase list**

In `backend/apps/agent/controller.py`:

1. Add `mission_phases` parameter to `__init__`:

```python
    def __init__(
        self,
        session,
        provider,
        driver,
        objective: str,
        mission_budget: dict,
        phase_budgets: dict | None = None,
        model_name: str = "mock",
        mission_phases: list[str] | None = None,
    ) -> None:
        # ... existing ...
        self._mission_phases = mission_phases or SLICE_1_PHASES
```

2. Update `_next_slice_phase` to use `self._mission_phases`:

```python
    def _next_slice_phase(self, current: str) -> str | None:
        try:
            idx = self._mission_phases.index(current)
        except ValueError:
            return None
        nxt = idx + 1
        if nxt >= len(self._mission_phases):
            return None
        return self._mission_phases[nxt]
```

Remove `@staticmethod` — it now reads `self._mission_phases`.

3. Update `tasks.py` to pass `mission_phases=profile.phases` when building the controller.

- [ ] **Step 4: Run test — expect PASS**

- [ ] **Step 5: Run all controller tests**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_controller.py apps/agent/tests/test_controller_edge.py -v`

- [ ] **Step 6: Commit**

```bash
git add backend/apps/agent/controller.py backend/apps/agent/tasks.py backend/apps/agent/tests/test_controller.py backend/apps/agent/tests/test_controller_edge.py
git commit -m "feat(agent): profile-driven phase list in controller"
```
