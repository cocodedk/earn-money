from __future__ import annotations

import pytest
from apps.agent.phases import PHASE_ORDER, next_phase, is_valid_transition


class TestPhaseOrder:
    def test_phase_order_is_list_of_strings(self):
        assert isinstance(PHASE_ORDER, list)
        assert all(isinstance(p, str) for p in PHASE_ORDER)

    def test_required_phases_present(self):
        for phase in ("recon", "enumerate", "probe", "verify", "report"):
            assert phase in PHASE_ORDER

    def test_report_is_last(self):
        assert PHASE_ORDER[-1] == "report"

    def test_recon_is_first(self):
        assert PHASE_ORDER[0] == "recon"


class TestNextPhase:
    def test_recon_to_enumerate(self):
        assert next_phase("recon") == "enumerate"

    def test_enumerate_to_probe(self):
        assert next_phase("enumerate") == "probe"

    def test_probe_to_verify(self):
        assert next_phase("probe") == "verify"

    def test_verify_to_report(self):
        assert next_phase("verify") == "report"

    def test_report_returns_none(self):
        assert next_phase("report") is None

    def test_unknown_phase_returns_none(self):
        assert next_phase("unknown_phase") is None

    def test_all_phases_have_successor_except_last(self):
        for phase in PHASE_ORDER[:-1]:
            assert next_phase(phase) is not None

    def test_consecutive_phases_are_adjacent(self):
        for i, phase in enumerate(PHASE_ORDER[:-1]):
            assert next_phase(phase) == PHASE_ORDER[i + 1]


class TestIsValidTransition:
    def test_forward_one_step(self):
        assert is_valid_transition("recon", "enumerate") is True
        assert is_valid_transition("enumerate", "probe") is True
        assert is_valid_transition("probe", "verify") is True
        assert is_valid_transition("verify", "report") is True

    def test_skip_forward_is_valid(self):
        assert is_valid_transition("recon", "probe") is True
        assert is_valid_transition("recon", "verify") is True
        assert is_valid_transition("enumerate", "verify") is True

    def test_any_phase_to_report_is_valid(self):
        for phase in PHASE_ORDER[:-1]:
            assert is_valid_transition(phase, "report") is True

    def test_same_phase_is_invalid(self):
        for phase in PHASE_ORDER:
            assert is_valid_transition(phase, phase) is False

    def test_backward_transition_is_invalid(self):
        assert is_valid_transition("enumerate", "recon") is False
        assert is_valid_transition("probe", "recon") is False
        assert is_valid_transition("probe", "enumerate") is False
        assert is_valid_transition("verify", "recon") is False
        assert is_valid_transition("report", "verify") is False

    def test_unknown_from_phase(self):
        assert is_valid_transition("unknown", "enumerate") is False

    def test_unknown_to_phase(self):
        assert is_valid_transition("recon", "unknown") is False

    def test_both_unknown(self):
        assert is_valid_transition("foo", "bar") is False
