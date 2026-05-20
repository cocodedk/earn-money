"""ProbeRunner SSE-event emission tests (turn stages, done, prompt body)."""
from __future__ import annotations

from unittest.mock import patch

from ._probe_runner_test_helpers import _events_from, _j


class TestEventEmission:
    def test_emits_action_pending_before_parse(self, make_runner):
        runner = make_runner([_j(tool="stop", category="stop", args={})])
        runner.run()
        names = [(e["data"].get("stage"), e["event"]) for e in _events_from(runner)]
        # First emitted turn-stage must be action_pending.
        first_action = next(
            (s for s, ev in names if ev == "turn" and s == "action_pending"), None,
        )
        assert first_action == "action_pending"

    def test_emits_action_parsed_after_parse(self, make_runner):
        runner = make_runner([_j(tool="stop", category="stop", args={})])
        runner.run()
        stages = [e["data"].get("stage") for e in _events_from(runner) if e["event"] == "turn"]
        # action_pending must come before action_parsed in the same turn.
        assert "action_parsed" in stages
        assert stages.index("action_pending") < stages.index("action_parsed")

    def test_action_parsed_carries_parse_recovered_true_when_fenced(self, make_runner):
        fenced = "```json\n" + _j(tool="stop", category="stop", args={}) + "\n```"
        runner = make_runner([fenced])
        runner.run()
        parsed = [e["data"] for e in _events_from(runner)
                  if e["event"] == "turn" and e["data"].get("stage") == "action_parsed"]
        assert parsed and parsed[0]["parse_recovered"] is True

    def test_action_parsed_carries_parse_recovered_false_on_clean_json(self, make_runner):
        runner = make_runner([_j(tool="stop", category="stop", args={})])
        runner.run()
        parsed = [e["data"] for e in _events_from(runner)
                  if e["event"] == "turn" and e["data"].get("stage") == "action_parsed"]
        assert parsed and parsed[0]["parse_recovered"] is False

    def test_emits_done_with_summary_on_natural_exit(self, make_runner):
        runner = make_runner([_j(tool="stop", category="stop", args={"reason": "done"})])
        runner._run_safe()
        done = [e["data"] for e in _events_from(runner) if e["event"] == "done"]
        assert done and done[0]["stop_reason"] == "done"
        assert "turns" in done[0]
        assert "candidates_count" in done[0]

    def test_emits_done_with_operator_cancel_when_stopped(self, make_runner):
        from earn_money.dashboard.probe_runner import _StopRequested
        runner = make_runner(replies=[_j(tool="stop", category="stop", args={})])
        # Force _StopRequested to bubble out of run() by mocking the
        # base loop. _run_safe must convert it into a done event with
        # stop_reason=operator_cancel and the full summary payload.
        with patch.object(runner, "run", side_effect=_StopRequested()):
            runner._run_safe()
        done = [e["data"] for e in _events_from(runner) if e["event"] == "done"]
        assert done
        assert done[0]["stop_reason"] == "operator_cancel"
        for k in ("turns", "candidates_count", "verified_count", "denials_count"):
            assert k in done[0]

    def test_emits_probe_error_when_loop_crashes(self, make_runner):
        runner = make_runner(replies=[_j(tool="stop", category="stop", args={})])
        with patch.object(runner, "run", side_effect=RuntimeError("boom")):
            runner._run_safe()
        errs = [e["data"] for e in _events_from(runner) if e["event"] == "probe_error"]
        assert errs and "boom" in errs[0]["message"]
        assert errs[0]["stage"] == "runtime"

    def test_finding_event_protects_trusted_fields(self, make_runner):
        runner = make_runner(replies=[_j(tool="stop", category="stop", args={})])
        # Hostile verifier payload tries to overwrite turn / kind.
        runner._on_finding(turn=7, kind="candidate",
                           finding={"type": "idor", "turn": "BAD", "kind": "BAD"})
        evt = _events_from(runner)[-1]
        assert evt["event"] == "finding"
        assert evt["data"]["turn"] == 7
        assert evt["data"]["kind"] == "candidate"

    def test_retries_without_response_format_when_first_provider_call_fails(
        self, make_runner,
    ):
        """Pin the response_format retry behaviour: first call sends
        `response_format={"type": "json_object"}`; if the provider
        returns HTTP 400 (the model adapter rejecting the kwarg), the
        second call must omit it and succeed. One bad model must not
        kill the whole run.

        Auth/credit/rate-limit errors (401/402/429) are NOT fixable by
        dropping the kwarg and have their own no-retry tests in
        test_hacker_loop.py::TestProviderHelper."""
        from earn_money.agent.providers_openai_compat import ProviderError
        runner = make_runner(replies=[])  # we wire side_effect manually below
        runner.provider.complete.side_effect = [
            ProviderError("response_format unsupported", status_code=400),
            _j(tool="stop", category="stop", args={"reason": "done"}),
        ]
        result = runner.run()
        assert result.stop_reason == "done"
        calls = runner.provider.complete.call_args_list
        assert len(calls) == 2
        assert calls[0].kwargs.get("response_format") == {"type": "json_object"}
        assert "response_format" not in calls[1].kwargs


