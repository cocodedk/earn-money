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
import logging
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from earn_money import config, flags
from earn_money.dashboard import aggregator
from earn_money.dashboard.probe_runner import ProbeRunner

log = logging.getLogger(__name__)

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
    "/static/probe.css":        (_STATIC / "probe.css",        _CSS),
    "/static/render.js":        (_STATIC / "render.js",        _JS),
    "/static/render_panels.js": (_STATIC / "render_panels.js", _JS),
    "/static/dashboard.js":     (_STATIC / "dashboard.js",     _JS),
    "/static/tabs.js":          (_STATIC / "tabs.js",          _JS),
    "/static/probe.js":         (_STATIC / "probe.js",         _JS),
    "/static/probe-render.js":  (_STATIC / "probe-render.js",  _JS),
}

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
                elif path == "/api/probe/stream":
                    self._serve_probe_stream()
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

        def _read_body(self) -> bytes:
            length = int(self.headers.get("Content-Length") or "0")
            return self.rfile.read(length) if length > 0 else b""

        def _send_json(self, status: int, payload: dict) -> None:  # type: ignore[type-arg]
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _serve_probe_start(self) -> None:
            # `global` must be declared before ANY use of the name in the
            # function body. The fast-409 check below reads _PROBE_SLOT, so
            # this declaration must come first — otherwise Python emits a
            # SyntaxWarning ("used prior to global declaration") and the
            # name is treated as local at the read sites.
            global _PROBE_SLOT

            try:
                body = json.loads(self._read_body() or b"{}")
            except json.JSONDecodeError:
                return self._send_json(400, {"error": "invalid JSON body"})

            base_url = body.get("base_url")
            if not isinstance(base_url, str) or not base_url.strip():
                return self._send_json(400, {"error": "base_url required"})
            base_url = base_url.strip().rstrip("/")
            parsed = urlparse(base_url)
            if parsed.scheme not in ("http", "https"):
                return self._send_json(400, {"error":
                    f"base_url scheme must be http or https, got {parsed.scheme!r}"})
            if parsed.username or parsed.password:
                return self._send_json(400, {"error":
                    "base_url must not contain userinfo (user:pass@)"})
            if not parsed.hostname:
                return self._send_json(400, {"error": "base_url missing host"})

            # Defence-in-depth fast-fail for obvious SSRF / internal
            # targets. The authoritative enforcement lives in
            # ScopePolicy._check_host (agent/scope_policy.py) — it
            # rejects loopback / private / link-local / IMDS / multicast
            # IPs at HTTP-request time, and the safe-default RoE has
            # allowed_hosts=[] so every host is denied unless explicitly
            # listed. This early guard just gives the operator a 400
            # before any probe machinery is built. Hosts allowed by an
            # explicit RoE profile (e.g. a lab pointing at `localhost`)
            # still get rejected here — for true local-lab work, use a
            # hostname like `target.cocode.dk` mapped via /etc/hosts.
            host_lower = parsed.hostname.lower()
            if host_lower in ("localhost", "0.0.0.0", "::", "::1"):
                return self._send_json(400, {"error":
                    f"base_url host {parsed.hostname!r} is loopback/unspecified"})
            try:
                import ipaddress
                addr = ipaddress.ip_address(host_lower)
                for net_cidr in ("127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12",
                                 "192.168.0.0/16", "169.254.0.0/16",
                                 "224.0.0.0/4", "::1/128", "fc00::/7", "fe80::/10"):
                    if addr in ipaddress.ip_network(net_cidr):
                        return self._send_json(400, {"error":
                            f"base_url host {parsed.hostname!r} is private/reserved"})
            except ValueError:
                pass  # hostname (not an IP literal) — fine, let runtime ScopePolicy enforce

            # target_kind is required and explicit — removes the prior
            # ambiguity where omitting `program` silently skipped FROZEN.
            target_kind = body.get("target_kind")
            if target_kind not in ("local_lab", "registered_program"):
                return self._send_json(400, {"error":
                    "target_kind must be 'local_lab' or 'registered_program'"})

            platform = body.get("platform", "local")
            program = body.get("program")
            if platform in ("", None):
                platform = "local"
            if program == "":
                program = None
            if not isinstance(platform, str):
                return self._send_json(400, {"error": "platform must be a string"})
            if program is not None and not isinstance(program, str):
                return self._send_json(400, {"error": "program must be a string"})

            # registered_program REQUIRES program (the FROZEN gate
            # depends on it). local_lab MAY omit program — FROZEN is
            # skipped for local-lab targets by design, but RoE /
            # ScopePolicy still enforce allowed_hosts at request time.
            if target_kind == "registered_program" and not program:
                return self._send_json(400, {"error":
                    "program required when target_kind=registered_program"})

            roe_raw = body.get("roe_profile")
            roe_path: Path | None
            if isinstance(roe_raw, str) and roe_raw.strip():
                _rp = Path(roe_raw.strip())
                roe_path = _rp if _rp.is_absolute() else self._paths.root / _rp
            else:
                roe_path = None

            max_turns = body.get("max_turns")
            # `type(x) is int` rejects bool (which is a subclass of
            # int — `isinstance(True, int)` is True, and
            # `1 <= True <= 50` is True too, so isinstance would
            # silently accept max_turns=true).
            if max_turns is not None and (
                type(max_turns) is not int or not (1 <= max_turns <= 50)
            ):
                return self._send_json(400, {"error":
                    "max_turns must be an int between 1 and 50"})

            if roe_path is not None and not roe_path.exists():
                return self._send_json(400, {"error":
                    f"RoE profile not found: {roe_path}"})

            try:
                flags.require_recon_enabled(self._paths)
                # FROZEN check is gated on target_kind — local_lab targets
                # are off-platform and have no FROZEN flag to check.
                if target_kind == "registered_program":
                    flags.require_program_not_frozen(self._paths, platform, program)  # type: ignore[arg-type]
            except flags.ReconDisabled as e:
                return self._send_json(403, {"error": str(e)})
            except flags.ProgramFrozen as e:
                return self._send_json(403, {"error": str(e)})

            # Fast 409 — fail before doing any construction work.
            with _PROBE_SLOT_LOCK:
                if _PROBE_SLOT is not None and _PROBE_SLOT.is_running():
                    return self._send_json(409, {
                        "error": "another probe is running",
                        "run_id": _PROBE_SLOT.run_id(),
                    })

            # Build the runner OUTSIDE the lock. ProbeRunner.__init__ does
            # file I/O (load_roe_profile), SQLite I/O (_seed_urls), and
            # provider construction (providers_mod.from_env()) — none of
            # which should pin the global slot lock across slow operations.
            try:
                runner = ProbeRunner(
                    base_url=base_url, roe_path=roe_path, paths=self._paths,
                    target_kind=target_kind,
                    platform=platform, program=program, max_turns=max_turns,
                    # NOTE: deliberately no on_finished=. The slot is
                    # NOT cleared when the runner exits — that would
                    # race a fast run against the browser's EventSource
                    # connect (operator never sees the done event).
                    # The slot is replaced by the next start instead.
                )
            except Exception:
                log.exception("ProbeRunner init failed")
                return self._send_json(500, {"error": "runner init failed"})

            # Re-check + install under the lock. A racing handler may have
            # installed its own slot while we were constructing — discard
            # ours in that case (it never started; nothing to stop).
            with _PROBE_SLOT_LOCK:
                if _PROBE_SLOT is not None and _PROBE_SLOT.is_running():
                    return self._send_json(409, {
                        "error": "another probe is running",
                        "run_id": _PROBE_SLOT.run_id(),
                    })
                # Install the slot BEFORE starting the thread — otherwise a
                # fast runner can finish (and fire on_finished, finding no
                # slot to clear) before this handler reaches the assignment.
                _PROBE_SLOT = runner
                try:
                    run_id = runner.start()
                except Exception:
                    _PROBE_SLOT = None
                    raise

            self._send_json(200, {"run_id": run_id})

        def _serve_probe_stream(self) -> None:
            qs = urlparse(self.path).query
            params = parse_qs(qs)
            run_id_list = params.get("run_id") or []
            run_id = run_id_list[0] if run_id_list else None
            if not run_id:
                return self.send_error(400, "run_id query param required")

            with _PROBE_SLOT_LOCK:
                runner = _PROBE_SLOT
            if runner is None:
                return self.send_error(404, "no probe running")
            if runner.run_id() != run_id:
                return self.send_error(410, "run_id does not match the active probe")

            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()

            # Defence-in-depth: only known event names ever reach the
            # wire. SSE event names must be a single line of ASCII; an
            # accidental newline or non-ASCII byte from a future emitter
            # would crash `name.encode("ascii")` outside the protocol.
            _ALLOWED_SSE_EVENTS = {
                "turn", "finding", "done", "probe_error", "_keepalive",
            }

            # Wrap EVERY wfile write — including the very first `retry: 0`
            # frame — so a client that disconnects between end_headers()
            # and the first byte doesn't escape as an uncaught
            # BrokenPipeError. The loop thread is independent of this
            # handler thread, so an early disconnect must not stop or
            # clear the runner.
            try:
                self.wfile.write(b"retry: 0\n\n")
                self.wfile.flush()

                for evt in runner.events():
                    name = evt.get("event", "")
                    data = evt.get("data", {})
                    if name not in _ALLOWED_SSE_EVENTS:
                        # Coerce an unknown name into a probe_error frame
                        # rather than crash on .encode("ascii").
                        name = "probe_error"
                        data = {"message": "invalid event type", "stage": "stream"}
                    if name == "_keepalive":
                        self.wfile.write(b":\n\n")
                    else:
                        payload = json.dumps(data, default=str).encode("utf-8")
                        frame = (
                            b"event: " + name.encode("ascii")
                            + b"\ndata: " + payload + b"\n\n"
                        )
                        self.wfile.write(frame)
                    self.wfile.flush()
                    if name in ("done", "probe_error"):
                        return
            except (BrokenPipeError, ConnectionResetError):
                return

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
