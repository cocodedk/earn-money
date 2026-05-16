"""Tests for POST /api/probe/start and GET /api/probe/stream."""
from __future__ import annotations

import io
import json
from pathlib import Path
from typing import NamedTuple
from unittest.mock import MagicMock, patch

import pytest

from earn_money import config, flags


class _FakeRunner:
    """Test double for ProbeRunner — same surface, no thread, no provider."""

    def __init__(self, *_args, on_finished=None, **_kwargs):
        self._id = "fakerun123"
        self._running = True
        self._on_finished = on_finished

    def start(self) -> str:
        return self._id

    def run_id(self) -> str:
        return self._id

    def is_running(self) -> bool:
        return self._running

    def events(self):
        yield {
            "event": "done",
            "data": {
                "turns": 0,
                "stop_reason": "done",
                "candidates_count": 0,
                "verified_count": 0,
                "denials_count": 0,
            },
        }


@pytest.fixture()
def tmp_root(tmp_path: Path) -> Path:
    (tmp_path / "RECON_ENABLED").touch()
    return tmp_path


@pytest.fixture(autouse=True)
def _reset_probe_slot():
    """Ensure no probe slot leaks between tests. The handler installs
    a _FakeRunner under server._PROBE_SLOT on a successful start; without
    this fixture a subsequent test would see a stale 409 from a slot the
    previous test left in place."""
    from earn_money.dashboard import server
    server._PROBE_SLOT = None
    yield
    server._PROBE_SLOT = None


@pytest.fixture()
def handler_factory(tmp_root: Path):
    from earn_money.dashboard import server
    paths = config.Paths.from_root(tmp_root)
    # Patch ProbeRunner in the server module to our fake.
    with patch.object(server, "ProbeRunner", _FakeRunner, create=True):
        index_html = b"<!doctype html><title>t</title>"
        static = {}
        yield server._make_handler(paths, index_html, static), paths


def _drive(
    handler_cls, method: str, path: str, *, raw_body: bytes = b""
) -> tuple[int, dict]:
    """Drive a route method on the handler class without sockets.

    `_serve_probe_start` reads exactly `Content-Length` bytes from
    `self.rfile`. The rfile here therefore contains **only the body
    bytes** — not a full HTTP request line + headers. (An earlier
    version of this shim prepended fake request headers; that put the
    handler's read at byte 0 of the header line and silently 400'd
    every test.)"""
    import io

    wfile = io.BytesIO()
    h = handler_cls.__new__(handler_cls)
    h.rfile = io.BytesIO(raw_body)
    h.wfile = wfile
    h.command = method
    h.path = path
    h.request_version = "HTTP/1.1"
    h.headers = MagicMock()
    h.headers.get = lambda k, default=None: {
        "Content-Length": str(len(raw_body)),
        "Content-Type": "application/json",
    }.get(k, default)
    h.send_response = MagicMock()
    h.send_header = MagicMock()
    h.end_headers = MagicMock()
    h.send_error = MagicMock()
    if method == "POST" and path == "/api/probe/start":
        h._serve_probe_start()
    elif method == "GET" and path.split("?", 1)[0] == "/api/probe/stream":
        h._serve_probe_stream()
    else:
        raise ValueError(f"shim doesn't know route {method} {path}")
    status = (
        h.send_response.call_args.args[0]
        if h.send_response.call_args
        else (h.send_error.call_args.args[0] if h.send_error.call_args else 0)
    )
    body_bytes = wfile.getvalue()
    try:
        body_json = json.loads(body_bytes.split(b"\r\n\r\n", 1)[-1] or b"{}")
    except json.JSONDecodeError:
        body_json = {"_raw": body_bytes.decode("utf-8", errors="replace")}
    return status, body_json


def _invoke_post(handler_cls, path: str, body: dict) -> tuple[int, dict]:
    """Convenience: JSON-encode `body` and drive POST."""
    return _drive(
        handler_cls, "POST", path, raw_body=json.dumps(body).encode("utf-8")
    )


