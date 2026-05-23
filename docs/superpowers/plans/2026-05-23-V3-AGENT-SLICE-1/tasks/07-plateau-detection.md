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
