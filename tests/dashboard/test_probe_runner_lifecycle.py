"""ProbeRunner lifecycle + cancellation + events()-iterator tests."""
from __future__ import annotations

import re

import pytest

from ._probe_runner_test_helpers import _j


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
