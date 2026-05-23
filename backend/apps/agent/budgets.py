from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BudgetExhaustedError(RuntimeError):
    """Raised when a budget dimension limit is reached."""

    dimension: str
    scope: str  # "mission" or "phase"
    limit: int
    consumed: int

    def __str__(self) -> str:
        return (
            f"Budget exhausted: {self.dimension!r} {self.scope} limit "
            f"{self.limit} reached (consumed={self.consumed})"
        )


def _extract_limit(budget: dict, dimension: str) -> int | None:
    """Return the limit for a dimension, or None if unbounded."""
    key = f"max_{dimension}"
    return budget.get(key)


class BudgetTracker:
    """Tracks mission-level and phase-level budget consumption."""

    def __init__(self, mission_budget: dict, phase_budget: dict) -> None:
        self._mission_budget = dict(mission_budget)
        self._phase_budget = dict(phase_budget)
        self._mission_consumed: dict[str, int] = {}
        self._phase_consumed: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def consume(self, dimension: str, amount: int = 1) -> None:
        """Increment consumed counts for both mission and phase."""
        self._mission_consumed[dimension] = (
            self._mission_consumed.get(dimension, 0) + amount
        )
        self._phase_consumed[dimension] = (
            self._phase_consumed.get(dimension, 0) + amount
        )

    def switch_phase(self, new_phase_budget: dict) -> None:
        """Reset phase budget to new limits and clear phase consumed counts."""
        self._phase_budget = dict(new_phase_budget)
        self._phase_consumed = {}

    # ------------------------------------------------------------------
    # Checks
    # ------------------------------------------------------------------

    def check(self, dimension: str) -> None:
        """Raise BudgetExhaustedError if mission or phase limit is reached."""
        self._check_scope(dimension, "mission", self._mission_budget, self._mission_consumed)
        self._check_scope(dimension, "phase", self._phase_budget, self._phase_consumed)

    def check_all(self) -> None:
        """Check all dimensions that appear in either budget."""
        dimensions = set()
        for key in self._mission_budget:
            if key.startswith("max_"):
                dimensions.add(key[4:])
        for key in self._phase_budget:
            if key.startswith("max_"):
                dimensions.add(key[4:])
        for dim in dimensions:
            self.check(dim)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def remaining(self, dimension: str) -> int:
        """Return mission remaining for dimension. Returns max int if unbounded."""
        limit = _extract_limit(self._mission_budget, dimension)
        if limit is None:
            return 2**31
        consumed = self._mission_consumed.get(dimension, 0)
        return max(0, limit - consumed)

    def phase_remaining(self, dimension: str) -> int:
        """Return phase remaining for dimension. Returns max int if unbounded."""
        limit = _extract_limit(self._phase_budget, dimension)
        if limit is None:
            return 2**31
        consumed = self._phase_consumed.get(dimension, 0)
        return max(0, limit - consumed)

    def consumed_snapshot(self) -> dict:
        """Return a snapshot of both mission and phase consumed counts."""
        return {
            "mission": dict(self._mission_consumed),
            "phase": dict(self._phase_consumed),
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _check_scope(
        self,
        dimension: str,
        scope: str,
        budget: dict,
        consumed: dict,
    ) -> None:
        limit = _extract_limit(budget, dimension)
        if limit is None:
            return
        used = consumed.get(dimension, 0)
        if used >= limit:
            raise BudgetExhaustedError(
                dimension=dimension,
                scope=scope,
                limit=limit,
                consumed=used,
            )
