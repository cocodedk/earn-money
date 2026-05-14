"""HTTP server for the dashboard.

stdlib `ThreadingHTTPServer` + a small `BaseHTTPRequestHandler` subclass.
Two routes:
- `GET /`           → ``templates/index.html`` (200, ``text/html``)
- `GET /api/status` → ``aggregator.build_status(paths)`` as JSON
- anything else     → 404

Bound to ``127.0.0.1`` by construction; non-loopback access is blocked
at the socket layer rather than via auth.
"""

from __future__ import annotations

import argparse
import json
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from earn_money import config
from earn_money.dashboard import aggregator

_TEMPLATE_PATH = Path(__file__).parent / "templates" / "index.html"
_DEFAULT_PORT = 8080
_HOST = "127.0.0.1"


def build(paths: config.Paths, port: int) -> ThreadingHTTPServer:
    """Return a `ThreadingHTTPServer` bound to 127.0.0.1:`port`.

    `port=0` picks an ephemeral port (used by tests). The server is not
    started — the caller runs `serve_forever()` on a thread.

    The HTML template is read once here so per-request handlers don't
    hit the filesystem. A missing template is a fail-fast install bug:
    `FileNotFoundError` propagates and the server refuses to start.
    """
    index_html = _TEMPLATE_PATH.read_bytes()
    handler_cls = _make_handler(paths, index_html)
    return ThreadingHTTPServer((_HOST, port), handler_cls)


def _make_handler(
    paths: config.Paths, index_html: bytes
) -> type[BaseHTTPRequestHandler]:
    """Build a `BaseHTTPRequestHandler` subclass that closes over `paths`.

    The handler must be a class, not an instance, so we bake `paths` and
    the cached template into a fresh subclass per server. This is the
    standard pattern for injecting state into `BaseHTTPRequestHandler`.
    """

    class DashboardHandler(BaseHTTPRequestHandler):
        # Prevent stuck client connections from pinning threads forever.
        timeout = 5.0

        # Suppress the default stderr access log; the dashboard runs in
        # the operator's foreground terminal and noise drowns out real
        # signal. Errors still surface via `log_error`.
        def log_message(self, format: str, *args: object) -> None:
            return

        def do_GET(self) -> None:
            try:
                if self.path == "/api/status":
                    self._serve_status()
                elif self.path == "/":
                    self._serve_index()
                else:
                    self.send_error(404, "Not Found")
            except Exception:
                # `log_message` is silenced above but `log_error` is not,
                # so unexpected failures still surface to stderr.
                self.log_error("%s", traceback.format_exc())
                self.send_error(500, "Internal Server Error")

        def _serve_status(self) -> None:
            payload = json.dumps(aggregator.build_status(paths)).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _serve_index(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(index_html)))
            self.end_headers()
            self.wfile.write(index_html)

    return DashboardHandler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dashboard")
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    parser.add_argument("--port", default=_DEFAULT_PORT, type=int)
    args = parser.parse_args(argv)
    paths = config.Paths.from_root(args.root)
    httpd = build(paths, port=args.port)
    # `_HOST` is the bound host by construction; `server_address[1]` is
    # the actual int port (which may differ from `args.port` when 0).
    bound_port = httpd.server_address[1]
    print(f"dashboard: serving on http://{_HOST}:{bound_port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("dashboard: shutting down")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
