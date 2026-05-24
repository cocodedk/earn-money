---
tier: CAPABLE
depends_on:
  - 03-dispatch
files:
  creates: []
  modifies:
    - backend/apps/agent/controller_dispatch.py
    - backend/apps/agent/tests/test_controller.py
  deletes: []
exports:
  - _has_candidate
imports: []
allow_extra_files: false
---

### Task 4: Verify phase entry gate

**Files:**
- Modify: `backend/apps/agent/controller_dispatch.py`
- Modify: `backend/apps/agent/tests/test_controller.py`

- [ ] **Step 1: Write failing tests for verify phase gate**

Add to `test_controller.py`:

```python
@pytest.mark.django_db(transaction=True)
class TestVerifyPhaseGate:
    @pytest.mark.asyncio
    async def test_verify_transition_denied_without_candidate(self, db_objects):
        """Transition to verify is denied if no submit_candidate exists."""
        c = _ctrl(db_objects, [
            _action_json(
                "request_phase_transition", from_phase="probe",
                to_phase="verify", evidence_refs=[],
            ),
            _action_json("stop"),
        ])
        c.session.current_phase = "probe"
        c.session.save(update_fields=["current_phase"])
        c._mission_phases = ["recon", "enumerate", "probe", "verify", "report"]
        await c.run()
        c.session.refresh_from_db()
        assert c.session.current_phase == "probe"

    @pytest.mark.asyncio
    async def test_verify_transition_allowed_with_candidate(self, db_objects):
        """Transition to verify is allowed when a submit_candidate action exists."""
        c = _ctrl(db_objects, [
            _action_json(
                "submit_candidate", category="xss",
                description="test", evidence_refs=[],
            ),
            _action_json(
                "request_phase_transition", from_phase="probe",
                to_phase="verify", evidence_refs=[],
            ),
            _action_json("stop"),
        ])
        c.session.current_phase = "probe"
        c.session.save(update_fields=["current_phase"])
        c._mission_phases = ["recon", "enumerate", "probe", "verify", "report"]
        await c.run()
        c.session.refresh_from_db()
        assert c.session.status == "completed"
        assert c.session.current_phase == "verify"
        # stop fires in verify phase — current_phase stays "verify"
        # (stop does not advance phase, it just ends the mission)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_controller.py::TestVerifyPhaseGate -v`
Expected: FAIL — verify transition proceeds without candidate check

- [ ] **Step 3: Implement verify gate in phase transition handler**

In `controller_dispatch.py`, modify `_handle_phase_transition`:

```python
def _handle_phase_transition(ctrl, parsed) -> None:
    from .phases import is_valid_transition

    if not is_valid_transition(parsed.from_phase, parsed.to_phase):
        return

    if parsed.to_phase == "verify" and not _has_candidate(ctrl.session):
        return

    from .event_log import build_budget_snapshot, emit_phase_changed
    snapshot = build_budget_snapshot(
        ctrl.session, ctrl.budget.consumed_snapshot(),
    )
    emit_phase_changed(
        ctrl.session, parsed.from_phase, parsed.to_phase, parsed.reason,
        budget_snapshot=snapshot,
    )
    ctrl.advance_phase(parsed.to_phase, parsed.reason)


def _has_candidate(session) -> bool:
    """Return True if the session has at least one submit_candidate action."""
    from .models import AgentAction
    return AgentAction.objects.filter(
        turn__session=session,
        action_type="submit_candidate",
    ).exists()
```

Do not count rejected or invalid action records as candidates. If `AgentAction` has a status, error, or validity field, add the existing local success filter to `_has_candidate()` and cover it with a regression test in `TestVerifyPhaseGate`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_controller.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/controller_dispatch.py backend/apps/agent/tests/test_controller.py
git commit -m "feat(agent): add verify phase entry gate — requires candidate"
```