def _drive_dispatch(
    handler_cls, method: str, path: str, *, raw_body: bytes = b""
) -> tuple[int, bytes, object]:
    """Drive do_GET or do_POST dispatcher directly (not route methods).

    Returns (status, body, handler) so tests can inspect handler state.
    Stubs send_response, send_header, end_headers, send_error, log_error."""
    wfile = io.BytesIO()
    h = handler_cls.__new__(handler_cls)
    h.rfile = io.BytesIO(raw_body)
    h.wfile = wfile
    h.command = method
    h.path = path
    h.request_version = "HTTP/1.1"
    h.headers = MagicMock()
    h.headers.get = lambda k, default=None: {
        "Content-Length": str(len(raw_body)),
        "Content-Type": "application/json",
    }.get(k, default)
    h.send_response = MagicMock()
    h.send_header = MagicMock()
    h.end_headers = MagicMock()
    h.send_error = MagicMock()
    h.log_error = MagicMock()
    if method == "GET":
        h.do_GET()
    elif method == "POST":
        h.do_POST()
    else:
        raise ValueError(f"unknown method {method}")
    status = (
        h.send_response.call_args.args[0]
        if h.send_response.call_args
        else (h.send_error.call_args.args[0] if h.send_error.call_args else 0)
    )
    body_bytes = wfile.getvalue()
    return status, body_bytes, h


def _invoke_post_raw(handler_cls, path: str, raw: bytes) -> tuple[int, dict]:
    """Convenience: drive POST with arbitrary bytes (malformed-JSON tests)."""
    return _drive(handler_cls, "POST", path, raw_body=raw)


_BASE = "https://target.example.com"


