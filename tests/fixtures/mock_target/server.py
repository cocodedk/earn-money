"""Deterministic HTTP fixture for active-recon integration tests.

Runs four handlers on four local ports so a single host header maps
to a distinct in-scope / out-of-scope identity:

- 127.0.0.1:18081  — in-scope host A. Returns 200 with title.
- 127.0.0.1:18082  — in-scope host B. Returns 301 redirect
                     to the OOS host (tests --no-follow-redirects).
- 127.0.0.1:18083  — OOS host. Returns 200; should never be probed by
                     the wrapper post-scope-filter.
- 127.0.0.1:18084  — Slow host. Sleeps 3s before responding; used by
                     kill-switch e2e test to exercise mid-run abort.
"""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class _InScopeHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Server", "mock-target/1.0")
        self.end_headers()
        self.wfile.write(b"<title>In-Scope A</title>")

    def log_message(self, *_a: object, **_k: object) -> None:
        pass


class _RedirectHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(301)
        self.send_header("Location", "http://127.0.0.1:18083/")
        self.end_headers()

    def log_message(self, *_a: object, **_k: object) -> None:
        pass


class _OosHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Server", "should-not-be-probed/1.0")
        self.end_headers()
        self.wfile.write(b"<title>OOS</title>")

    def log_message(self, *_a: object, **_k: object) -> None:
        pass


class _SlowHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        import time
        time.sleep(3.0)
        self.send_response(200)
        self.send_header("Server", "slow-target/1.0")
        self.end_headers()
        self.wfile.write(b"<title>Slow</title>")

    def log_message(self, *_a: object, **_k: object) -> None:
        pass


def _serve(port: int, handler_cls: type[BaseHTTPRequestHandler]) -> HTTPServer:
    server = HTTPServer(("127.0.0.1", port), handler_cls)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def start_mock_target() -> tuple[HTTPServer, HTTPServer, HTTPServer, HTTPServer]:
    return (
        _serve(18081, _InScopeHandler),
        _serve(18082, _RedirectHandler),
        _serve(18083, _OosHandler),
        _serve(18084, _SlowHandler),
    )


def stop_mock_target(servers: tuple[HTTPServer, ...]) -> None:
    for s in servers:
        s.shutdown()
        s.server_close()
