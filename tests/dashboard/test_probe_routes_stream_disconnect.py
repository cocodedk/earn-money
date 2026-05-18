"""GET /api/probe/stream — client-disconnect / BrokenPipe resilience."""
from __future__ import annotations

import io

from ._probe_routes_helpers import _FakeRunner, _invoke_get


class TestStreamRouteDisconnect:
    def test_client_disconnect_mid_stream_does_not_kill_runner(
        self, handler_factory,
    ):
        from earn_money.dashboard import server
        handler_cls, _paths = handler_factory
        runner = _FakeRunner()
        done_data = {"turns": 0, "stop_reason": "done",
                     "candidates_count": 0, "verified_count": 0, "denials_count": 0}

        def events(last_event_id: int = 0):
            yield {"event": "turn", "data": {"turn": 1}}
            yield {"event": "done", "data": done_data}

        runner.events = events
        server._PROBE_SLOT = runner

        class FailingBytesIO(io.BytesIO):
            _call_count = 0

            def write(self, data):
                self._call_count += 1
                if self._call_count >= 2:
                    raise BrokenPipeError("client gone")
                return super().write(data)

            def flush(self):
                pass

        fake_wfile = FailingBytesIO()
        _invoke_get(handler_cls, "/api/probe/stream?run_id=fakerun123",
                    wfile=fake_wfile)
        assert server._PROBE_SLOT is runner

    def test_client_disconnect_on_first_write_does_not_kill_runner(
        self, handler_factory,
    ):
        from earn_money.dashboard import server
        handler_cls, _paths = handler_factory
        runner = _FakeRunner()
        server._PROBE_SLOT = runner

        class FailingBytesIO(io.BytesIO):
            _call_count = 0

            def write(self, data):
                self._call_count += 1
                if self._call_count >= 1:
                    raise BrokenPipeError("client gone on first write")
                return super().write(data)

            def flush(self):
                pass

        fake_wfile = FailingBytesIO()
        _invoke_get(handler_cls, "/api/probe/stream?run_id=fakerun123",
                    wfile=fake_wfile)
        assert server._PROBE_SLOT is runner
