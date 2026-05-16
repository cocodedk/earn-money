# Task 7 — `GET /api/probe/stream?run_id=…` (SSE)

**Spec section:** `docs/superpowers/specs/2026-05-16-probe-live-tab/06-server-routes.md` §"GET /api/probe/stream", §"Notes on the wire format"

**Files:**
- Modify: `src/earn_money/dashboard/server.py`
- Modify: `tests/dashboard/test_probe_routes.py`

This task adds the stream route. The dispatcher wiring lands in Task 8 — until then, tests invoke `_serve_probe_stream` directly via the same shim used in Task 6.

- [ ] **Step 1: Write the failing test for 400-on-missing-run-id**

Append to `tests/dashboard/test_probe_routes.py`:

```python
def _invoke_get(handler_cls, path: str) -> tuple[int, bytes]:
    """Convenience: drive GET on the stream route through the shared
    `_drive` helper defined in tests/dashboard/test_probe_routes.py
    (Task 6 introduces it). Returns (status, raw_wfile_bytes) — the
    stream route writes SSE frames, not JSON, so callers inspect bytes
    directly rather than the parsed-body dict."""
    import io
    from unittest.mock import MagicMock
    wfile = io.BytesIO()
    h = handler_cls.__new__(handler_cls)
    h.rfile = io.BytesIO(b"")
    h.wfile = wfile
    h.command = "GET"
    h.path = path
    h.request_version = "HTTP/1.1"
    h.headers = MagicMock()
    h.send_response = MagicMock()
    h.send_error = MagicMock()
    h.send_header = MagicMock()
    h.end_headers = MagicMock()
    h._serve_probe_stream()
    status = (h.send_response.call_args.args[0]
              if h.send_response.call_args else
              h.send_error.call_args.args[0])
    return status, wfile.getvalue()


class TestStreamRoute:
    def test_returns_400_when_run_id_query_param_missing(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, _ = _invoke_get(handler_cls, "/api/probe/stream")
        assert status == 400
```

- [ ] **Step 2: Run — expect FAIL (`_serve_probe_stream` doesn't exist)**

```bash
uv run pytest tests/dashboard/test_probe_routes.py::TestStreamRoute::test_returns_400_when_run_id_query_param_missing -v
```

- [ ] **Step 3: Implement `_serve_probe_stream`**

Inside `DashboardHandler` (next to `_serve_probe_start`):

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
```

- [ ] **Step 4: Run the test — expect PASS**

```bash
uv run pytest tests/dashboard/test_probe_routes.py::TestStreamRoute::test_returns_400_when_run_id_query_param_missing -v
```

- [ ] **Step 5: Add the remaining stream-route tests from spec 12**

Implement each test below as a method on `TestStreamRoute`. **Never commit a test body that is only `pass` or `...`** — both silently pass. For each test, install a `_FakeRunner` in `server._PROBE_SLOT` first (the autouse fixture from Task 6 clears it between tests), wire `_FakeRunner.events` to yield the canned sequence the test needs, call `_invoke_get(handler_cls, "/api/probe/stream?run_id=fakerun123")`, then assert on the bytes written to `wfile` or on the status:

- `test_returns_404_when_no_probe_running` — leave `_PROBE_SLOT = None`. Assert `status == 404`.
- `test_returns_410_when_run_id_does_not_match_active_runner` — install a runner with `run_id() == "fakerun123"`, call with `?run_id=otherid`. Assert `status == 410`.
- `test_emits_event_stream_content_type` — happy path with `events()` yielding just a `done`. Assert `h.send_header.call_args_list` contains `("Content-Type", "text/event-stream; charset=utf-8")`.
- `test_sends_retry_zero_header_frame` — happy path. Assert the bytes written start with `b"retry: 0\n\n"`.
- `test_frames_turn_event_correctly` — `events()` yields `[{"event":"turn","data":{"turn":1,"stage":"action_pending"}}, {"event":"done","data":{...}}]`. Assert the written bytes contain `b"event: turn\ndata: " + json.dumps({"turn":1,"stage":"action_pending"}).encode() + b"\n\n"`.
- `test_frames_finding_event_correctly` — `events()` yields `[{"event":"finding","data":{"turn":1,"kind":"candidate","type":"idor"}}, {"event":"done","data":{...}}]`. Assert the written bytes contain the matching `event: finding\ndata: {...}\n\n` frame.
- `test_closes_response_after_done` — `events()` yields `[{"event":"done","data":{...}}, {"event":"turn","data":{...}}]`. Assert the response body contains the `done` frame but NOT the subsequent `turn` frame (the route returned after `done`).
- `test_closes_response_after_probe_error` — same shape with `probe_error` instead of `done`. Assert no later frames in the response body.
- `test_keepalive_yields_comment_frame` — `events()` yields `[{"event":"_keepalive","data":{}}, {"event":"done","data":{...}}]`. Assert the written bytes contain `b":\n\n"`.
- `test_client_disconnect_does_not_kill_runner` — configure the writer to raise `BrokenPipeError` on the second `wfile.write`. Use a real `_FakeRunner` whose `events()` yields two frames; assert the runner instance is still in `_PROBE_SLOT` after the handler returns (i.e. the disconnect did not call `stop()` or clear the slot).

- [ ] **Step 6: Run the whole `TestStreamRoute` class — expect all PASS**

```bash
uv run pytest tests/dashboard/test_probe_routes.py::TestStreamRoute -v
```

- [ ] **Step 7: Run the full test suite**

```bash
uv run pytest -q
```

- [ ] **Step 8: Lint**

```bash
uv run ruff check src/earn_money/dashboard/server.py tests/dashboard/test_probe_routes.py
```

- [ ] **Step 9: Commit**

```bash
git add src/earn_money/dashboard/server.py tests/dashboard/test_probe_routes.py
git commit -m "feat(dashboard): GET /api/probe/stream SSE with run_id validation"
```
