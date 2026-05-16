"""Tests for ProbeRunner — the dashboard's threaded HackerLoop subclass."""
from __future__ import annotations

import json
import re
from unittest.mock import MagicMock, patch

import pytest

from earn_money.agent.observations import ObservationWrapper
from earn_money.agent.task_router import TaskType


def _runner_with_session(observations: list[ObservationWrapper] | None = None):
    """Build a ProbeRunner without actually starting its thread."""
    from earn_money.dashboard.probe_runner import ProbeRunner

    # Construct via factory that bypasses provider env (patched).
    runner = MagicMock(spec=ProbeRunner)
    runner._next_task_hint = None
    runner.session = MagicMock()
    runner.session.observations = observations or []
    # Bind the real _pick_task method to the mock.
    runner._pick_task = ProbeRunner._pick_task.__get__(runner, ProbeRunner)
    return runner


class TestPickTask:
    def test_no_observations_picks_agent_planning(self):
        r = _runner_with_session([])
        assert r._pick_task() == TaskType.AGENT_PLANNING

    def test_javascript_content_type_picks_coding_security(self):
        obs = ObservationWrapper.from_response(
            200, "https://t/x", {"content-type": "application/javascript"}, "var x=1;",
        )
        r = _runner_with_session([obs])
        assert r._pick_task() == TaskType.CODING_SECURITY

    def test_html_with_script_picks_coding_security(self):
        obs = ObservationWrapper.from_response(
            200, "https://t/x", {"content-type": "text/html"}, "<html><script>1</script></html>",
        )
        r = _runner_with_session([obs])
        assert r._pick_task() == TaskType.CODING_SECURITY

    def test_html_without_script_picks_agent_planning(self):
        obs = ObservationWrapper.from_response(
            200, "https://t/x", {"content-type": "text/html"}, "<html><body>hi</body></html>",
        )
        r = _runner_with_session([obs])
        assert r._pick_task() == TaskType.AGENT_PLANNING

    def test_json_content_type_picks_agent_planning(self):
        obs = ObservationWrapper.from_response(
            200, "https://t/x", {"content-type": "application/json"}, "{}",
        )
        r = _runner_with_session([obs])
        assert r._pick_task() == TaskType.AGENT_PLANNING

    def test_report_candidate_hint_picks_structured_extraction(self):
        r = _runner_with_session([])
        r._next_task_hint = TaskType.STRUCTURED_EXTRACTION
        assert r._pick_task() == TaskType.STRUCTURED_EXTRACTION

    def test_hint_is_consumed_after_one_use(self, make_runner):
        runner = make_runner([_j(tool="stop", category="stop", args={})])
        # Simulate a ReportCandidateAction having just been processed.
        runner._next_task_hint = TaskType.STRUCTURED_EXTRACTION
        assert runner._pick_task() == TaskType.STRUCTURED_EXTRACTION
        # Trigger the _on_turn_complete branch that clears the hint.
        from earn_money.agent.probe_actions import StopAction
        runner._on_turn_complete(2, StopAction(tool="stop", category="stop"), "completed")
        assert runner._next_task_hint is None


@pytest.fixture()
def make_runner(tmp_path, monkeypatch):
    """Build a real ProbeRunner instance without starting its thread.

    Returns a factory that accepts canned LLM-reply strings (in order)
    and optional profile overrides. The factory bypasses the real
    OpenRouter provider and resolves RoE paths under tmp_path/roe."""

    def _factory(replies: list[str | None], **profile_overrides):
        from earn_money import config
        from earn_money.dashboard import probe_runner as pr

        (tmp_path / "RECON_ENABLED").touch()
        roe_dir = tmp_path / "roe"
        roe_dir.mkdir(exist_ok=True)
        roe_yaml = roe_dir / "test.yaml"
        roe_yaml.write_text(
            "name: test\n"
            "allowed_hosts: [target.example.com]\n"
            "max_requests: 100\nmax_posts: 20\nmax_turns: 10\n"
            "max_runtime_seconds: 60\nmax_response_bytes: 5000\n"
            "delay_between_requests_ms: 0\n"
            "allow_get: true\nallow_post: true\nallow_idor_checks: true\n"
        )

        provider = MagicMock()
        iter_replies = iter(replies)
        provider.complete.side_effect = lambda **_kw: next(iter_replies)
        monkeypatch.setattr(
            "earn_money.dashboard.probe_runner.providers_mod.from_env",
            lambda: provider,
        )

        paths = config.Paths.from_root(tmp_path)
        return pr.ProbeRunner(
            base_url="https://target.example.com",
            roe_path=roe_yaml,
            paths=paths,
        )

    return _factory


