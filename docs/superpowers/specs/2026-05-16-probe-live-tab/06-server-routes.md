# 06 — Dashboard server routes

Modifies `src/earn_money/dashboard/server.py`. Adds two routes plus a module-level slot and lock for the one-at-a-time guard.

## New module state

```python
_PROBE_SLOT_LOCK = threading.Lock()
_PROBE_SLOT: ProbeRunner | None = None
```

Why a lock: two near-simultaneous `POST /api/probe/start` requests on `ThreadingHTTPServer` race the slot check. The lock makes the slot read/write atomic across handler threads.

## Routes

### POST /api/probe/start

```
Content-Type:  application/json
Body (JSON):
  {
    "base_url":     "https://target.example.com",   # required, http/https only, no userinfo
    "platform":     "local",                        # optional
    "program":      "test-prog",                    # optional
    "roe_profile":  "roe/local-lab.yaml",           # optional; empty string = null
    "max_turns":    10                              # optional, 1 ≤ n ≤ 50
  }

Responses:
  200 { "run_id": "<uuid4 hex>" }       — runner started
  400 { "error": "<message>" }          — base_url invalid / max_turns out of range
                                          / RoE path not found / malformed JSON
                                          / platform or program not a string
  403 { "error": "RECON_ENABLED absent" | "Program frozen: …" }
  409 { "error": "another probe is running", "run_id": "<existing>" }
  500 { "error": "<traceback summary>" } — unexpected failure during construction
```

Handler outline:

```python
def _serve_probe_start(self) -> None:
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
        return self._send_json(400, {"error": f"base_url scheme must be http or https, got {parsed.scheme!r}"})
    if parsed.username or parsed.password:
        return self._send_json(400, {"error": "base_url must not contain userinfo (user:pass@)"})
    if not parsed.hostname:
        return self._send_json(400, {"error": "base_url missing host"})

    # platform/program — accept JSON, so guard the types explicitly
    # rather than trusting form-input habits. Avoid `body.get(...) or
    # default` because that coerces 0/False/[]/{} into the default and
    # hides bad input from the type check below.
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

    # roe_profile empty string is treated as null, not Path("").
    # Relative paths are resolved against the dashboard's --root, not the
    # process cwd, so `roe/local-lab.yaml` works regardless of how the
    # server was invoked.
    roe_raw = body.get("roe_profile")
    if isinstance(roe_raw, str) and roe_raw.strip():
        roe_path = Path(roe_raw.strip())
        if not roe_path.is_absolute():
            roe_path = self._paths.root / roe_path
    else:
        roe_path = None

    max_turns = body.get("max_turns")
    if max_turns is not None:
        if not isinstance(max_turns, int) or not (1 <= max_turns <= 50):
            return self._send_json(400, {"error": "max_turns must be an int between 1 and 50"})

    # Validate the RoE path early — operators type it into a form field
    # and typos are likely. A 400 with the literal path is far more
    # helpful than the generic 500 we'd otherwise emit from runner init.
    if roe_path is not None and not roe_path.exists():
        return self._send_json(400, {"error": f"RoE profile not found: {roe_path}"})

    try:
        flags.require_recon_enabled(self._paths)
        if program:
            flags.require_program_not_frozen(self._paths, platform, program)
    except flags.ReconDisabled as e:
        return self._send_json(403, {"error": str(e)})
    except flags.ProgramFrozen as e:
        return self._send_json(403, {"error": str(e)})

    with _PROBE_SLOT_LOCK:
        global _PROBE_SLOT
        if _PROBE_SLOT is not None and _PROBE_SLOT.is_running():
            return self._send_json(409, {
                "error": "another probe is running",
                "run_id": _PROBE_SLOT.run_id(),
            })
        try:
            runner = ProbeRunner(
                base_url=base_url, roe_path=roe_path, paths=self._paths,
                platform=platform, program=program, max_turns=max_turns,
                on_finished=_clear_probe_slot,
            )
        except Exception as e:
            return self._send_json(500, {"error": f"runner init failed: {e}"})

        # Install the slot BEFORE starting the thread — otherwise a fast
        # runner can finish (and fire on_finished, finding no slot to clear)
        # before this handler reaches the assignment. With the slot in
        # place first, _clear_probe_slot sees the correct runner regardless
        # of how quickly the loop exits.
        _PROBE_SLOT = runner
        try:
            run_id = runner.start()
        except Exception:
            _PROBE_SLOT = None
            raise

    self._send_json(200, {"run_id": run_id})


def _clear_probe_slot(run_id: str) -> None:
    """Callback handed to ProbeRunner; clears the module slot in the
    runner's `finally`. Lives in server.py because that's where the slot
    is — the runner never imports from server.py."""
    global _PROBE_SLOT
    with _PROBE_SLOT_LOCK:
        if _PROBE_SLOT is not None and _PROBE_SLOT.run_id() == run_id:
            _PROBE_SLOT = None
```

`_read_body()` reads `Content-Length` bytes from `self.rfile` (helper added to the handler — small wrapper).

### GET /api/probe/stream

```
Query string:  ?run_id=<uuid4 hex>             ← required since v1.1

Response headers (on success):
  HTTP/1.1 200 OK
  Content-Type:        text/event-stream; charset=utf-8
  Cache-Control:       no-cache
  X-Accel-Buffering:   no

Response status / errors:
  404                          — no probe running (slot empty)
  410 Gone                     — run_id query param does not match the active runner
  400                          — run_id query param missing

