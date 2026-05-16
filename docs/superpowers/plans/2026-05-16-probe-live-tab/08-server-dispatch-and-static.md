# Task 8 — Wire dispatchers (`do_GET` / `do_POST`) and new static asset routes

**Spec section:** `docs/superpowers/specs/2026-05-16-probe-live-tab/06-server-routes.md` §"Wiring in `_STATIC_ROUTES`", §"Dispatcher delta in `do_GET`"

**Files:**
- Modify: `src/earn_money/dashboard/server.py`

The route methods exist (Tasks 6 and 7) but no HTTP request reaches them yet — the handler's `do_GET` doesn't know about `/api/probe/stream`, and there is no `do_POST` at all. This task wires both. Static assets for the new JS/CSS files are also registered so the existing read-once / cache pattern serves them.

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

- [ ] **Step 4: Manual smoke (no automated test added in this task)**

The dispatcher wiring is verified end-to-end by the existing `TestStartRoute` / `TestStreamRoute` tests being reachable. Run them through `_invoke_get` / `_invoke_post` once more to confirm nothing in the wiring regressed:

```bash
uv run pytest tests/dashboard/test_probe_routes.py -v
```

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

- [ ] **Step 5: Run the dashboard test directory in full**

```bash
uv run pytest tests/dashboard/ -v
```

- [ ] **Step 6: Lint**

```bash
uv run ruff check src/earn_money/dashboard/server.py
```

- [ ] **Step 7: Commit**

```bash
git add src/earn_money/dashboard/server.py
git commit -m "feat(dashboard): wire do_GET/do_POST for probe routes + static assets"
```
