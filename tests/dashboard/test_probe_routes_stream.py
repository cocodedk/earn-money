"""GET /api/probe/stream — SSE replay route.

Client-disconnect resilience tests live in
test_probe_routes_stream_disconnect.py.
"""
from __future__ import annotations

import json

from ._probe_routes_helpers import _FakeRunner, _invoke_get


class TestStreamRoute:
    def test_returns_400_when_run_id_query_param_missing(self, handler_factory):
        handler_cls, _paths = handler_factory
        result = _invoke_get(handler_cls, "/api/probe/stream")
        assert result.status == 400

    def test_returns_404_when_no_probe_running(self, handler_factory):
        from earn_money.dashboard import server
        handler_cls, _paths = handler_factory
        server._PROBE_SLOT = None
        result = _invoke_get(handler_cls, "/api/probe/stream?run_id=fakerun123")
        assert result.status == 404

    def test_returns_410_when_run_id_does_not_match_active_runner(
        self, handler_factory,
    ):
        from earn_money.dashboard import server
        handler_cls, _paths = handler_factory
        server._PROBE_SLOT = _FakeRunner()
        result = _invoke_get(handler_cls, "/api/probe/stream?run_id=otherid")
        assert result.status == 410

    def test_emits_event_stream_content_type(self, handler_factory):
        from earn_money.dashboard import server
        handler_cls, _paths = handler_factory
        server._PROBE_SLOT = _FakeRunner()
        result = _invoke_get(handler_cls, "/api/probe/stream?run_id=fakerun123")
        headers = [c.args for c in result.handler.send_header.call_args_list]
        assert ("Content-Type", "text/event-stream; charset=utf-8") in headers

    def test_sends_retry_zero_header_frame(self, handler_factory):
        from earn_money.dashboard import server
        handler_cls, _paths = handler_factory
        server._PROBE_SLOT = _FakeRunner()
        result = _invoke_get(handler_cls, "/api/probe/stream?run_id=fakerun123")
        assert result.body.startswith(b"retry: 0\n\n")

    def test_frames_turn_event_correctly(self, handler_factory):
        from earn_money.dashboard import server
        handler_cls, _paths = handler_factory
        runner = _FakeRunner()
        turn_data = {"turn": 1, "stage": "action_pending"}
        done_data = {"turns": 1, "stop_reason": "done",
                     "candidates_count": 0, "verified_count": 0, "denials_count": 0}

        def events(last_event_id: int = 0):
            yield {"event": "turn", "data": turn_data}
            yield {"event": "done", "data": done_data}

        runner.events = events
        server._PROBE_SLOT = runner
        result = _invoke_get(handler_cls, "/api/probe/stream?run_id=fakerun123")
        expected = (
            b"event: turn\ndata: "
            + json.dumps(turn_data).encode()
            + b"\n\n"
        )
        assert expected in result.body

    def test_frames_finding_event_correctly(self, handler_factory):
        from earn_money.dashboard import server
        handler_cls, _paths = handler_factory
        runner = _FakeRunner()
        finding_data = {"turn": 1, "kind": "candidate", "type": "idor"}
        done_data = {"turns": 1, "stop_reason": "done",
                     "candidates_count": 1, "verified_count": 0, "denials_count": 0}

        def events(last_event_id: int = 0):
            yield {"event": "finding", "data": finding_data}
            yield {"event": "done", "data": done_data}

        runner.events = events
        server._PROBE_SLOT = runner
        result = _invoke_get(handler_cls, "/api/probe/stream?run_id=fakerun123")
        expected = (
            b"event: finding\ndata: "
            + json.dumps(finding_data).encode()
            + b"\n\n"
        )
        assert expected in result.body

    def test_closes_response_after_done(self, handler_factory):
        from earn_money.dashboard import server
        handler_cls, _paths = handler_factory
        runner = _FakeRunner()
        done_data = {"turns": 0, "stop_reason": "done",
                     "candidates_count": 0, "verified_count": 0, "denials_count": 0}
        turn_data = {"turn": 1, "stage": "action_pending"}

        def events(last_event_id: int = 0):
            yield {"event": "done", "data": done_data}
            yield {"event": "turn", "data": turn_data}

        runner.events = events
        server._PROBE_SLOT = runner
        result = _invoke_get(handler_cls, "/api/probe/stream?run_id=fakerun123")
        done_frame = (
            b"event: done\ndata: " + json.dumps(done_data).encode() + b"\n\n"
        )
        turn_frame = (
            b"event: turn\ndata: " + json.dumps(turn_data).encode() + b"\n\n"
        )
        assert done_frame in result.body
        assert turn_frame not in result.body

    def test_closes_response_after_probe_error(self, handler_factory):
        from earn_money.dashboard import server
        handler_cls, _paths = handler_factory
        runner = _FakeRunner()
        error_data = {"message": "something bad", "stage": "action"}
        turn_data = {"turn": 1, "stage": "action_pending"}

        def events(last_event_id: int = 0):
            yield {"event": "probe_error", "data": error_data}
            yield {"event": "turn", "data": turn_data}

        runner.events = events
        server._PROBE_SLOT = runner
        result = _invoke_get(handler_cls, "/api/probe/stream?run_id=fakerun123")
        error_frame = (
            b"event: probe_error\ndata: "
            + json.dumps(error_data).encode()
            + b"\n\n"
        )
        turn_frame = (
            b"event: turn\ndata: " + json.dumps(turn_data).encode() + b"\n\n"
        )
        assert error_frame in result.body
        assert turn_frame not in result.body

    def test_keepalive_yields_comment_frame(self, handler_factory):
        from earn_money.dashboard import server
        handler_cls, _paths = handler_factory
        runner = _FakeRunner()
        done_data = {"turns": 0, "stop_reason": "done",
                     "candidates_count": 0, "verified_count": 0, "denials_count": 0}

        def events(last_event_id: int = 0):
            yield {"event": "_keepalive", "data": {}}
            yield {"event": "done", "data": done_data}

        runner.events = events
        server._PROBE_SLOT = runner
        result = _invoke_get(handler_cls, "/api/probe/stream?run_id=fakerun123")
        assert b":\n\n" in result.body