Body (success):
  retry: 0                                       ← belt: discourage auto-reconnect
  event: turn
  data: {"turn":1,"stage":"action_pending",...}
  
  event: turn
  data: {"turn":1,"stage":"action_parsed",...}
  ...
  event: done
  data: {"turns":7,"stop_reason":"max_turns","candidates":2,"verified":1,"denials":0}

Behaviour:
  - Parses ?run_id= from the query string.
  - Reads the current _PROBE_SLOT under the lock.
  - If no slot: 404. If slot's run_id != param: 410.
  - Otherwise drains runner.events() until "done" or "probe_error", framing each.
  - Sends ":\n\n" comment lines on _keepalive events to hold the connection open.
  - On client disconnect (BrokenPipeError on wfile.write): silently end; the
    loop thread keeps running (independent of this connection).
```

Handler outline:

```python
def _serve_probe_stream(self) -> None:
    qs = urlparse(self.path).query
    params = parse_qs(qs)
    run_id = (params.get("run_id") or [None])[0]
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
    self.wfile.write(b"retry: 0\n\n")
    self.wfile.flush()

    try:
        for evt in runner.events():
            name = evt.get("event", "")
            data = evt.get("data", {})
            if name == "_keepalive":
                self.wfile.write(b":\n\n")
            else:
                payload = json.dumps(data, default=str).encode("utf-8")
                frame = b"event: " + name.encode("ascii") + b"\ndata: " + payload + b"\n\n"
                self.wfile.write(frame)
            self.wfile.flush()
            if name in ("done", "probe_error"):
                return
    except (BrokenPipeError, ConnectionResetError):
        return  # client gone; loop thread is independent
```

Notes on the wire format (resolves second-reviewer #7):

- `Connection: keep-alive` was previously listed; **removed**. Python's `BaseHTTPRequestHandler` doesn't reliably honour it across HTTP/1.0 vs 1.1 contexts, and SSE survives without it — each frame is `wfile.flush()`-ed individually, and the connection naturally closes after `done` / `probe_error`.
- The earlier draft claimed `Transfer-Encoding: chunked happens by omitting Content-Length`. **Removed** — `BaseHTTPRequestHandler` doesn't auto-emit chunk framing. What actually happens is: response has no `Content-Length`, each `wfile.write` sends bytes immediately after `flush()`, and the SSE protocol is robust to the absence of chunked encoding because each event is `\n\n`-terminated.
- `retry: 0` is sent as a belt against auto-reconnect. The browser-side `EventSource.close()` after the first `done`/`probe_error` is the real fix; this is defence-in-depth.

`run_id` query param (resolves second-reviewer #4): the client receives the `run_id` from `POST /api/probe/start` and includes it on the stream URL. The server rejects mismatches with `410 Gone` — preventing a stale tab from accidentally consuming a fresh run's stream.

## DELETE /api/probe (optional, low cost)

Not in v1. The `stop()` method on `ProbeRunner` exists but isn't reachable from the dashboard form in this iteration. Adding a `POST /api/probe/stop` (or `DELETE /api/probe`) route is a 10-line follow-up: drain the slot, call `runner.stop()`, return 204. Out of scope per [13-out-of-scope.md](13-out-of-scope.md).

## Wiring in `_STATIC_ROUTES`

Four new static assets:

```python
_STATIC_ROUTES: dict[str, tuple[Path, str]] = {
    # … existing entries …
    "/static/tabs.js":           (_STATIC / "tabs.js",         _JS),
    "/static/probe.js":          (_STATIC / "probe.js",        _JS),
    "/static/probe-render.js":   (_STATIC / "probe-render.js", _JS),
    "/static/probe.css":         (_STATIC / "probe.css",       _CSS),
}
```

Cached at server start (existing pattern at `server.py:62-65`).

## Dispatcher delta in `do_GET`

```python
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
```

And a new `do_POST`:

```python
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
```

## Handler state: `paths`

The new route validation reads `self._paths.root` (for RoE-path resolution against the dashboard root), so `self._paths` must be available on the handler instance — not just as a closure variable. The existing `_make_handler(paths, index_html, static_assets)` factory builds a fresh `BaseHTTPRequestHandler` subclass per server, so the wiring is concrete:

```python
def _make_handler(paths, index_html, static_assets):

    class DashboardHandler(BaseHTTPRequestHandler):
        # Bake `paths` onto the class so instance methods read it as
        # self._paths. Cleaner than threading the closure variable
        # through every new handler method.
        _paths = paths
        timeout = 5.0
        # … existing log_message / do_GET unchanged …

        def do_POST(self) -> None: ...
        def _serve_probe_start(self) -> None: ...
        def _serve_probe_stream(self) -> None: ...

    return DashboardHandler
```

The existing `_serve_status` keeps reading the closure-scoped `paths` (no churn there). New methods use `self._paths`.

## Tests

`tests/dashboard/test_probe_routes.py`:

- `POST /api/probe/start` with valid body → 200 + `run_id`. Use a `FakeProbeRunner` subbed into the module via `monkeypatch` so no real thread spawns.
- `POST /api/probe/start` without `base_url` → 400.
- `POST /api/probe/start` without `RECON_ENABLED` → 403.
- `POST /api/probe/start` against a frozen program → 403.
- Two `POST /api/probe/start` in a row → second returns 409 with the first run's `run_id`.
- `GET /api/probe/stream` with no slot → 404.
- `GET /api/probe/stream` with a slot that yields `[turn, finding, done]` → SSE body contains all three frames in order, ends after `done`.

Detail in [12-tests.md](12-tests.md).
