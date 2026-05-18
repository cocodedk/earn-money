"""do_GET / do_POST dispatcher + GET /api/probe/current discovery tests."""
from __future__ import annotations

import json

from ._probe_routes_helpers import _drive_dispatch, _FakeRunner


class TestDispatcher:
    """Test that do_GET and do_POST correctly dispatch to route handlers."""

    def test_do_post_dispatches_probe_start(self, handler_factory):
        handler_cls, _paths = handler_factory
        body = json.dumps({
            "base_url": "https://target.example.com",
            "target_kind": "local_lab",
        }).encode("utf-8")
        status, response_body, _h = _drive_dispatch(
            handler_cls, "POST", "/api/probe/start", raw_body=body,
        )
        assert status == 200
        assert b"fakerun123" in response_body

    def test_do_get_dispatches_probe_stream(self, handler_factory):
        from earn_money.dashboard import server
        handler_cls, _paths = handler_factory
        server._PROBE_SLOT = _FakeRunner()
        status, response_body, _h = _drive_dispatch(
            handler_cls, "GET", "/api/probe/stream?run_id=fakerun123",
        )
        assert status == 200
        assert b"event: done" in response_body

    def test_do_post_unknown_path_returns_404(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, _response_body, _h = _drive_dispatch(
            handler_cls, "POST", "/api/does-not-exist", raw_body=b"{}",
        )
        assert status == 404


class TestProbeCurrentRoute:
    """`GET /api/probe/current` lets the dashboard discover an active
    probe without the operator knowing the run_id. Returns 404 when
    there is no slot, 200 with metadata when there is."""

    class _CurrentFake:
        def __init__(self, *, running: bool = True) -> None:
            self._running = running

        def run_id(self) -> str:
            return "currentfake1"

        def is_running(self) -> bool:
            return self._running

        def metadata(self) -> dict:
            return {
                "run_id": "currentfake1",
                "base_url": "https://target.example.com",
                "target_kind": "local_lab",
                "platform": "local",
                "program": None,
                "roe_profile": "/tmp/test.yaml",
                "max_turns": 75,
                "is_running": self._running,
            }

    def test_returns_404_when_no_slot(self, handler_factory):
        handler_cls, _ = handler_factory
        from earn_money.dashboard import server
        server._PROBE_SLOT = None
        status, _body, _h = _drive_dispatch(
            handler_cls, "GET", "/api/probe/current",
        )
        assert status == 404

    def test_returns_200_with_metadata_when_running(self, handler_factory):
        handler_cls, _ = handler_factory
        from earn_money.dashboard import server
        server._PROBE_SLOT = self._CurrentFake(running=True)
        status, body_bytes, _h = _drive_dispatch(
            handler_cls, "GET", "/api/probe/current",
        )
        assert status == 200
        payload = json.loads(body_bytes.split(b"\r\n\r\n", 1)[-1])
        assert payload["run_id"] == "currentfake1"
        assert payload["base_url"] == "https://target.example.com"
        assert payload["is_running"] is True
        assert payload["max_turns"] == 75

    def test_returns_200_for_completed_slot(self, handler_factory):
        """Slot persists after the run finishes so a late subscriber
        can still replay the trace; the endpoint reports is_running
        false in that case."""
        handler_cls, _ = handler_factory
        from earn_money.dashboard import server
        server._PROBE_SLOT = self._CurrentFake(running=False)
        status, body_bytes, _h = _drive_dispatch(
            handler_cls, "GET", "/api/probe/current",
        )
        assert status == 200
        payload = json.loads(body_bytes.split(b"\r\n\r\n", 1)[-1])
        assert payload["is_running"] is False
