"""Route-level tests for the SSE replay behavior added by the
server-side in-memory event history.

The dashboard must survive page reloads and let a second tab attach to
the same run, so the `/api/probe/stream` handler:

- reads `Last-Event-ID` from the request headers,
- forwards it to `runner.events(last_event_id=...)`,
- emits `id: <seq>` on every event frame.
"""
from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from earn_money import config


class _ReplayingFakeRunner:
    """Fake runner whose `events()` honours `last_event_id`.

    Used to verify the handler:
    1. Reads `Last-Event-ID` from the request headers.
    2. Forwards it as a kwarg to the runner.
    3. Writes `id: <seq>` on every SSE frame.
    """

    def __init__(self, history: list[dict], *_a, on_finished=None, **_kw):
        self._id = "fakerun123"
        self._history = history
        self._on_finished = on_finished
        self.events_called_with: list[int] = []

    def start(self) -> str:
        return self._id

    def run_id(self) -> str:
        return self._id

    def is_running(self) -> bool:
        return False

    def events(self, last_event_id: int = 0):
        self.events_called_with.append(last_event_id)
        for evt in self._history:
            if evt["seq"] > last_event_id:
                yield evt


@pytest.fixture()
def tmp_root(tmp_path: Path) -> Path:
    (tmp_path / "RECON_ENABLED").touch()
    return tmp_path


@pytest.fixture(autouse=True)
def _reset_probe_slot():
    from earn_money.dashboard import server
    server._PROBE_SLOT = None
    yield
    server._PROBE_SLOT = None


def _install_runner(runner) -> None:
    from earn_money.dashboard import server
    server._PROBE_SLOT = runner


def _drive_stream(
    handler_cls, run_id: str, *, last_event_id: str | None = None,
) -> bytes:
    """Drive `_serve_probe_stream` directly, returning the bytes written
    to the response body."""
    wfile = io.BytesIO()
    h = handler_cls.__new__(handler_cls)
    h.rfile = io.BytesIO(b"")
    h.wfile = wfile
    h.path = f"/api/probe/stream?run_id={run_id}"
    h.request_version = "HTTP/1.1"
    h.command = "GET"
    headers = {"Content-Length": "0"}
    if last_event_id is not None:
        headers["Last-Event-ID"] = last_event_id
    h.headers = MagicMock()
    h.headers.get = lambda k, default=None: headers.get(k, default)
    h.send_response = MagicMock()
    h.send_header = MagicMock()
    h.end_headers = MagicMock()
    h.send_error = MagicMock()
    h.log_error = MagicMock()
    h._serve_probe_stream()
    return wfile.getvalue()


@pytest.fixture()
def handler_cls(tmp_root: Path):
    from earn_money.dashboard import server
    paths = config.Paths.from_root(tmp_root)
    index_html = b"<!doctype html><title>t</title>"
    return server._make_handler(paths, index_html, {})


def _make_history() -> list[dict]:
    return [
        {"seq": 1, "event": "turn", "data": {"turn": 1, "stage": "action_pending"}},
        {"seq": 2, "event": "turn", "data": {"turn": 1, "stage": "action_parsed"}},
        {"seq": 3, "event": "turn", "data": {"turn": 2, "stage": "action_pending"}},
        {"seq": 4, "event": "done", "data": {"turns": 2, "stop_reason": "done"}},
    ]


class TestReplayOnFreshConnection:
    def test_fresh_subscriber_receives_full_history(self, handler_cls):
        runner = _ReplayingFakeRunner(_make_history())
        _install_runner(runner)
        body = _drive_stream(handler_cls, "fakerun123")
        # Fresh connection sends no Last-Event-ID → handler passes 0.
        assert runner.events_called_with == [0]
        # All four events should appear, in order.
        assert body.count(b"event: turn") == 3
        assert body.count(b"event: done") == 1

    def test_each_frame_carries_id_field_with_seq(self, handler_cls):
        runner = _ReplayingFakeRunner(_make_history())
        _install_runner(runner)
        body = _drive_stream(handler_cls, "fakerun123")
        # SSE spec: `id: <token>\n` before each event lets the browser
        # resume cleanly via Last-Event-ID on reconnect.
        assert b"id: 1\n" in body
        assert b"id: 2\n" in body
        assert b"id: 3\n" in body
        assert b"id: 4\n" in body


class TestLastEventIdResume:
    def test_handler_reads_last_event_id_header_and_forwards(self, handler_cls):
        runner = _ReplayingFakeRunner(_make_history())
        _install_runner(runner)
        _drive_stream(handler_cls, "fakerun123", last_event_id="2")
        assert runner.events_called_with == [2]

    def test_resume_skips_already_seen_events(self, handler_cls):
        runner = _ReplayingFakeRunner(_make_history())
        _install_runner(runner)
        body = _drive_stream(handler_cls, "fakerun123", last_event_id="2")
        # Only seq=3 (turn) and seq=4 (done) should reach the wire.
        assert b"id: 1\n" not in body
        assert b"id: 2\n" not in body
        assert b"id: 3\n" in body
        assert b"id: 4\n" in body

    def test_non_numeric_last_event_id_falls_back_to_zero(self, handler_cls):
        """A malformed Last-Event-ID must not crash the handler; treat
        it as a fresh subscriber."""
        runner = _ReplayingFakeRunner(_make_history())
        _install_runner(runner)
        body = _drive_stream(handler_cls, "fakerun123", last_event_id="not-a-number")
        assert runner.events_called_with == [0]
        assert b"id: 1\n" in body


class TestMultipleSubscribers:
    def test_two_consecutive_subscribers_each_get_full_history(self, handler_cls):
        runner = _ReplayingFakeRunner(_make_history())
        _install_runner(runner)
        body_a = _drive_stream(handler_cls, "fakerun123")
        body_b = _drive_stream(handler_cls, "fakerun123")
        # Each subscriber called events(0) — the handler does not "drain"
        # the history away from later subscribers.
        assert runner.events_called_with == [0, 0]
        assert body_a.count(b"event: done") == 1
        assert body_b.count(b"event: done") == 1
