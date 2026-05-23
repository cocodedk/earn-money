### Task 17: Phase transition logic

**Files:**
- Create: `backend/apps/agent/phases.py`
- Create: `backend/apps/agent/tests/test_phases.py`

- [ ] **Step 1: Write tests**

```python
# backend/apps/agent/tests/test_phases.py
from apps.agent.phases import next_phase, is_valid_transition, PHASE_ORDER


def test_phase_order():
    assert PHASE_ORDER == ["recon", "enumerate", "probe", "verify", "report"]


def test_next_phase_from_recon():
    assert next_phase("recon") == "enumerate"


def test_next_phase_from_report_is_none():
    assert next_phase("report") is None


def test_valid_forward_transition():
    assert is_valid_transition("recon", "enumerate")


def test_invalid_backward_transition():
    assert not is_valid_transition("enumerate", "recon")


def test_skip_transition_not_allowed():
    assert not is_valid_transition("recon", "probe")


def test_report_transition_from_any():
    for phase in ("recon", "enumerate", "probe", "verify"):
        assert is_valid_transition(phase, "report")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest apps/agent/tests/test_phases.py -v`
Expected: FAIL

- [ ] **Step 3: Implement**

```python
# backend/apps/agent/phases.py
from __future__ import annotations

PHASE_ORDER = ["recon", "enumerate", "probe", "verify", "report"]


def next_phase(current: str) -> str | None:
    try:
        idx = PHASE_ORDER.index(current)
    except ValueError:
        return None
    if idx + 1 < len(PHASE_ORDER):
        return PHASE_ORDER[idx + 1]
    return None


def is_valid_transition(from_phase: str, to_phase: str) -> bool:
    if to_phase == "report":
        return from_phase in PHASE_ORDER and from_phase != "report"
    try:
        fi = PHASE_ORDER.index(from_phase)
        ti = PHASE_ORDER.index(to_phase)
    except ValueError:
        return False
    return ti == fi + 1
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest apps/agent/tests/test_phases.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/phases.py backend/apps/agent/tests/test_phases.py
git commit -m "feat(agent): add phase transition validation"
```
