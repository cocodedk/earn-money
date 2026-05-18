"""GET /api/probe/stream handler — SSE event replay + tail.

Extracted from server.py to keep the main module under the project's
200-line cap. The function takes an existing ProbeRunner and the
BaseHTTPRequestHandler instance and writes SSE frames directly.
"""
from __future__ import annotations

import json
from typing import Any

from earn_money.dashboard.probe_runner import ProbeRunner

# Defence-in-depth: only known event names ever reach the wire. SSE
# event names must be a single line of ASCII; an accidental newline or
# non-ASCII byte from a future emitter would crash `name.encode("ascii")`
# outside the protocol.
_ALLOWED_SSE_EVENTS = {
    "turn", "finding", "done", "probe_error", "_keepalive", "meta",
}


def send_sse_headers(handler: Any) -> None:
    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("X-Accel-Buffering", "no")
    handler.end_headers()


def stream_events(handler: Any, runner: ProbeRunner, last_event_id: int) -> None:
    """Stream the per-run event history as SSE frames.

    Wrap EVERY wfile write — including the very first `retry: 0` frame —
    so a client that disconnects between end_headers() and the first
    byte doesn't escape as an uncaught BrokenPipeError. The loop thread
    is independent of this handler thread, so an early disconnect must
    not stop or clear the runner.
    """
    try:
        handler.wfile.write(b"retry: 0\n\n")
        handler.wfile.flush()

        for evt in runner.events(last_event_id=last_event_id):
            name = evt.get("event", "")
            data = evt.get("data", {})
            seq = evt.get("seq")
            if name not in _ALLOWED_SSE_EVENTS:
                # Coerce an unknown name into a probe_error frame
                # rather than crash on .encode("ascii").
                name = "probe_error"
                data = {"message": "invalid event type", "stage": "stream"}
            if name == "_keepalive":
                handler.wfile.write(b":\n\n")
            else:
                payload = json.dumps(data, default=str).encode("utf-8")
                frame = b""
                if isinstance(seq, int):
                    frame += b"id: " + str(seq).encode("ascii") + b"\n"
                frame += (
                    b"event: " + name.encode("ascii")
                    + b"\ndata: " + payload + b"\n\n"
                )
                handler.wfile.write(frame)
            handler.wfile.flush()
            if name in ("done", "probe_error"):
                return
    except (BrokenPipeError, ConnectionResetError):
        return


def parse_last_event_id(header_value: str | None) -> int:
    """Browser reconnect carries `Last-Event-ID: <seq>`. The EventHistory
    replays everything with seq > last_event_id, then tails new appends —
    so a page reload sees the trace it would otherwise have lost. A
    malformed header falls back to a fresh-subscriber replay; never
    crash the stream."""
    try:
        return int(header_value) if header_value else 0
    except (TypeError, ValueError):
        return 0