class TestStartRoute:
    def test_returns_200_with_run_id_on_success(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab"},
        )
        assert status == 200
        assert body == {"run_id": "fakerun123"}

    def test_returns_400_when_base_url_missing(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post(
            handler_cls, "/api/probe/start", {"target_kind": "local_lab"}
        )
        assert status == 400
        assert "base_url required" in body["error"]

    def test_returns_400_when_body_is_invalid_json(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post_raw(
            handler_cls, "/api/probe/start", b"{not-json"
        )
        assert status == 400
        assert "invalid JSON body" in body["error"]

    def test_returns_400_when_roe_profile_path_does_not_exist(
        self, handler_factory
    ):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab", "roe_profile": "/nope.yaml"},
        )
        assert status == 400
        assert "RoE profile not found" in body["error"]

    def test_returns_400_when_base_url_scheme_not_http(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": "ftp://x.com", "target_kind": "local_lab"},
        )
        assert status == 400
        assert "scheme" in body["error"]

    def test_returns_400_when_base_url_has_userinfo(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": "https://u:p@x.com", "target_kind": "local_lab"},
        )
        assert status == 400
        assert "userinfo" in body["error"]

    def test_returns_400_when_base_url_missing_host(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": "https://", "target_kind": "local_lab"},
        )
        assert status == 400
        assert "missing host" in body["error"]

    def test_returns_400_when_base_url_is_localhost(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": "http://localhost", "target_kind": "local_lab"},
        )
        assert status == 400
        assert "loopback" in body["error"]

    def test_returns_400_when_base_url_is_loopback_ip(self, handler_factory):
        handler_cls, _paths = handler_factory
        for url in ("http://127.0.0.1", "http://[::1]"):
            status, body = _invoke_post(
                handler_cls,
                "/api/probe/start",
                {"base_url": url, "target_kind": "local_lab"},
            )
            assert status == 400, f"expected 400 for {url}, got {status}"
            assert "private/reserved" in body["error"] or "loopback" in body["error"]

    def test_returns_400_when_base_url_is_imds(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": "http://169.254.169.254", "target_kind": "local_lab"},
        )
        assert status == 400
        assert "private/reserved" in body["error"]

    def test_returns_400_when_base_url_is_private_v4(self, handler_factory):
        handler_cls, _paths = handler_factory
        for ip in ("10.0.0.5", "172.16.0.1", "192.168.1.1"):
            status, body = _invoke_post(
                handler_cls,
                "/api/probe/start",
                {"base_url": f"http://{ip}", "target_kind": "local_lab"},
            )
            assert status == 400, f"expected 400 for {ip}, got {status}"
            assert "private/reserved" in body["error"]

    def test_returns_400_when_base_url_is_unspecified(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, _body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": "http://0.0.0.0", "target_kind": "local_lab"},
        )
        assert status == 400

    def test_hostname_that_resolves_locally_passes_route_check(
        self, handler_factory
    ):
        handler_cls, _paths = handler_factory
        status, _body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": "http://target.cocode.dk", "target_kind": "local_lab"},
        )
        assert status == 200

    def test_returns_400_when_max_turns_out_of_range(self, handler_factory):
        handler_cls, _paths = handler_factory
        for bad in (0, 51):
            status, body = _invoke_post(
                handler_cls,
                "/api/probe/start",
                {"base_url": _BASE, "target_kind": "local_lab", "max_turns": bad},
            )
            assert status == 400, f"expected 400 for max_turns={bad}"
            assert "max_turns" in body["error"]

    def test_returns_400_when_max_turns_is_true(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, _body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab", "max_turns": True},
        )
        assert status == 400

    def test_returns_400_when_max_turns_is_false(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, _body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab", "max_turns": False},
        )
        assert status == 400

    def test_returns_400_when_max_turns_is_string(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, _body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab", "max_turns": "10"},
        )
        assert status == 400

    def test_returns_400_when_max_turns_is_float(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, _body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab", "max_turns": 10.5},
        )
        assert status == 400

    def test_empty_string_roe_profile_treated_as_null(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, _body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab", "roe_profile": ""},
        )
        assert status == 200

    def test_relative_roe_path_resolved_against_root(
        self, handler_factory, tmp_root: Path
    ):
        handler_cls, _paths = handler_factory
        roe_dir = tmp_root / "roe"
        roe_dir.mkdir()
        (roe_dir / "test.yaml").write_text("# dummy roe", encoding="utf-8")
        status, _body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {
                "base_url": _BASE,
                "target_kind": "local_lab",
                "roe_profile": "roe/test.yaml",
            },
        )
        assert status == 200

    def test_empty_platform_defaults_to_local(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, _body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab", "platform": ""},
        )
        assert status == 200

    def test_null_platform_defaults_to_local(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, _body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab", "platform": None},
        )
        assert status == 200

    def test_empty_program_treated_as_none(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, _body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab", "program": ""},
        )
        assert status == 200

    def test_returns_400_when_platform_is_false(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab", "platform": False},
        )
        assert status == 400
        assert "platform must be a string" in body["error"]

    def test_returns_400_when_platform_is_zero(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab", "platform": 0},
        )
        assert status == 400
        assert "platform must be a string" in body["error"]

    def test_returns_400_when_platform_is_list(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab", "platform": []},
        )
        assert status == 400
        assert "platform must be a string" in body["error"]

    def test_returns_400_when_program_is_list(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab", "program": []},
        )
        assert status == 400
        assert "program must be a string" in body["error"]

    def test_returns_400_when_program_is_false(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab", "program": False},
        )
        assert status == 400
        assert "program must be a string" in body["error"]

    def test_returns_403_when_recon_enabled_absent(
        self, tmp_path: Path
    ):
        from earn_money.dashboard import server
        paths = config.Paths.from_root(tmp_path)  # no RECON_ENABLED created
        with patch.object(server, "ProbeRunner", _FakeRunner, create=True):
            handler_cls = server._make_handler(
                paths, b"<!doctype html>", {}
            )
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab"},
        )
        assert status == 403
        assert "RECON_ENABLED" in body["error"]

    def test_requires_target_kind(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE},
        )
        assert status == 400
        assert "target_kind" in body["error"]

    def test_returns_400_when_target_kind_invalid(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "production"},
        )
        assert status == 400
        assert "target_kind" in body["error"]

    def test_allows_missing_program_for_local_lab(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, _body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab"},
        )
        assert status == 200

    def test_requires_program_for_registered_program(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "registered_program"},
        )
        assert status == 400
        assert "program required" in body["error"]

    def test_returns_403_when_registered_program_frozen(
        self, handler_factory, tmp_root: Path
    ):
        handler_cls, paths = handler_factory
        flags.freeze_program(paths, "local", "frozen-prog", reason="test")
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {
                "base_url": _BASE,
                "target_kind": "registered_program",
                "program": "frozen-prog",
            },
        )
        assert status == 403
        assert "frozen" in body["error"].lower()

    def test_does_not_check_frozen_for_local_lab(
        self, handler_factory, tmp_root: Path
    ):
        handler_cls, paths = handler_factory
        flags.freeze_program(paths, "local", "frozen-prog", reason="test")
        status, _body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {
                "base_url": _BASE,
                "target_kind": "local_lab",
                "program": "frozen-prog",
            },
        )
        assert status == 200

    def test_returns_409_when_another_probe_is_running(self, handler_factory):
        handler_cls, _paths = handler_factory
        _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab"},
        )
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab"},
        )
        assert status == 409
        assert body["error"] == "another probe is running"

    def test_409_payload_includes_existing_run_id(self, handler_factory):
        handler_cls, _paths = handler_factory
        _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab"},
        )
        _status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab"},
        )
        assert body["run_id"] == "fakerun123"

    def test_returns_500_when_runner_construction_raises(
        self, handler_factory
    ):
        from earn_money.dashboard import server

        handler_cls, _paths = handler_factory

        def raising_factory(*_args, **_kwargs):
            raise RuntimeError("boom")

        with patch.object(server, "ProbeRunner", raising_factory):
            status, body = _invoke_post(
                handler_cls,
                "/api/probe/start",
                {"base_url": _BASE, "target_kind": "local_lab"},
            )
        assert status == 500
        assert "runner init failed" in body["error"]

    def test_clear_probe_slot_clears_matching_finished_runner_when_called_directly(
        self, handler_factory
    ):
        from earn_money.dashboard import server

        handler_cls, _paths = handler_factory
        _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab"},
        )
        assert server._PROBE_SLOT is not None
        run_id = server._PROBE_SLOT.run_id()
        server._clear_probe_slot(run_id)
        assert server._PROBE_SLOT is None


