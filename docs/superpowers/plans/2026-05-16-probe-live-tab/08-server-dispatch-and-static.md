# Task 8 — Wire dispatchers (`do_GET` / `do_POST`) and new static asset routes

**Spec section:** `docs/superpowers/specs/2026-05-16-probe-live-tab/06-server-routes.md` §"Wiring in `_STATIC_ROUTES`", §"Dispatcher delta in `do_GET`"

**Files:**
- Modify: `src/earn_money/dashboard/server.py`
- Modify: `tests/dashboard/test_probe_routes.py`

The route methods exist (Tasks 6 and 7) but no HTTP request reaches them yet — the handler's `do_GET` doesn't know about `/api/probe/stream`, and there is no `do_POST` at all. This task wires both. Static assets for the new JS/CSS files are also registered so the existing read-once / cache pattern serves them.

The Task 6/7 helpers call `_serve_probe_start` / `_serve_probe_stream` directly — they verify route behaviour but **not** the dispatcher. This task adds explicit `do_POST` / `do_GET` coverage so a future edit that breaks the dispatcher can't pass silently.

- [ ] **Step 1: Extend `_STATIC_ROUTES`**

In `src/earn_money/dashboard/server.py`, add four entries to the `_STATIC_ROUTES` dict (insertion order matches the existing style):

```python
_STATIC_ROUTES: dict[str, tuple[Path, str]] = {
    "/static/tokens.css":         (_STATIC / "tokens.css",         _CSS),
    "/static/dashboard.css":      (_STATIC / "dashboard.css",      _CSS),
    "/static/panels.css":         (_STATIC / "panels.css",         _CSS),
    "/static/probe.css":          (_STATIC / "probe.css",          _CSS),
    "/static/render.js":          (_STATIC / "render.js",          _JS),
    "/static/render_panels.js":   (_STATIC / "render_panels.js",   _JS),
    "/static/dashboard.js":       (_STATIC / "dashboard.js",       _JS),
    "/static/tabs.js":            (_STATIC / "tabs.js",            _JS),
    "/static/probe.js":           (_STATIC / "probe.js",           _JS),
    "/static/probe-render.js":    (_STATIC / "probe-render.js",    _JS),
}
```

- [ ] **Step 2: Update `do_GET` to route `/api/probe/stream`**

In `DashboardHandler.do_GET`, add the new `elif` between `"/api/status"` and `"/"`:

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

- [ ] **Step 3: Add `do_POST`**

Inside `DashboardHandler`, immediately after `do_GET`:

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

`traceback` is already imported at the top of the file (existing usage in `do_GET`). Confirm before merging.

- [ ] **Step 4: Add the `_drive_dispatch` helper**

Append to `tests/dashboard/test_probe_routes.py`:

```python
def _drive_dispatch(handler_cls, method: str, path: str, *, raw_body: bytes = b""):
    """Drive `do_POST` / `do_GET` (not the route methods directly) so
    the dispatcher wiring is exercised. Returns (status, body, handler)."""
    import io
    from unittest.mock import MagicMock

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
    # log_error is called from the do_POST exception path; stub it out
    # so the test doesn't write to stderr.
    h.log_error = MagicMock()

    if method == "POST":
        h.do_POST()
    elif method == "GET":
        h.do_GET()
    else:
        raise ValueError(method)

    status = (
        h.send_response.call_args.args[0]
        if h.send_response.call_args
        else h.send_error.call_args.args[0]
    )
    return status, wfile.getvalue(), h
```

- [ ] **Step 5: Write the failing test `test_do_post_dispatches_probe_start`**

```python
class TestDispatcher:
    def test_do_post_dispatches_probe_start(self, handler_factory):
        handler_cls, _paths = handler_factory
        raw = json.dumps({"base_url": "https://target.example.com"}).encode("utf-8")
        status, body, _h = _drive_dispatch(
            handler_cls, "POST", "/api/probe/start", raw_body=raw,
        )
        assert status == 200
        assert b"fakerun123" in body
```

Run; expect FAIL until `do_POST` is wired in Step 3.

- [ ] **Step 6: Write the failing test `test_do_get_dispatches_probe_stream`**

```python
    def test_do_get_dispatches_probe_stream(self, handler_factory):
        from earn_money.dashboard import server
        handler_cls, _paths = handler_factory
        server._PROBE_SLOT = _FakeRunner()
        status, body, _h = _drive_dispatch(
            handler_cls, "GET", "/api/probe/stream?run_id=fakerun123",
        )
        assert status == 200
        assert b"event: done" in body
```

Run; expect FAIL until the `/api/probe/stream` elif is added in Step 2.

- [ ] **Step 7: Write the failing test `test_do_post_unknown_path_returns_404`**

```python
    def test_do_post_unknown_path_returns_404(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, _body, _h = _drive_dispatch(
            handler_cls, "POST", "/api/does-not-exist", raw_body=b"{}",
        )
        assert status == 404
```

This pins the `do_POST` 404 path so a future edit can't introduce a route silently.

- [ ] **Step 8: Run the three dispatcher tests — expect all PASS**

```bash
uv run pytest tests/dashboard/test_probe_routes.py::TestDispatcher -v
```

(They pass because Steps 1–3 already wired the dispatcher. If any fails, the dispatcher edits are wrong — fix and re-run.)

Optional manual smoke (requires a running server — skip in CI):

```bash
touch RECON_ENABLED
uv run python -m earn_money.dashboard.server --root . &
SERVER_PID=$!
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"base_url":"https://nonexistent.example.com"}' \
  http://127.0.0.1:8080/api/probe/start
kill $SERVER_PID
```

Expected: 200 + `{"run_id":"…"}` (the runner will fail almost immediately because there's no real LLM env config, but the dispatcher reached the route).

- [ ] **Step 9: Run the dashboard test directory in full**

```bash
uv run pytest tests/dashboard/ -v
```

- [ ] **Step 10: Lint**

```bash
uv run ruff check src/earn_money/dashboard/server.py tests/dashboard/test_probe_routes.py
```

- [ ] **Step 11: Commit**

```bash
git add src/earn_money/dashboard/server.py tests/dashboard/test_probe_routes.py
git commit -m "feat(dashboard): wire do_GET/do_POST for probe routes + static assets"
```
