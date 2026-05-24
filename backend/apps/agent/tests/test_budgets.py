from __future__ import annotations

import pytest
from apps.agent.budgets import BudgetTracker, BudgetExhaustedError


def _mission(turns=10, llm=5):
    return {"max_turns": turns, "max_llm_calls": llm}


def _phase(turns=3):
    return {"max_turns": turns}


class TestCreation:
    def test_fresh_tracker_has_zero_consumed(self):
        bt = BudgetTracker(_mission(), _phase())
        snap = bt.consumed_snapshot()
        assert snap["mission"] == {}
        assert snap["phase"] == {}

    def test_remaining_equals_limit_initially(self):
        bt = BudgetTracker(_mission(turns=10), _phase(turns=3))
        assert bt.remaining("turns") == 10
        assert bt.phase_remaining("turns") == 3


class TestConsume:
    def test_consume_decrements_both(self):
        bt = BudgetTracker(_mission(turns=10), _phase(turns=3))
        bt.consume("turns", 2)
        assert bt.remaining("turns") == 8
        assert bt.phase_remaining("turns") == 1

    def test_consume_default_amount_is_one(self):
        bt = BudgetTracker(_mission(turns=10), _phase(turns=3))
        bt.consume("turns")
        assert bt.remaining("turns") == 9

    def test_consume_untracked_dimension_is_ok(self):
        bt = BudgetTracker(_mission(), _phase())
        bt.consume("http_requests", 5)
        snap = bt.consumed_snapshot()
        assert snap["mission"]["http_requests"] == 5


class TestMissionExhausted:
    def test_raises_when_mission_limit_reached(self):
        bt = BudgetTracker(_mission(turns=2), _phase(turns=100))
        bt.consume("turns", 2)
        with pytest.raises(BudgetExhaustedError) as exc_info:
            bt.check("turns")
        err = exc_info.value
        assert err.dimension == "turns"
        assert err.scope == "mission"
        assert err.limit == 2
        assert err.consumed == 2

    def test_raises_on_overshoot(self):
        bt = BudgetTracker(_mission(turns=1), _phase(turns=100))
        bt.consume("turns", 5)
        with pytest.raises(BudgetExhaustedError, match="mission"):
            bt.check("turns")


class TestPhaseExhausted:
    def test_raises_when_phase_limit_reached(self):
        bt = BudgetTracker(_mission(turns=100), _phase(turns=2))
        bt.consume("turns", 2)
        with pytest.raises(BudgetExhaustedError) as exc_info:
            bt.check("turns")
        assert exc_info.value.scope == "phase"

    def test_phase_raises_before_mission(self):
        bt = BudgetTracker(_mission(turns=100), _phase(turns=1))
        bt.consume("turns", 1)
        with pytest.raises(BudgetExhaustedError, match="phase"):
            bt.check("turns")


class TestSwitchPhase:
    def test_switch_resets_phase_consumed(self):
        bt = BudgetTracker(_mission(turns=100), _phase(turns=2))
        bt.consume("turns", 2)
        bt.switch_phase({"max_turns": 5})
        # phase consumed reset; should not raise
        bt.check("turns")
        assert bt.phase_remaining("turns") == 5

    def test_mission_consumed_preserved_after_switch(self):
        bt = BudgetTracker(_mission(turns=100), _phase(turns=2))
        bt.consume("turns", 2)
        bt.switch_phase({"max_turns": 5})
        assert bt.remaining("turns") == 98


class TestConsumedSnapshot:
    def test_snapshot_reflects_consumption(self):
        bt = BudgetTracker(_mission(turns=10, llm=5), _phase(turns=3))
        bt.consume("turns", 3)
        bt.consume("llm_calls", 2)
        snap = bt.consumed_snapshot()
        assert snap["mission"] == {"turns": 3, "llm_calls": 2}
        assert snap["phase"] == {"turns": 3, "llm_calls": 2}

    def test_snapshot_is_copy(self):
        bt = BudgetTracker(_mission(), _phase())
        snap = bt.consumed_snapshot()
        snap["mission"]["turns"] = 999
        assert bt.consumed_snapshot()["mission"].get("turns") is None


class TestUnboundedDimensions:
    def test_unbounded_never_raises(self):
        bt = BudgetTracker({}, {})
        for _ in range(1000):
            bt.consume("turns")
        bt.check("turns")  # should not raise

    def test_remaining_returns_large_int_for_unbounded(self):
        bt = BudgetTracker({}, {})
        assert bt.remaining("turns") == 2**31
        assert bt.phase_remaining("turns") == 2**31


class TestCheckAll:
    def test_check_all_raises_first_exhausted(self):
        bt = BudgetTracker({"max_turns": 2, "max_llm_calls": 10}, {"max_turns": 5})
        bt.consume("turns", 3)
        with pytest.raises(BudgetExhaustedError):
            bt.check_all()

    def test_check_all_passes_when_all_ok(self):
        bt = BudgetTracker({"max_turns": 10}, {"max_turns": 5})
        bt.consume("turns", 2)
        bt.check_all()  # no raise


class TestErrorStr:
    def test_str_representation(self):
        err = BudgetExhaustedError(
            dimension="turns", scope="mission", limit=5, consumed=5
        )
        assert "turns" in str(err)
        assert "mission" in str(err)
