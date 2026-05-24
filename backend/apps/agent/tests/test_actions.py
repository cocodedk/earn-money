from __future__ import annotations

import pytest
from apps.agent.actions import parse_action, ActionEnvelope, InvalidActionError
from apps.agent.actions.matrix import (
    PhaseViolationError,
    check_phase_action,
    allowed_actions_for_phase,
)


def _base(**kwargs) -> dict:
    return {
        "action": "observe_page",
        "goal": "see the page",
        "reason": "need context",
        "hypothesis": "page is loaded",
        **kwargs,
    }


class TestObservePage:
    def test_defaults(self):
        env = parse_action(_base())
        assert env.action == "observe_page"
        assert env.parsed.include_screenshot is False
        assert env.parsed.element_ids is None

    def test_with_screenshot(self):
        env = parse_action(_base(include_screenshot=True, element_ids=["a", "b"]))
        assert env.parsed.include_screenshot is True
        assert env.parsed.element_ids == ["a", "b"]

    def test_envelope_fields(self):
        env = parse_action(_base())
        assert isinstance(env, ActionEnvelope)
        assert env.goal == "see the page"
        assert env.reason == "need context"
        assert env.hypothesis == "page is loaded"


class TestNavigate:
    def _nav(self, **kw):
        return _base(action="navigate", **kw)

    def test_path_only(self):
        env = parse_action(self._nav(path="/login"))
        assert env.parsed.path == "/login"

    def test_url_ref(self):
        env = parse_action(self._nav(url_ref="asset-42"))
        assert env.parsed.url_ref == "asset-42"

    def test_reject_javascript(self):
        with pytest.raises(InvalidActionError, match="javascript:"):
            parse_action(self._nav(path="javascript:alert(1)"))

    def test_reject_data(self):
        with pytest.raises(InvalidActionError, match="data:"):
            parse_action(self._nav(path="data:text/html,<h1>x</h1>"))

    def test_reject_protocol_relative(self):
        with pytest.raises(InvalidActionError, match="//"):
            parse_action(self._nav(path="//evil.com/"))

    def test_reject_absolute_url(self):
        with pytest.raises(InvalidActionError, match="://"):
            parse_action(self._nav(url_ref="https://evil.com/"))


class TestInspectAsset:
    def test_valid(self):
        env = parse_action(_base(action="inspect_asset", asset_ref="ref-1"))
        assert env.parsed.asset_ref == "ref-1"

    def test_missing_asset_ref(self):
        with pytest.raises(InvalidActionError):
            parse_action(_base(action="inspect_asset"))


class TestStoreNote:
    def test_valid_types(self):
        for note_type in ("hypothesis", "gap", "credential_label", "route", "parameter", "candidate"):
            env = parse_action(_base(action="store_note", note_type=note_type, content={}))
            assert env.parsed.note_type == note_type

    def test_invalid_type(self):
        with pytest.raises(InvalidActionError, match="Invalid note_type"):
            parse_action(_base(action="store_note", note_type="unknown", content={}))

    def test_missing_content(self):
        with pytest.raises(InvalidActionError):
            parse_action(_base(action="store_note", note_type="gap"))


class TestSubmitCandidate:
    def test_valid(self):
        env = parse_action(_base(
            action="submit_candidate",
            category="sqli",
            description="found sqli",
            evidence_refs=["e1"],
        ))
        assert env.parsed.category == "sqli"
        assert env.parsed.evidence_refs == ["e1"]

    def test_missing_field(self):
        with pytest.raises(InvalidActionError):
            parse_action(_base(action="submit_candidate", category="sqli"))


class TestRequestPhaseTransition:
    def test_valid(self):
        env = parse_action(_base(
            action="request_phase_transition",
            from_phase="recon",
            to_phase="enumerate",
            reason="done",
            evidence_refs=[],
        ))
        assert env.parsed.from_phase == "recon"
        assert env.parsed.remaining_questions is None

    def test_with_remaining_questions(self):
        env = parse_action(_base(
            action="request_phase_transition",
            from_phase="recon",
            to_phase="enumerate",
            reason="done",
            evidence_refs=[],
            remaining_questions=["q1"],
        ))
        assert env.parsed.remaining_questions == ["q1"]


