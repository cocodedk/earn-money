---
tier: APEX
depends_on: [06-event-enrichment-emitters]
files:
  creates: []
  modifies:
    - backend/apps/agent/controller_turn.py
    - backend/apps/agent/controller.py
    - backend/apps/agent/tests/test_controller.py
  deletes: []
  renames: []
  generated: []
exports: []
imports:
  - module: "apps.agent.event_log.build_budget_snapshot"
    file: backend/apps/agent/controller.py
  - module: "apps.agent.event_log.summarize_observation"
    file: backend/apps/agent/controller_turn.py
allow_extra_files: false
---

# Task 7: Controller Turn — Persist consumed_budget Every Turn

**Files:**
- Modify: `backend/apps/agent/controller_turn.py`
- Modify: `backend/apps/agent/controller.py`
- Modify: `backend/apps/agent/tests/test_controller.py`

---

- [ ] **Step 1: Write test that consumed_budget persists after completed turn**

Add to `backend/apps/agent/tests/test_controller.py` (or a new file
`test_budget_persist.py` if test_controller.py is near 200 lines):

```python
@pytest.mark.django_db
class TestConsumedBudgetPersistence:
    """consumed_budget must be written to DB after every turn path."""

    @pytest.mark.asyncio
    async def test_budget_persisted_after_executed_turn(self, db_objects):
        """Use the existing _mock_provider/_mock_driver/_action_json
        helpers from test_controller.py. Provider returns a stop action
        so the controller finishes after one turn."""
        session_obj = _ctrl(
            db_objects,
            responses=[_action_json(action="stop", reason="done")],
            budget={"max_turns": 10},
        )
        await session_obj.run()
        session_obj.session.refresh_from_db()
        assert session_obj.session.consumed_budget["mission"]["turns"] >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_controller.py::TestConsumedBudgetPersistence -v`
Expected: FAIL — `consumed_budget` is `{}` because it's only written at session finish, not per-turn

- [ ] **Step 3: Add budget persist to run_turn**

In `backend/apps/agent/controller_turn.py`, modify `run_turn` to persist
budget after every turn path. Wrap the function body in try/finally:

```python
async def run_turn(ctrl: MissionController) -> bool:
    """Execute one turn. Return True if the mission should stop."""
    turn = create_turn(ctrl.session, model=ctrl.model_name)
    ctrl.budget.consume("turns")

    try:
        llm_resp = await ctrl.provider.complete(ctrl.system_prompt, ctrl.messages)
        turn.input_tokens = llm_resp.input_tokens
        turn.output_tokens = llm_resp.output_tokens
        turn.save(update_fields=["input_tokens", "output_tokens"])

        raw: dict | str = {}
        try:
            raw = json.loads(llm_resp.raw_text)
            envelope = parse_action(raw)
        except (json.JSONDecodeError, InvalidActionError) as exc:
            return _handle_invalid(ctrl, turn, str(exc), llm_resp.raw_text)

        try:
            check_phase_action(ctrl.session.current_phase, envelope.action)
        except PhaseViolationError as exc:
            return _handle_denied(ctrl, turn, envelope, str(exc))

        return await _execute(ctrl, turn, envelope)
    finally:
        ctrl.session.consumed_budget = ctrl.budget.consumed_snapshot()
        ctrl.session.save(update_fields=["consumed_budget"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_controller.py::TestConsumedBudgetPersistence -v`
Expected: PASS

- [ ] **Step 5: Update controller._finish to pass budget_snapshot to emit_mission_finished**

In `backend/apps/agent/controller.py`, update `_finish`:

```python
def _finish(self, status: str, reason: str) -> None:
    consumed = self.budget.consumed_snapshot()
    finish_session(self.session, status, consumed)
    from .event_log import build_budget_snapshot
    snapshot = build_budget_snapshot(self.session, consumed)
    emit_mission_finished(self.session, status, reason, budget_snapshot=snapshot)
```

- [ ] **Step 6: Update controller._try_auto_advance to pass budget_snapshot**

In `backend/apps/agent/controller.py`, update `_try_auto_advance`:

```python
def _try_auto_advance(self) -> bool:
    current = self.session.current_phase
    nxt = self._next_slice_phase(current)
    if nxt is None:
        return False
    if not is_valid_transition(current, nxt):
        return False  # pragma: no cover — defensive

    reason = f"auto-advance: {self.plateau.plateau_reason()}"
    from .event_log import build_budget_snapshot, emit_phase_changed
    snapshot = build_budget_snapshot(
        self.session, self.budget.consumed_snapshot(),
    )
    emit_phase_changed(self.session, current, nxt, reason, budget_snapshot=snapshot)
    self.advance_phase(nxt, reason)
    return True
```

- [ ] **Step 7: Update controller_turn call sites to pass enrichment data**

In `backend/apps/agent/controller_turn.py`, update `_handle_denied` to pass
enrichment to `emit_action_denied`:

```python
def _handle_denied(ctrl, turn, envelope: ActionEnvelope, reason: str) -> bool:
    record_action(
        turn=turn, action_type=envelope.action, args_redacted={},
        goal=envelope.goal, reason=envelope.reason,
        hypothesis=envelope.hypothesis,
        validation_status=ValidationStatus.DENIED_PHASE,
    )
    finish_turn(turn, TurnStatus.ACTION_DENIED)
    ctrl.plateau.record_denial()

    from .event_log import build_budget_snapshot, emit_action_denied
    snapshot = build_budget_snapshot(
        ctrl.session, ctrl.budget.consumed_snapshot(),
    )
    emit_action_denied(
        ctrl.session, turn.index, envelope.action, reason,
        goal=envelope.goal, hypothesis=envelope.hypothesis,
        budget_snapshot=snapshot,
    )

    denial = format_observation_message(denial_reason=reason)
    raw = json.dumps({"action": envelope.action})
    ctrl.messages.append({"role": "assistant", "content": raw})
    ctrl.messages.append({"role": "user", "content": denial})
    return False
```

Update `_execute_browser_action` → `_execute` call site to pass enrichment
to `emit_action_executed`:

```python
    obs_dict = await _execute_browser_action(ctrl, turn, action_rec, envelope)
    from .event_log import (
        build_budget_snapshot, emit_action_executed, summarize_observation,
    )
    snapshot = build_budget_snapshot(
        ctrl.session, ctrl.budget.consumed_snapshot(),
    )
    obs_summary = summarize_observation(obs_dict)
    emit_action_executed(
        ctrl.session, turn.index, envelope.action,
        goal=envelope.goal, reason=envelope.reason,
        hypothesis=envelope.hypothesis,
        budget_snapshot=snapshot,
        observation_summary=obs_summary,
    )
    finish_turn(turn, TurnStatus.COMPLETED)
```

- [ ] **Step 8: Run full controller test suite**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_controller.py apps/agent/tests/test_controller_edge.py -v`
Expected: ALL PASS

- [ ] **Step 9: Commit**

```bash
git add backend/apps/agent/controller_turn.py backend/apps/agent/controller.py backend/apps/agent/tests/test_controller.py
git commit -m "feat(agent): persist consumed_budget every turn + pass enrichment to events"
```