class DrivenGet(NamedTuple):
    """Result of `_invoke_get` — exposes the handler too so tests can
    inspect `send_header.call_args_list` and so callers can supply a
    custom wfile that raises (e.g. BrokenPipeError) mid-stream."""
    status: int
    body: bytes
    handler: object


def _invoke_get(handler_cls, path: str, *, wfile=None) -> DrivenGet:
    """Drive GET on the stream route directly (bypassing do_GET). For
    the dispatcher-coverage tests in Task 8, use `_drive_dispatch`
    instead — that path exercises do_GET / do_POST."""
    if wfile is None:
        wfile = io.BytesIO()

    h = handler_cls.__new__(handler_cls)
    h.rfile = io.BytesIO(b"")
    h.wfile = wfile
    h.command = "GET"
    h.path = path
    h.request_version = "HTTP/1.1"
    h.headers = MagicMock()
    h.send_response = MagicMock()
    h.send_error = MagicMock()
    h.send_header = MagicMock()
    h.end_headers = MagicMock()
    h._serve_probe_stream()
    status = (h.send_response.call_args.args[0]
              if h.send_response.call_args else
              h.send_error.call_args.args[0])
    body = wfile.getvalue() if hasattr(wfile, "getvalue") else b""
    return DrivenGet(status, body, h)


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
        self, handler_factory
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

        def events():
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

        def events():
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

        def events():
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

        def events():
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

        def events():
            yield {"event": "_keepalive", "data": {}}
            yield {"event": "done", "data": done_data}

        runner.events = events
        server._PROBE_SLOT = runner
        result = _invoke_get(handler_cls, "/api/probe/stream?run_id=fakerun123")
        assert b":\n\n" in result.body

    def test_client_disconnect_mid_stream_does_not_kill_runner(
        self, handler_factory
    ):
        from earn_money.dashboard import server
        handler_cls, _paths = handler_factory
        runner = _FakeRunner()
        done_data = {"turns": 0, "stop_reason": "done",
                     "candidates_count": 0, "verified_count": 0, "denials_count": 0}

        def events():
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
        self, handler_factory
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


class TestDispatcher:
    """Test that do_GET and do_POST correctly dispatch to route handlers."""

    def test_do_post_dispatches_probe_start(self, handler_factory):
        handler_cls, _paths = handler_factory
        body = json.dumps({
            "base_url": "https://target.example.com",
            "target_kind": "local_lab",
        }).encode("utf-8")
        status, response_body, _h = _drive_dispatch(
            handler_cls, "POST", "/api/probe/start", raw_body=body
        )
        assert status == 200
        assert b"fakerun123" in response_body

    def test_do_get_dispatches_probe_stream(self, handler_factory):
        from earn_money.dashboard import server
        handler_cls, _paths = handler_factory
        server._PROBE_SLOT = _FakeRunner()
        status, response_body, _h = _drive_dispatch(
            handler_cls, "GET", "/api/probe/stream?run_id=fakerun123"
        )
        assert status == 200
        assert b"event: done" in response_body

    def test_do_post_unknown_path_returns_404(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, _response_body, _h = _drive_dispatch(
            handler_cls, "POST", "/api/does-not-exist", raw_body=b"{}"
        )
        assert status == 404