class TestStopAction:
    def test_valid(self):
        env = parse_action(_base(action="stop", reason="done"))
        assert env.parsed.reason == "done"

    def test_reason_taken_from_envelope_when_not_separate(self):
        # "reason" is an envelope field; StopAction.reason is populated from it.
        env = parse_action(_base(action="stop"))
        assert env.parsed.reason == "need context"  # from _base() envelope default


class TestUnknownAction:
    def test_raises(self):
        with pytest.raises(InvalidActionError, match="Unknown action"):
            parse_action(_base(action="fly_to_the_moon"))


class TestMissingEnvelopeFields:
    def test_missing_goal(self):
        raw = {"action": "stop", "reason": "r", "reason_field": "x", "hypothesis": "h"}
        with pytest.raises(InvalidActionError, match="goal"):
            parse_action(raw)

    def test_missing_hypothesis(self):
        raw = {"action": "stop", "goal": "g", "reason": "r"}
        with pytest.raises(InvalidActionError, match="hypothesis"):
            parse_action(raw)


class TestPhaseActionMatrix:
    def test_recon_allows_observe_page(self):
        check_phase_action("recon", "observe_page")

    def test_recon_allows_navigate(self):
        check_phase_action("recon", "navigate")

    def test_recon_allows_inspect_asset(self):
        check_phase_action("recon", "inspect_asset")

    def test_recon_allows_store_note(self):
        check_phase_action("recon", "store_note")

    def test_recon_allows_request_phase_transition(self):
        check_phase_action("recon", "request_phase_transition")

    def test_recon_allows_stop(self):
        check_phase_action("recon", "stop")

    def test_recon_rejects_click(self):
        with pytest.raises(PhaseViolationError, match="click"):
            check_phase_action("recon", "click")

    def test_recon_rejects_submit_form(self):
        with pytest.raises(PhaseViolationError):
            check_phase_action("recon", "submit_form")

    def test_enumerate_adds_click(self):
        check_phase_action("enumerate", "click")

    def test_enumerate_adds_fill_form(self):
        check_phase_action("enumerate", "fill_form")

    def test_enumerate_adds_submit_candidate(self):
        check_phase_action("enumerate", "submit_candidate")

    def test_enumerate_inherits_recon_actions(self):
        check_phase_action("enumerate", "observe_page")
        check_phase_action("enumerate", "navigate")

    def test_enumerate_rejects_submit_form(self):
        with pytest.raises(PhaseViolationError):
            check_phase_action("enumerate", "submit_form")

    def test_probe_adds_submit_form(self):
        check_phase_action("probe", "submit_form")

    def test_probe_adds_http_request(self):
        check_phase_action("probe", "http_request")

    def test_probe_adds_run_stub(self):
        check_phase_action("probe", "run_stub")

    def test_probe_adds_run_tool(self):
        check_phase_action("probe", "run_tool")

    def test_probe_adds_request_verify(self):
        check_phase_action("probe", "request_verify")

    def test_verify_inherits_probe_actions(self):
        check_phase_action("verify", "submit_form")
        check_phase_action("verify", "http_request")

    def test_report_allows_store_note(self):
        check_phase_action("report", "store_note")

    def test_report_allows_submit_candidate(self):
        check_phase_action("report", "submit_candidate")

    def test_report_allows_stop(self):
        check_phase_action("report", "stop")

    def test_report_rejects_navigate(self):
        with pytest.raises(PhaseViolationError):
            check_phase_action("report", "navigate")

    def test_report_rejects_click(self):
        with pytest.raises(PhaseViolationError):
            check_phase_action("report", "click")

    def test_unknown_phase_raises(self):
        with pytest.raises(PhaseViolationError, match="Unknown phase"):
            check_phase_action("unknown_phase", "observe_page")

    def test_allowed_actions_for_recon_is_sorted(self):
        actions = allowed_actions_for_phase("recon")
        assert actions == sorted(actions)

    def test_allowed_actions_for_recon_contains_expected(self):
        actions = allowed_actions_for_phase("recon")
        assert "observe_page" in actions
        assert "navigate" in actions
        assert "click" not in actions

    def test_allowed_actions_for_unknown_phase_raises(self):
        with pytest.raises(PhaseViolationError, match="Unknown phase"):
            allowed_actions_for_phase("nonexistent")
