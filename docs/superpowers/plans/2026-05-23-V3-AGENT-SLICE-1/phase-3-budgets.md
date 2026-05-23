# Phase 3 — Budgets & Plateau Detection

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest apps/agent/tests/test_budgets.py -v`
Expected: FAIL

- [ ] **Step 3: Implement budget tracker**

```python
# backend/apps/agent/budgets.py
from __future__ import annotations


class BudgetExhaustedError(RuntimeError):
    def __init__(self, dimension: str, scope: str, limit: int, consumed: int):
        self.dimension = dimension
        self.scope = scope
        super().__init__(
            f"{scope} budget exhausted: {dimension} "
            f"({consumed}/{limit})"
        )


class BudgetTracker:
    def __init__(
        self,
        mission_budget: dict[str, int],
        phase_budget: dict[str, int],
    ) -> None:
        self._mission_limits = dict(mission_budget)
        self._phase_limits = dict(phase_budget)
        self._mission_consumed: dict[str, int] = {}
        self._phase_consumed: dict[str, int] = {}

    def consume(self, dimension: str, amount: int = 1) -> None:
        key = _budget_key(dimension)
        self._mission_consumed[key] = self._mission_consumed.get(key, 0) + amount
        self._phase_consumed[key] = self._phase_consumed.get(key, 0) + amount

    def check(self, dimension: str) -> None:
        key = _budget_key(dimension)
        m_limit = self._mission_limits.get(f"max_{key}")
        if m_limit is not None:
            consumed = self._mission_consumed.get(key, 0)
            if consumed >= m_limit:
                raise BudgetExhaustedError(key, "mission", m_limit, consumed)
        p_limit = self._phase_limits.get(f"max_{key}")
        if p_limit is not None:
            consumed = self._phase_consumed.get(key, 0)
            if consumed >= p_limit:
                raise BudgetExhaustedError(key, "phase", p_limit, consumed)

    def remaining(self, dimension: str) -> int:
        key = _budget_key(dimension)
        limit = self._mission_limits.get(f"max_{key}")
        if limit is None:
            return 999999
        return max(0, limit - self._mission_consumed.get(key, 0))

    def phase_remaining(self, dimension: str) -> int:
        key = _budget_key(dimension)
        limit = self._phase_limits.get(f"max_{key}")
        if limit is None:
            return 999999
        return max(0, limit - self._phase_consumed.get(key, 0))

    def switch_phase(self, new_phase_budget: dict[str, int]) -> None:
        self._phase_limits = dict(new_phase_budget)
        self._phase_consumed = {}

    def consumed_snapshot(self) -> dict[str, int]:
        return dict(self._mission_consumed)


def _budget_key(dimension: str) -> str:
    return dimension.removeprefix("max_")
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest apps/agent/tests/test_budgets.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/budgets.py backend/apps/agent/tests/test_budgets.py
git commit -m "feat(agent): add dual-layer budget tracker"
```

### Task 7: Plateau detection

**Files:**
- Create: `backend/apps/agent/plateau.py`
- Create: `backend/apps/agent/tests/test_plateau.py`

- [ ] **Step 1: Write tests for plateau detector**

```python
# backend/apps/agent/tests/test_plateau.py
import pytest
from apps.agent.plateau import PlateauDetector


def test_no_plateau_initially():
    pd = PlateauDetector()
    assert not pd.is_plateaued()


def test_plateau_after_max_turns_without_route():
    pd = PlateauDetector(max_turns_without_new_route=3)
    pd.record_turn(new_routes=0, new_elements=1)
    pd.record_turn(new_routes=0, new_elements=1)
    pd.record_turn(new_routes=0, new_elements=1)
    assert pd.is_plateaued()
    assert "route" in pd.plateau_reason()


def test_route_discovery_resets_counter():
    pd = PlateauDetector(max_turns_without_new_route=3)
    pd.record_turn(new_routes=0, new_elements=0)
    pd.record_turn(new_routes=0, new_elements=0)
    pd.record_turn(new_routes=1, new_elements=0)
    assert not pd.is_plateaued()


def test_plateau_after_repeated_denials():
    pd = PlateauDetector(max_repeated_denials=3)
    pd.record_denial()
    pd.record_denial()
    pd.record_denial()
    assert pd.is_plateaued()
    assert "denial" in pd.plateau_reason()


def test_plateau_after_invalid_actions():
    pd = PlateauDetector(max_invalid_actions=2)
    pd.record_invalid()
    pd.record_invalid()
    assert pd.is_plateaued()


def test_successful_action_resets_denial_counter():
    pd = PlateauDetector(max_repeated_denials=3)
    pd.record_denial()
    pd.record_denial()
    pd.record_turn(new_routes=0, new_elements=0)
    pd.record_denial()
    assert not pd.is_plateaued()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest apps/agent/tests/test_plateau.py -v`
Expected: FAIL

- [ ] **Step 3: Implement plateau detector**

```python
# backend/apps/agent/plateau.py
from __future__ import annotations


class PlateauDetector:
    def __init__(
        self,
        max_turns_without_new_route: int = 3,
        max_turns_without_new_interactive_element: int = 3,
        max_repeated_denials: int = 3,
        max_invalid_actions: int = 2,
    ) -> None:
        self._max_no_route = max_turns_without_new_route
        self._max_no_element = max_turns_without_new_interactive_element
        self._max_denials = max_repeated_denials
        self._max_invalid = max_invalid_actions
        self._turns_without_route = 0
        self._turns_without_element = 0
        self._consecutive_denials = 0
        self._consecutive_invalid = 0
        self._reason: str | None = None

    def record_turn(self, new_routes: int, new_elements: int) -> None:
        self._consecutive_denials = 0
        self._consecutive_invalid = 0
        if new_routes > 0:
            self._turns_without_route = 0
        else:
            self._turns_without_route += 1
        if new_elements > 0:
            self._turns_without_element = 0
        else:
            self._turns_without_element += 1

    def record_denial(self) -> None:
        self._consecutive_denials += 1

    def record_invalid(self) -> None:
        self._consecutive_invalid += 1

    def is_plateaued(self) -> bool:
        if self._turns_without_route >= self._max_no_route:
            self._reason = "No new route discovered"
            return True
        if self._turns_without_element >= self._max_no_element:
            self._reason = "No new interactive element discovered"
            return True
        if self._consecutive_denials >= self._max_denials:
            self._reason = "Repeated denial plateau"
            return True
        if self._consecutive_invalid >= self._max_invalid:
            self._reason = "Repeated invalid action plateau"
            return True
        return False

    def plateau_reason(self) -> str:
        return self._reason or ""
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest apps/agent/tests/test_plateau.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/plateau.py backend/apps/agent/tests/test_plateau.py
git commit -m "feat(agent): add plateau detection for phase advancement"
```
