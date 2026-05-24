---
tier: CAPABLE
depends_on:
  - 04-action-schemas
files:
  creates:
    - backend/apps/agent/actions/matrix.py
  modifies:
    - backend/apps/agent/tests/test_actions.py
allow_extra_files: false
---

### Task 5: Phase-action matrix enforcement

**Files:**
- Create: `backend/apps/agent/actions/matrix.py`
- Modify: `backend/apps/agent/tests/test_actions.py`

- [ ] **Step 1: Write tests for matrix enforcement**

```python
# append to backend/apps/agent/tests/test_actions.py
from apps.agent.actions.matrix import (
    check_phase_action, allowed_actions_for_phase, PhaseViolationError,
)


def test_observe_page_allowed_in_recon():
    check_phase_action("recon", "observe_page")


def test_observe_page_denied_in_report():
    with pytest.raises(PhaseViolationError):
        check_phase_action("report", "observe_page")


def test_navigate_allowed_in_enumerate():
    check_phase_action("enumerate", "navigate")


def test_submit_candidate_denied_in_recon():
    with pytest.raises(PhaseViolationError):
        check_phase_action("recon", "submit_candidate")


def test_submit_candidate_allowed_in_enumerate():
    check_phase_action("enumerate", "submit_candidate")


def test_store_note_allowed_everywhere():
    for phase in ("recon", "enumerate", "probe", "verify", "report"):
        check_phase_action(phase, "store_note")


def test_stop_allowed_everywhere():
    for phase in ("recon", "enumerate", "probe", "verify", "report"):
        check_phase_action(phase, "stop")


def test_inspect_asset_denied_in_report():
    with pytest.raises(PhaseViolationError):
        check_phase_action("report", "inspect_asset")


def test_allowed_actions_for_phase_filters_deferred_actions():
    allowed = allowed_actions_for_phase("enumerate")
    assert "navigate" in allowed
    assert "click" not in allowed
    assert "run_tool" not in allowed
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest apps/agent/tests/test_actions.py -v -k "phase"` 
Expected: FAIL

- [ ] **Step 3: Implement matrix**

```python
# backend/apps/agent/actions/matrix.py
from __future__ import annotations


class PhaseViolationError(ValueError):
    pass


IMPLEMENTED_SLICE_1_ACTIONS = {
    "observe_page", "navigate", "inspect_asset",
    "store_note", "submit_candidate",
    "request_phase_transition", "stop",
}


_PHASE_ACTION_MATRIX: dict[str, set[str]] = {
    "recon": {
        "observe_page", "navigate", "inspect_asset",
        "store_note", "request_phase_transition", "stop",
    },
    "enumerate": {
        "observe_page", "navigate", "click", "fill_form",
        "inspect_asset", "store_note", "submit_candidate",
        "request_phase_transition", "stop",
    },
    "probe": {
        "observe_page", "navigate", "click", "fill_form", "submit_form",
        "http_request", "run_stub", "run_tool", "inspect_asset",
        "store_note", "submit_candidate", "request_verify",
        "request_phase_transition", "stop",
    },
    "verify": {
        "observe_page", "navigate", "click", "fill_form", "submit_form",
        "http_request", "store_note", "submit_candidate",
        "request_verify", "request_phase_transition", "stop",
    },
    "report": {
        "store_note", "submit_candidate", "stop",
    },
}


def check_phase_action(phase: str, action: str) -> None:
    allowed = _PHASE_ACTION_MATRIX.get(phase)
    if allowed is None:
        raise PhaseViolationError(f"Unknown phase: {phase!r}")
    if action not in allowed:
        raise PhaseViolationError(
            f"Action {action!r} is not allowed in phase {phase!r}"
        )


def allowed_actions_for_phase(phase: str) -> list[str]:
    allowed = _PHASE_ACTION_MATRIX.get(phase)
    if allowed is None:
        raise PhaseViolationError(f"Unknown phase: {phase!r}")
    return sorted(allowed & IMPLEMENTED_SLICE_1_ACTIONS)
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest apps/agent/tests/test_actions.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/actions/matrix.py backend/apps/agent/tests/test_actions.py
git commit -m "feat(agent): add phase-action matrix enforcement"
```
