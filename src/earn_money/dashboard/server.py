"""HTTP server for the dashboard.

stdlib `ThreadingHTTPServer` + a small `BaseHTTPRequestHandler` subclass.
Routes:
- `GET /`                      → ``templates/index.html`` (200, ``text/html``)
- `GET /static/dashboard.css`  → cached CSS bytes (200, ``text/css``)
- `GET /static/dashboard.js`   → cached JS bytes  (200, ``application/javascript``)
- `GET /api/status`            → ``aggregator.build_status(paths)`` as JSON
- anything else                → 404

Default bind is ``127.0.0.1`` (loopback only). `--host` lets the
operator opt into a non-loopback bind when the host firewall is the
auth boundary (e.g. VPS deployment behind a FW rule allowing only the
operator's IP).
"""

from __future__ import annotations

import argparse
import json
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TYPE_CHECKING

from earn_money import config
from earn_money.dashboard import aggregator

if TYPE_CHECKING:
    from earn_money.dashboard.probe_runner import ProbeRunner

_TEMPLATES = Path(__file__).parent / "templates"
_STATIC = _TEMPLATES / "static"
_DEFAULT_PORT = 8080
_DEFAULT_HOST = "127.0.0.1"

# URL → (filesystem path, Content-Type).
_CSS = "text/css; charset=utf-8"
_JS = "application/javascript; charset=utf-8"
_STATIC_ROUTES: dict[str, tuple[Path, str]] = {
    "/static/tokens.css":       (_STATIC / "tokens.css",       _CSS),
    "/static/dashboard.css":    (_STATIC / "dashboard.css",    _CSS),
    "/static/panels.css":       (_STATIC / "panels.css",       _CSS),
    "/static/render.js":        (_STATIC / "render.js",        _JS),
    "/static/render_panels.js": (_STATIC / "render_panels.js", _JS),
    "/static/dashboard.js":     (_STATIC / "dashboard.js",     _JS),
}

# One-at-a-time probe runner — module-level slot under a lock so two
# near-simultaneous POST /api/probe/start handler threads race safely.
# IMPORTANT: the slot is NOT auto-cleared when a runner finishes. The
# slot acts as "the most recent runner" (running or done) so a late-
# arriving EventSource can still drain the terminal `done` /
# `probe_error` event. The slot is replaced when the next start
# overwrites it (see Task 6). See 04-probe-runner-class.md §"_run_safe"
# for the rationale.
_PROBE_SLOT: "ProbeRunner | None" = None  # noqa: UP037
_PROBE_SLOT_LOCK = threading.Lock()


def _clear_probe_slot(run_id: str) -> None:
    """Manual/test-only cleanup helper. NOT wired to ProbeRunner via
    on_finished — the runner deliberately keeps the slot populated
    after exit so the stream route can still serve the terminal event.
    This helper exists so tests can reset module state between cases
    (the `_reset_probe_slot` autouse fixture in
    tests/dashboard/test_probe_routes.py just sets `_PROBE_SLOT = None`
    directly, but the named helper is available for explicit-run-id
    cleanup if a future iteration needs it)."""
    global _PROBE_SLOT
    with _PROBE_SLOT_LOCK:
        if _PROBE_SLOT is not None and _PROBE_SLOT.run_id() == run_id:
            _PROBE_SLOT = None


def build(
    paths: config.Paths, port: int, host: str = _DEFAULT_HOST,
) -> ThreadingHTTPServer:
    """Return a `ThreadingHTTPServer` bound to `host`:`port`.

    Default host is `127.0.0.1` — loopback-only. Operators behind a
    host firewall that allow-lists their own IP can pass `host="0.0.0.0"`
    (or a specific interface) to accept direct connections; the firewall
    is then the auth boundary. `port=0` picks an ephemeral port.

    Static assets (index.html plus the entries in `_STATIC_ROUTES`) are
    read once here so per-request handlers don't hit the filesystem. A
    missing file is a fail-fast install bug: `FileNotFoundError`
    propagates and the server refuses to start.
    """
    index_html = (_TEMPLATES / "index.html").read_bytes()
    static_assets: dict[str, tuple[bytes, str]] = {
        url: (path.read_bytes(), ctype)
        for url, (path, ctype) in _STATIC_ROUTES.items()
    }
    handler_cls = _make_handler(paths, index_html, static_assets)
    return ThreadingHTTPServer((host, port), handler_cls)


def _make_handler(
    paths: config.Paths,
    index_html: bytes,
    static_assets: dict[str, tuple[bytes, str]],
) -> type[BaseHTTPRequestHandler]:
    """Build a `BaseHTTPRequestHandler` subclass that closes over `paths`.

    The handler must be a class, not an instance, so we bake `paths` and
    the cached assets into a fresh subclass per server. This is the
    standard pattern for injecting state into `BaseHTTPRequestHandler`.
    """

    class DashboardHandler(BaseHTTPRequestHandler):
        # Bake `paths` onto the class so new route methods can read
        # self._paths.root for relative-path resolution. The existing
        # _serve_status keeps reading the closure variable.
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

    return DashboardHandler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dashboard")
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    parser.add_argument("--port", default=_DEFAULT_PORT, type=int)
    parser.add_argument(
        "--host", default=_DEFAULT_HOST,
        help="bind address; default 127.0.0.1 (loopback). Set to 0.0.0.0 "
             "for direct access when the host firewall is the auth boundary.",
    )
    args = parser.parse_args(argv)
    paths = config.Paths.from_root(args.root)
    httpd = build(paths, port=args.port, host=args.host)
    # `server_address[1]` is the actual int port (which may differ from
    # `args.port` when 0).
    bound_port = httpd.server_address[1]
    print(f"dashboard: serving on http://{args.host}:{bound_port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("dashboard: shutting down")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
