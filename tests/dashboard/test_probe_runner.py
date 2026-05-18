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


class TestMetadataApi:
    """`runner.metadata()` exposes the same payload that the SSE `meta`
    event carries, so the `/api/probe/current` endpoint can answer
    "what is currently running?" without re-parsing the history."""

    def test_metadata_returns_meta_event_payload(self, make_runner):
        runner = make_runner([])
        m = runner.metadata()
        assert m["run_id"] == runner.run_id()
        assert m["base_url"] == "https://target.example.com"
        assert m["target_kind"] == "local_lab"
        assert m["max_turns"] == 10

    def test_metadata_includes_is_running_false_before_start(self, make_runner):
        runner = make_runner([])
        m = runner.metadata()
        assert m["is_running"] is False


def _grab_meta(runner) -> dict | None:
    """Snapshot the runner's history for the first `meta` event without
    blocking on a non-completed run. `iter_since` would otherwise hang
    until either a terminal event arrives or a keepalive fires."""
    for evt in runner._history.iter_since(0, keepalive_interval=0.01):
        if evt.get("event") == "_keepalive":
            return None
        if evt.get("event") == "meta":
            return evt
    return None


class TestRunMetadata:
    """The dashboard needs to display run config (base_url, target_kind,
    roe_path, max_turns, platform, program) so a page reload + replay
    shows the operator what's actually running. ProbeRunner emits a
    `meta` SSE event as the very first history entry at construction
    time — deterministically seq=1, replayed to every subscriber."""

    def test_meta_event_is_seq_1(self, make_runner):
        runner = make_runner([])
        snapshot = runner._history.snapshot_seqs()
        assert snapshot, "no events in history — meta was not emitted"
        assert snapshot[0] == 1

    def test_meta_event_carries_base_url_and_target_kind(self, make_runner):
        runner = make_runner([])
        meta = _grab_meta(runner)
        assert meta is not None
        assert meta["data"]["base_url"] == "https://target.example.com"
        assert meta["data"]["target_kind"] == "local_lab"

    def test_meta_event_carries_run_id_and_max_turns(self, make_runner):
        runner = make_runner([])
        meta = _grab_meta(runner)
        assert meta["data"]["run_id"] == runner.run_id()
        # max_turns is whatever the loaded profile says; the test RoE
        # fixture sets it to 10.
        assert meta["data"]["max_turns"] == 10

    def test_meta_event_carries_roe_profile_path(self, make_runner):
        runner = make_runner([])
        meta = _grab_meta(runner)
        assert meta["data"]["roe_profile"].endswith("test.yaml")


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


class TestBaseHostAugmentation:
    def test_local_lab_without_roe_adds_base_host(self):
        from earn_money.agent.roe_profile import RoeProfile, RoeSourceType
        from earn_money.dashboard.probe_runner import _augment_with_base_host

        profile = RoeProfile.safe_default()
        assert profile.allowed_hosts == []
        augmented = _augment_with_base_host(profile, "https://target.example.com:8443/x")
        assert augmented.allowed_hosts == ["target.example.com"]
        # source_type/ref preserved from safe_default
        assert augmented.source_type == RoeSourceType.MANUAL

    def test_augmentation_is_noop_when_host_already_present(self):
        from earn_money.agent.roe_profile import RoeProfile, RoeSourceType
        from earn_money.dashboard.probe_runner import _augment_with_base_host

        profile = RoeProfile(
            name="p", source_type=RoeSourceType.MANUAL,
            allowed_hosts=["target.example.com"],
        )
        out = _augment_with_base_host(profile, "https://target.example.com/")
        assert out is profile  # short-circuit, no rebuild


@pytest.fixture()
def make_runner(tmp_path, monkeypatch):
    """Build a real ProbeRunner instance without starting its thread.

    Returns a factory that accepts canned LLM-reply strings (in order)
    and optional profile overrides. The factory bypasses the real
    OpenRouter provider and resolves RoE paths under tmp_path/roe."""

    def _factory(replies: list[str | None], *, presolved: bool = True, **profile_overrides):
        from earn_money import config
        from earn_money.agent.action_classes import ActionClass
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
        runner = pr.ProbeRunner(
            base_url="https://target.example.com",
            roe_path=roe_yaml,
            paths=paths,
            target_kind="local_lab",
        )
        if presolved:
            # Pre-mark all probe classes as tried so single-STOP fixtures
            # are still valid under the new STOP-validation rule. Tests
            # that exercise STOP escalation pass `presolved=False`.
            runner.session.tried_action_classes = set(ActionClass)
        return runner

    return _factory


def _events_from(runner) -> list[dict]:
    """Drain the runner's history synchronously and return events.

    Equivalent to the old queue-drain helper, but reads through the
    EventHistory replay buffer. Skips the constructor-time `meta` event
    (seq=1) so per-turn assertions stay index-stable, and strips the
    seq id for backward-compat.
    """
    out: list[dict] = []
    for evt in runner._history.iter_since(0, keepalive_interval=0.01):
        if evt.get("event") == "_keepalive":
            break
        if evt.get("event") == "meta":
            continue
        out.append({"event": evt["event"], "data": evt["data"]})
        if evt["event"] in ("done", "probe_error"):
            break
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

    def test_events_yields_keepalive_when_idle(self, make_runner):
        runner = make_runner([_j(tool="stop", category="stop", args={})])
        # Shrink the keepalive interval so this test doesn't wait the
        # full production 15 s for the first _keepalive frame. The
        # runner hasn't been started — after the constructor's `meta`
        # event drains, the iterator should sit idle and emit
        # _keepalive within the configured interval.
        runner._EVENTS_GET_TIMEOUT_SECONDS = 0.01
        # Drain the meta event first; the *next* yield is the keepalive.
        gen = runner.events(last_event_id=runner._history.snapshot_seqs()[-1])
        evt = next(gen)
        assert evt["event"] == "_keepalive"
        assert evt["data"] == {}


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