def _events_from(runner) -> list[dict]:
    """Drain runner._queue synchronously and return events as a list."""
    out: list[dict] = []
    while not runner._queue.empty():
        out.append(runner._queue.get_nowait())
    return out


def _j(**kwargs) -> str:
    return json.dumps(kwargs)


class TestLifecycle:
    def test_run_id_is_uuid4_hex(self, make_runner):
        runner = make_runner([_j(tool="stop", category="stop", args={})])
        assert re.fullmatch(r"[0-9a-f]{32}", runner.run_id())

    def test_is_running_false_before_start(self, make_runner):
        runner = make_runner([_j(tool="stop", category="stop", args={})])
        assert runner.is_running() is False

    def test_double_start_raises_already_running(self, make_runner):
        from earn_money.dashboard.probe_runner import AlreadyRunning
        runner = make_runner([_j(tool="stop", category="stop", args={})])
        runner.start()
        with pytest.raises(AlreadyRunning):
            runner.start()
        # let the loop thread settle so it doesn't bleed into the next test
        if runner._thread is not None:
            runner._thread.join(timeout=2.0)

    def test_run_safe_does_not_call_on_finished(self, make_runner):
        """Regression: a fast run must NOT clear the server slot in
        `finally`. The slot has to outlive the runner thread so a
        late-arriving EventSource can still drain the terminal event.
        Verify by asserting on_finished is never invoked."""
        seen: list[str] = []
        runner = make_runner([_j(tool="stop", category="stop", args={})])
        runner._on_finished = lambda run_id: seen.append(run_id)
        runner._run_safe()
        assert seen == [], "_on_finished must not be called from _run_safe"

    def test_terminal_event_survives_after_thread_exit(self, make_runner):
        """Regression: emit a `done` from within _run_safe (synchronous,
        on the test thread). Then drain events() — the `done` must still
        be available even though is_running() is False."""
        runner = make_runner([_j(tool="stop", category="stop", args={"reason": "done"})])
        runner._run_safe()
        # _run_safe has returned; thread (had there been one) would be dead.
        runner._thread = None  # mimic post-thread-exit state
        runner._EVENTS_GET_TIMEOUT_SECONDS = 0.01
        drained = list(runner.events())
        # events() must yield the buffered done before returning.
        assert any(e["event"] == "done" for e in drained)


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
        raises, the second call must omit the kwarg and succeed. One
        bad model must not kill the whole run."""
        runner = make_runner(replies=[])  # we wire side_effect manually below
        runner.provider.complete.side_effect = [
            RuntimeError("response_format unsupported"),
            _j(tool="stop", category="stop", args={"reason": "done"}),
        ]
        result = runner.run()
        assert result.stop_reason == "done"
        calls = runner.provider.complete.call_args_list
        assert len(calls) == 2
        assert calls[0].kwargs.get("response_format") == {"type": "json_object"}
        assert "response_format" not in calls[1].kwargs


class TestStop:
    def test_stop_sets_event_flag(self, make_runner):
        runner = make_runner([_j(tool="stop", category="stop", args={})])
        runner.stop()
        assert runner._stop_event.is_set()

    def test_stop_causes_next_turn_complete_to_raise(self, make_runner):
        from earn_money.agent.probe_actions import StopAction
        from earn_money.dashboard.probe_runner import _StopRequested
        runner = make_runner([_j(tool="stop", category="stop", args={})])
        runner._stop_event.set()
        with pytest.raises(_StopRequested):
            runner._on_turn_complete(1, StopAction(tool="stop", category="stop"), "completed")


class TestEvents:
    def test_events_returns_after_done_event(self, make_runner):
        runner = make_runner([_j(tool="stop", category="stop", args={})])
        runner._emit("done", {"turns": 1, "stop_reason": "done",
                              "candidates_count": 0, "verified_count": 0,
                              "denials_count": 0})
        produced = []
        for evt in runner.events():
            produced.append(evt)
            if len(produced) >= 5:
                break  # guard against infinite loop
        assert produced[-1]["event"] == "done"

    def test_events_yields_keepalive_on_queue_idle(self, make_runner):
        runner = make_runner([_j(tool="stop", category="stop", args={})])
        # Shrink the get-timeout so this test doesn't wait the full
        # production 15 s for the first _keepalive frame.
        runner._EVENTS_GET_TIMEOUT_SECONDS = 0.01
        # Mark the runner as "still running" so the queue-empty branch
        # yields _keepalive instead of returning.
        runner._thread = MagicMock()
        runner._thread.is_alive = lambda: True
        gen = runner.events()
        evt = next(gen)
        assert evt == {"event": "_keepalive", "data": {}}
