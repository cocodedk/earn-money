---
companion_of: 06-budget-tracker
---

# Task 06 — Budget Tracker Implementation

Part of [Task 06](06-budget-tracker.md). Step 3 implementation code.

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

    def check_all(self) -> None:
        keys = set()
        for limits in (self._mission_limits, self._phase_limits):
            keys.update(_budget_key(k) for k in limits)
        for key in keys:
            if key == "turns":
                self.check(key)
                continue
            m_limit = self._mission_limits.get(f"max_{key}")
            m_consumed = self._mission_consumed.get(key, 0)
            if m_limit is not None and m_consumed and m_consumed >= m_limit:
                raise BudgetExhaustedError(key, "mission", m_limit, m_consumed)
            p_limit = self._phase_limits.get(f"max_{key}")
            p_consumed = self._phase_consumed.get(key, 0)
            if p_limit is not None and p_consumed and p_consumed >= p_limit:
                raise BudgetExhaustedError(key, "phase", p_limit, p_consumed)

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
