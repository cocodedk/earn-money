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
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from earn_money import config
from earn_money.dashboard.probe_runner import ProbeRunner

from ._server_handler import make_handler
from ._server_static import load_index_html, load_static_assets

# Re-export for compatibility with tests that
# `patch.object(server, "ProbeRunner", ...)` or call
# `server._make_handler(...)`.
__all__ = ["ProbeRunner", "_clear_probe_slot", "_make_handler", "build", "main"]

log = logging.getLogger(__name__)

_DEFAULT_PORT = 8080
_DEFAULT_HOST = "127.0.0.1"

# One-at-a-time probe runner — module-level slot under a lock so two
# near-simultaneous POST /api/probe/start handler threads race safely.
# IMPORTANT: the slot is NOT auto-cleared when a runner finishes. The
# slot acts as "the most recent runner" (running or done) so a late-
# arriving EventSource can still drain the terminal `done` /
# `probe_error` event. The slot is replaced when the next start
# overwrites it (see Task 6). See 04-probe-runner-class.md §"_run_safe"
# for the rationale.
_PROBE_SLOT: ProbeRunner | None = None
_PROBE_SLOT_LOCK = threading.Lock()


def _get_slot() -> ProbeRunner | None:
    return _PROBE_SLOT


def _set_slot(runner: ProbeRunner | None) -> None:
    global _PROBE_SLOT
    _PROBE_SLOT = runner


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


def _make_handler(
    paths: config.Paths,
    index_html: bytes,
    static_assets: dict[str, tuple[bytes, str]],
) -> type[BaseHTTPRequestHandler]:
    """Test-facing re-export of `_server_handler.make_handler`. Lazily
    reads `server.ProbeRunner` so test patches via
    `patch.object(server, "ProbeRunner", _FakeRunner)` take effect."""
    return make_handler(
        paths, index_html, static_assets,
        slot_lock=_PROBE_SLOT_LOCK,
        get_slot=_get_slot,
        set_slot=_set_slot,
        # Read at call time so `patch.object(server, "ProbeRunner", ...)`
        # patches stick — the lambda re-resolves the module-level name
        # each invocation.
        runner_cls_getter=lambda: ProbeRunner,
    )


def build(
    paths: config.Paths, port: int, host: str = _DEFAULT_HOST,
) -> ThreadingHTTPServer:
    """Return a `ThreadingHTTPServer` bound to `host`:`port`.

    Default host is `127.0.0.1` — loopback-only. Operators behind a
    host firewall that allow-lists their own IP can pass `host="0.0.0.0"`
    (or a specific interface) to accept direct connections; the firewall
    is then the auth boundary. `port=0` picks an ephemeral port.

    Static assets (index.html plus the entries in `_server_static`) are
    read once here so per-request handlers don't hit the filesystem. A
    missing file is a fail-fast install bug: `FileNotFoundError`
    propagates and the server refuses to start.
    """
    index_html = load_index_html()
    static_assets = load_static_assets()
    handler_cls = _make_handler(paths, index_html, static_assets)
    return ThreadingHTTPServer((host, port), handler_cls)


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
