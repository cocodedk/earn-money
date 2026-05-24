---
tier: CAPABLE
depends_on:
  - 03-migrations
files:
  creates:
    - backend/apps/agent/budgets.py
    - backend/apps/agent/tests/test_budgets.py
  modifies: []
allow_extra_files: false
---

### Task 6: Budget accounting

**Files:**
- Create: `backend/apps/agent/budgets.py`
- Create: `backend/apps/agent/tests/test_budgets.py`

- [ ] **Step 1: Write tests for budget tracker**

```python
# backend/apps/agent/tests/test_budgets.py
import pytest
from apps.agent.budgets import BudgetTracker, BudgetExhaustedError


def test_budget_tracker_creation():
    mission = {"max_turns": 25, "max_http_requests": 60, "max_asset_inspections": 10}
    phase = {"max_turns": 6, "max_http_requests": 20, "max_asset_inspections": 5}
    tracker = BudgetTracker(mission_budget=mission, phase_budget=phase)
    assert tracker.remaining("turns") == 25
    assert tracker.phase_remaining("turns") == 6


def test_consume_decrements_both():
    mission = {"max_turns": 25}
    phase = {"max_turns": 6}
    tracker = BudgetTracker(mission_budget=mission, phase_budget=phase)
    tracker.consume("turns", 1)
    assert tracker.remaining("turns") == 24
    assert tracker.phase_remaining("turns") == 5


def test_mission_budget_exhausted_raises():
    mission = {"max_turns": 2}
    phase = {"max_turns": 10}
    tracker = BudgetTracker(mission_budget=mission, phase_budget=phase)
    tracker.consume("turns", 2)
    with pytest.raises(BudgetExhaustedError, match="mission"):
        tracker.check("turns")


def test_phase_budget_exhausted_raises():
    mission = {"max_turns": 25}
    phase = {"max_turns": 3}
    tracker = BudgetTracker(mission_budget=mission, phase_budget=phase)
    tracker.consume("turns", 3)
    with pytest.raises(BudgetExhaustedError, match="phase"):
        tracker.check("turns")


def test_switch_phase_resets_phase_consumed():
    mission = {"max_turns": 25}
    phase = {"max_turns": 6}
    tracker = BudgetTracker(mission_budget=mission, phase_budget=phase)
    tracker.consume("turns", 5)
    tracker.switch_phase({"max_turns": 14})
    assert tracker.phase_remaining("turns") == 14
    assert tracker.remaining("turns") == 20


def test_consumed_snapshot():
    mission = {"max_turns": 25, "max_http_requests": 60}
    phase = {"max_turns": 6, "max_http_requests": 20}
    tracker = BudgetTracker(mission_budget=mission, phase_budget=phase)
    tracker.consume("turns", 3)
    tracker.consume("http_requests", 10)
    snap = tracker.consumed_snapshot()
    assert snap["turns"] == 3
    assert snap["http_requests"] == 10


def test_dimension_not_in_budget_is_unbounded():
    mission = {"max_turns": 25}
    phase = {"max_turns": 6}
    tracker = BudgetTracker(mission_budget=mission, phase_budget=phase)
    tracker.check("http_requests")


def test_check_all_covers_non_turn_dimensions():
    mission = {"max_turns": 25, "max_http_requests": 2}
    phase = {"max_turns": 6, "max_http_requests": 10}
    tracker = BudgetTracker(mission_budget=mission, phase_budget=phase)
    tracker.consume("http_requests", 2)
    with pytest.raises(BudgetExhaustedError, match="http_requests"):
        tracker.check_all()


def test_zero_budget_dimension_does_not_block_turn_check_until_used():
    mission = {"max_turns": 25, "max_http_requests": 0}
    phase = {"max_turns": 6, "max_http_requests": 0}
    tracker = BudgetTracker(mission_budget=mission, phase_budget=phase)
    tracker.check_all()
    with pytest.raises(BudgetExhaustedError, match="http_requests"):
        tracker.check("http_requests")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest apps/agent/tests/test_budgets.py -v`
Expected: FAIL

- [ ] **Step 3: Implement** — see [06-budget-tracker-impl.md](06-budget-tracker-impl.md)

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest apps/agent/tests/test_budgets.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/budgets.py backend/apps/agent/tests/test_budgets.py
git commit -m "feat(agent): add dual-layer budget tracker"
```
