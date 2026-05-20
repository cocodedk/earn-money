"""DashboardHandler factory.

Extracted from server.py to keep that module under the project's
200-line cap. The factory closes over `paths` + cached asset bytes and
returns a `BaseHTTPRequestHandler` subclass.
"""
from __future__ import annotations

import json
import logging
import threading
import traceback
from http.server import BaseHTTPRequestHandler
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

from earn_money import config
from earn_money.dashboard import aggregator
from earn_money.dashboard.probe_runner import ProbeRunner

from . import _server_probe_start as probe_start
from . import _server_probe_stream as probe_stream

if TYPE_CHECKING:
    from collections.abc import Callable

log = logging.getLogger(__name__)


def make_handler(
    paths: config.Paths,
    index_html: bytes,
    static_assets: dict[str, tuple[bytes, str]],
    *,
    slot_lock: threading.Lock,
    get_slot: Callable[[], ProbeRunner | None],
    set_slot: Callable[[ProbeRunner | None], None],
    runner_cls_getter: Callable[[], type[ProbeRunner]] = lambda: ProbeRunner,
) -> type[BaseHTTPRequestHandler]:
    """Build a `BaseHTTPRequestHandler` subclass that closes over `paths`.

    The handler must be a class, not an instance, so we bake `paths` and
    the cached assets into a fresh subclass per server. This is the
    standard pattern for injecting state into `BaseHTTPRequestHandler`.
    The slot lock + getter/setter live on the parent server module so
    multiple servers in one test process don't share probe state.
    """

    class DashboardHandler(BaseHTTPRequestHandler):
        # Bake `paths` onto the class so new route methods can read
        # self._paths.root for relative-path resolution.
        _paths = paths

        # Prevent stuck client connections from pinning threads forever.
        timeout = 5.0

        # Suppress the default stderr access log; the dashboard runs in
        # the operator's foreground terminal and noise drowns out real
        # signal. Errors still surface via `log_error`.
        def log_message(self, format: str, *args: object) -> None:
            return

        def do_GET(self) -> None:
            try:
                # Strip any query string before route dispatch — a cache-
                # buster like `?v=2` would otherwise miss every match and
                # silently 404 a real asset.
                path = self.path.split("?", 1)[0]
                if path == "/api/status":
                    self._serve_status()
                elif path == "/api/probe/stream":
                    self._serve_probe_stream()
                elif path == "/api/probe/current":
                    self._serve_probe_current()
                elif path == "/":
                    self._serve_index()
                elif path in static_assets:
                    self._send_bytes(*static_assets[path])
                else:
                    self.send_error(404, "Not Found")
            except Exception:
                # `log_message` is silenced above but `log_error` is not,
                # so unexpected failures still surface to stderr.
                self.log_error("%s", traceback.format_exc())
                self.send_error(500, "Internal Server Error")

        def do_POST(self) -> None:
            try:
                path = self.path.split("?", 1)[0]
                if path == "/api/probe/start":
                    self._serve_probe_start()
                else:
                    self.send_error(404, "Not Found")
            except Exception:
                self.log_error("%s", traceback.format_exc())
                self.send_error(500, "Internal Server Error")

        def _serve_status(self) -> None:
            payload = json.dumps(aggregator.build_status(paths)).encode("utf-8")
            self._send_bytes(payload, "application/json")

        def _serve_index(self) -> None:
            self._send_bytes(index_html, "text/html; charset=utf-8")

        def _send_bytes(self, body: bytes, content_type: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        # Responder protocol — exposed so probe_start helpers can push
        # JSON responses + read the body without importing
        # BaseHTTPRequestHandler.
        def read_body(self) -> bytes:
            length = int(self.headers.get("Content-Length") or "0")
            return self.rfile.read(length) if length > 0 else b""

        def send_json(self, status: int, payload: dict) -> None:  # type: ignore[type-arg]
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _serve_probe_start(self) -> None:
            probe_start.handle_probe_start(
                self, self._paths, slot_lock, get_slot, set_slot,
                runner_cls=runner_cls_getter(),
            )

        def _serve_probe_current(self) -> None:
            """Discovery endpoint. Lets the dashboard answer "is anything
            running right now?" without the operator knowing the run_id.

            Returns 404 when the slot is empty. Returns 200 with the
            runner's metadata (plus `is_running`) when populated — even
            for a finished run, so a late subscriber can still find and
            replay its history.
            """
            with slot_lock:
                runner = get_slot()
            if runner is None:
                return self.send_error(404, "no probe slot")
            try:
                payload = runner.metadata()
            except Exception:
                self.log_error("%s", traceback.format_exc())
                return self.send_error(500, "metadata unavailable")
            return self.send_json(200, payload)

        def _serve_probe_stream(self) -> None:
            qs = urlparse(self.path).query
            params = parse_qs(qs)
            run_id_list = params.get("run_id") or []
            run_id = run_id_list[0] if run_id_list else None
            if not run_id:
                return self.send_error(400, "run_id query param required")

            with slot_lock:
                runner = get_slot()
            if runner is None:
                return self.send_error(404, "no probe running")
            if runner.run_id() != run_id:
                return self.send_error(410, "run_id does not match the active probe")

            last_event_id = probe_stream.parse_last_event_id(
                self.headers.get("Last-Event-ID"),
            )
            probe_stream.send_sse_headers(self)
            probe_stream.stream_events(self, runner, last_event_id)

    return DashboardHandler
