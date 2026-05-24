---
tier: CAPABLE
depends_on:
  - 01-target-intel
  - 02-plateau-baseline
  - 03-prompt-intel
files:
  creates: []
  modifies:
    - backend/apps/agent/controller.py
    - backend/apps/agent/tests/test_controller.py
  deletes: []
exports: []
imports:
  - backend/apps/agent/target_intel.py
allow_extra_files: false
---

### Task 4: Wire target intel through MissionController

**Files:**
- Modify: `backend/apps/agent/controller.py`
- Modify: `backend/apps/agent/tests/test_controller.py`

- [ ] **Step 1: Write failing tests**

Add to `test_controller.py`:

```python
@pytest.mark.django_db(transaction=True)
class TestWarmStart:
    @pytest.mark.asyncio
    async def test_prior_intel_in_system_prompt(self, db_objects):
        from apps.agent.target_intel import TargetIntel
        from django.utils import timezone

        intel = TargetIntel(
            source_session_id="prev-123",
            source_completed_at=timezone.now(),
            is_stale=False,
            known_routes={"/login", "/admin"},
        )
        c = _ctrl(
            db_objects, [_action_json("stop")],
            budget={"max_turns": 5}, target_intel=intel,
        )
        prompt = c.system_prompt
        assert "Prior Target Intel" in prompt
        assert "/login" in prompt

    @pytest.mark.asyncio
    async def test_no_intel_means_no_section(self, db_objects):
        c = _ctrl(db_objects, [_action_json("stop")], budget={"max_turns": 5})
        prompt = c.system_prompt
        assert "Prior Target Intel" not in prompt

    @pytest.mark.asyncio
    async def test_advance_phase_preserves_known_routes(self, db_objects):
        from apps.agent.target_intel import TargetIntel
        from django.utils import timezone

        intel = TargetIntel(
            source_session_id="prev-999",
            source_completed_at=timezone.now(),
            is_stale=False,
            known_routes={"/login"},
        )
        c = _ctrl(
            db_objects, [_action_json("stop")],
            budget={"max_turns": 5}, target_intel=intel,
        )
        c.plateau.record_turn(
            new_routes=1, new_elements=0, route_paths=["/probe"],
        )
        c.advance_phase("probe", "test advance")
        assert c.plateau._known_routes == {"/login", "/probe"}
```

If the local `_ctrl` helper does not accept `target_intel`, extend that helper to pass arbitrary keyword arguments through to `MissionController`. These tests must verify constructor wiring, not post-construction mutation.

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_controller.py::TestWarmStart -v`
Expected: FAIL — controller doesn't accept or use target_intel

- [ ] **Step 3: Implement target_intel in controller**

Modify `MissionController.__init__` to accept `target_intel`:

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
    target_intel=None,
) -> None:
    ...
    self.target_intel = target_intel
    self._known_routes = set(target_intel.known_routes) if target_intel else set()
    self.plateau = PlateauDetector(known_routes=self._known_routes)
    ...
```

When editing existing code, preserve any existing `PlateauDetector` threshold arguments. Add `known_routes=self._known_routes` to the existing construction rather than replacing configured thresholds.

Also update `advance_phase` so the plateau reset preserves `known_routes`:

```python
def advance_phase(self, to_phase: str, reason: str) -> None:
    """Transition to a new phase and reset phase budget."""
    self.session.current_phase = to_phase
    self.session.save(update_fields=["current_phase"])
    new_budget = self._phase_budgets.get(to_phase, {})
    self.budget.switch_phase(new_budget)
    self._known_routes.update(getattr(self.plateau, "_known_routes", set()))
    self.plateau = PlateauDetector(known_routes=self._known_routes)
```

As above, preserve any existing plateau threshold arguments when resetting for a new phase.

Modify `system_prompt` property:

```python
@property
def system_prompt(self) -> str:
    from .target_intel import format_intel_prompt
    phase = self.session.current_phase
    intel_section = format_intel_prompt(self.target_intel)
    return build_system_prompt(
        objective=self.objective,
        phase=phase,
        allowed_actions=allowed_actions_for_phase(phase),
        budget_remaining=self.budget.remaining("turns"),
        prior_intel_section=intel_section,
    )
```

- [ ] **Step 4: Run ALL controller tests**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_controller.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/controller.py backend/apps/agent/tests/test_controller.py
git commit -m "feat(agent): wire target_intel through MissionController"
```