class TestPromptInSseEvent:
    def test_action_pending_event_includes_full_prompt_system_and_long_raw(self, make_runner):
        full_raw = '{"tool":"stop","category":"stop","args":{"reason":"' + "x" * 250 + '"}}'
        runner = make_runner([full_raw])
        runner.run()
        d = next(e["data"] for e in _events_from(runner)
                 if e["data"].get("stage") == "action_pending")
        assert d["prompt"]
        assert d["system"]
        assert d["raw"] == full_raw
        assert d["raw_excerpt"] == full_raw[:200]
        assert len(d["raw"]) > len(d["raw_excerpt"])
        assert d["attempt"] == 1
        assert d["used_response_format"] is True

    def test_action_pending_event_emitted_twice_when_retry_fires(self, make_runner):
        runner = make_runner(["{", _j(tool="stop", category="stop", args={"reason": "done"})])
        runner.run()
        pending = [e["data"] for e in _events_from(runner)
                   if e["data"].get("stage") == "action_pending"]
        assert len(pending) == 2
        assert pending[0]["attempt"] == 1
        assert pending[0]["used_response_format"] is True
        assert pending[1]["attempt"] == 2
        assert pending[1]["used_response_format"] is False

    def test_action_pending_carries_used_rf_false_when_provider_rejects_rf(self, make_runner):
        runner = make_runner(replies=[])
        runner.provider.complete.side_effect = [
            RuntimeError("response_format unsupported"),
            _j(tool="stop", category="stop", args={"reason": "done"}),
        ]
        runner.run()
        pending = [e["data"] for e in _events_from(runner)
                   if e["data"].get("stage") == "action_pending"]
        assert len(pending) == 1
        assert pending[0]["attempt"] == 1
        assert pending[0]["used_response_format"] is False

    def test_raw_excerpt_still_present_for_backcompat(self, make_runner):
        runner = make_runner([_j(tool="stop", category="stop", args={"reason": "done"})])
        runner.run()
        d = next(e["data"] for e in _events_from(runner)
                 if e["data"].get("stage") == "action_pending")
        assert "raw_excerpt" in d
        assert len(d["raw_excerpt"]) <= 200


class TestAttemptIdentityInSseEvent:
    def test_action_parsed_event_carries_attempt(self, make_runner):
        runner = make_runner([_j(tool="stop", category="stop", args={"reason": "done"})])
        runner.run()
        e = next(ev for ev in _events_from(runner)
                 if ev["data"].get("stage") == "action_parsed")
        assert e["data"]["attempt"] == 1

    def test_action_parsed_event_carries_attempt_2_after_retry(self, make_runner):
        runner = make_runner(["{", _j(tool="stop", category="stop", args={"reason": "done"})])
        runner.run()
        e = next(ev for ev in _events_from(runner)
                 if ev["data"].get("stage") == "action_parsed")
        assert e["data"]["attempt"] == 2

    def test_action_parse_failed_event_emitted_on_first_failure(self, make_runner):
        runner = make_runner(["{", _j(tool="stop", category="stop", args={"reason": "done"})])
        runner.run()
        f = next(ev for ev in _events_from(runner)
                 if ev["data"].get("stage") == "action_parse_failed")
        assert f["data"]["attempt"] == 1
        assert f["data"]["error"]
        assert f["data"]["turn"] == 1

    def test_action_parse_failed_event_not_emitted_on_happy_path(self, make_runner):
        runner = make_runner([_j(tool="stop", category="stop", args={"reason": "done"})])
        runner.run()
        assert not any(ev["data"].get("stage") == "action_parse_failed"
                       for ev in _events_from(runner))
