"""Shared helpers for the probe-routes test splits."""
from __future__ import annotations

import io
import json
from typing import NamedTuple
from unittest.mock import MagicMock

_BASE = "https://target.example.com"


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

    def events(self, last_event_id: int = 0):
        yield {
            "event": "done",
            "data": {
                "turns": 0,
                "stop_reason": "done",
                "candidates_count": 0,
                "verified_count": 0,
                "denials_count": 0,
            },
            "seq": 1,
        }


def _drive(
    handler_cls, method: str, path: str, *, raw_body: bytes = b"",
) -> tuple[int, dict]:
    """Drive a route method on the handler class without sockets.

    `_serve_probe_start` reads exactly `Content-Length` bytes from
    `self.rfile`. The rfile here therefore contains **only the body
    bytes** — not a full HTTP request line + headers. (An earlier
    version of this shim prepended fake request headers; that put the
    handler's read at byte 0 of the header line and silently 400'd
    every test.)"""
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
        handler_cls, "POST", path, raw_body=json.dumps(body).encode("utf-8"),
    )


def _invoke_post_raw(handler_cls, path: str, raw: bytes) -> tuple[int, dict]:
    """Convenience: drive POST with arbitrary bytes (malformed-JSON tests)."""
    return _drive(handler_cls, "POST", path, raw_body=raw)


def _drive_dispatch(
    handler_cls, method: str, path: str, *, raw_body: bytes = b"",
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


class DrivenGet(NamedTuple):
    """Result of `_invoke_get` — exposes the handler too so tests can
    inspect `send_header.call_args_list` and so callers can supply a
    custom wfile that raises (e.g. BrokenPipeError) mid-stream."""
    status: int
    body: bytes
    handler: object


def _invoke_get(handler_cls, path: str, *, wfile=None) -> DrivenGet:
    """Drive GET on the stream route directly (bypassing do_GET). For
    the dispatcher-coverage tests, use `_drive_dispatch` instead — that
    path exercises do_GET / do_POST."""
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
