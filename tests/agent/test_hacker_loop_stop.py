"""STOP-validation tests for HackerLoop.

STOP gets rejected when turns remain AND any applicable action class
is still untried; bounded at 2 consecutive rejections to prevent
infinite loops if the LLM keeps emitting STOP.
"""
from ._test_hacker_loop_helpers import _j, _loop


class TestStopValidation:
    """STOP gets rejected when turns remain AND any applicable action
    class is still untried; bounded at 2 consecutive rejections to
    prevent infinite loops if the LLM keeps emitting STOP."""

    def test_stop_rejected_when_classes_untried(self):
        """Empty session has discovery_get + auth_discovery applicable.
        STOP on turn 1 is rejected; the loop continues for at least one
        more turn instead of returning the 'done' reason."""
        loop = _loop([
            _j(tool="stop", category="stop", args={"reason": "done"}),
            _j(tool="get", category="http_get", args={"path": "/"}),
        ], presolved=False)
        result = loop.run()
        # Rejected STOP must NOT short-circuit to 'done'.
        assert result.stop_reason != "done"
        # At least 2 turns elapsed (rejected stop on 1, real GET on 2).
        assert result.turns >= 2

    def test_stop_accepted_when_no_applicable_classes(self):
        """All classes pre-marked tried → STOP on turn 1 accepted."""
        loop = _loop([_j(tool="stop", category="stop", args={"reason": "done"})])
        # _loop default `presolved=True` marks all classes tried.
        result = loop.run()
        assert result.stop_reason == "done"
        assert result.turns == 1

    def test_stop_accepted_at_max_turns(self):
        """Even with applicable classes, max_turns wins — engine returns
        max_turns naturally without needing STOP at all."""
        # Provide enough GETs to exhaust max_turns; engine will stop on its own.
        replies = [_j(tool="get", category="http_get", args={"path": "/"})] * 10
        loop = _loop(replies, max_turns=3, presolved=False)
        result = loop.run()
        assert result.stop_reason == "max_turns"
        assert result.turns == 3

    def test_bounded_rejection_returns_policy_stop(self):
        """LLM emits STOP twice in a row → engine bails with policy_stop
        rather than looping forever."""
        loop = _loop([
            _j(tool="stop", category="stop", args={"reason": "tired"}),
            _j(tool="stop", category="stop", args={"reason": "still tired"}),
        ], presolved=False)
        result = loop.run()
        assert result.stop_reason == "policy_stop"

    def test_rejection_counter_resets_after_non_stop_action(self):
        """STOP rejected → GET → STOP rejected → GET → STOP rejected.
        Counter resets after each non-STOP, so the run keeps going
        instead of bailing at 2 rejections."""
        loop = _loop([
            _j(tool="stop", category="stop", args={}),
            _j(tool="get", category="http_get", args={"path": "/"}),
            _j(tool="stop", category="stop", args={}),
            _j(tool="get", category="http_get", args={"path": "/robots.txt"}),
            _j(tool="stop", category="stop", args={}),
        ], max_turns=10, presolved=False)
        result = loop.run()
        # Three rejected stops + two real GETs = 5 turns total, then run
        # continues (mock exhausted on the 6th call). What matters: no
        # policy_stop, because counter reset between rejections.
        assert result.stop_reason != "policy_stop"

    def test_action_class_recorded_after_successful_execution(self):
        """A successful GET / marks discovery_get as tried on the session."""
        from earn_money.agent.action_classes import ActionClass
        loop = _loop([
            _j(tool="get", category="http_get", args={"path": "/"}),
            _j(tool="stop", category="stop", args={"reason": "done"}),
        ], presolved=False)
        # Pre-mark auth_discovery so STOP is valid after only discovery_get fires
        loop.session.tried_action_classes.add(ActionClass.AUTH_DISCOVERY)
        result = loop.run()
        assert ActionClass.DISCOVERY_GET in loop.session.tried_action_classes
        assert result.stop_reason == "done"

    def test_prompt_includes_coverage_block_in_plain_english(self):
        loop = _loop([_j(tool="stop", category="stop", args={})])
        prompt = loop._build_prompt()
        assert "=== Coverage status ===" in prompt
        assert "Already tried:" in prompt or "Still useful if allowed:" in prompt

    def test_rejected_stop_surfaced_in_next_prompt(self):
        """After a STOP rejection, the next prompt includes the rejection
        reason so the LLM knows what's expected. Once a non-STOP action
        fires the rejection note is cleared."""
        loop = _loop([
            _j(tool="stop", category="stop", args={}),
            _j(tool="get", category="http_get", args={"path": "/"}),
            _j(tool="stop", category="stop", args={"reason": "done"}),
        ], presolved=False)
        # Pre-mark auth_discovery so the final STOP succeeds after only
        # discovery_get fires.
        from earn_money.agent.action_classes import ActionClass
        loop.session.tried_action_classes.add(ActionClass.AUTH_DISCOVERY)
        prompts: list[str] = []
        loop._on_llm_response = (  # type: ignore[method-assign]
            lambda turn, raw, model_id, **kw: prompts.append(kw["prompt"])
        )
        loop.run()
        # Turn 1: clean prompt (no rejection yet).
        assert "STOP rejected on previous turn" not in prompts[0]
        # Turn 2: rejection note present (after turn 1's STOP got rejected).
        assert "STOP rejected on previous turn" in prompts[1]
        # Turn 3: rejection note gone (turn 2's GET cleared it).
        assert "STOP rejected on previous turn" not in prompts[2]
