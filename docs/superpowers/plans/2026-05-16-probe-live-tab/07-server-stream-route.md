# Task 7 — `GET /api/probe/stream?run_id=…` (SSE)

**Spec section:** `docs/superpowers/specs/2026-05-16-probe-live-tab/06-server-routes.md` §"GET /api/probe/stream", §"Notes on the wire format"

**Files:**
- Modify: `src/earn_money/dashboard/server.py`
- Modify: `tests/dashboard/test_probe_routes.py`

This task adds the stream route. The dispatcher wiring lands in Task 8 — until then, tests invoke `_serve_probe_stream` directly via the same shim used in Task 6.

- [ ] **Step 1: Write the failing test for 400-on-missing-run-id**

Append to `tests/dashboard/test_probe_routes.py` (the `from typing import NamedTuple` import goes near the top of the file alongside the existing imports added in Task 6):

```python
from typing import NamedTuple


class DrivenGet(NamedTuple):
    """Result of `_invoke_get` — exposes the handler too so tests can
    inspect `send_header.call_args_list` and so callers can supply a
    custom wfile that raises (e.g. BrokenPipeError) mid-stream."""
    status: int
    body: bytes
    handler: object


def _invoke_get(handler_cls, path: str, *, wfile=None) -> DrivenGet:
    """Drive GET on the stream route directly (bypassing do_GET). For
    the dispatcher-coverage tests in Task 8, use `_drive_dispatch`
    instead — that path exercises do_GET / do_POST."""
    import io
    from unittest.mock import MagicMock

    if wfile is None:
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
    body = wfile.getvalue() if hasattr(wfile, "getvalue") else b""
    return DrivenGet(status, body, h)


class TestStreamRoute:
    def test_returns_400_when_run_id_query_param_missing(self, handler_factory):
        handler_cls, _paths = handler_factory
        result = _invoke_get(handler_cls, "/api/probe/stream")
        assert result.status == 400
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

Implement each test below as a method on `TestStreamRoute`. **Never commit a test body that is only `pass` or `...`** — both silently pass. For each test, install a `_FakeRunner` in `server._PROBE_SLOT` first (the autouse fixture from Task 6 clears it between tests), wire `_FakeRunner.events` to yield the canned sequence the test needs, call `_invoke_get(handler_cls, "/api/probe/stream?run_id=fakerun123")`, then assert on `result.status` / `result.body` / `result.handler.send_header.call_args_list`. For the disconnect test, pass a custom `wfile=` that raises:

- `test_returns_404_when_no_probe_running` — leave `_PROBE_SLOT = None`. Assert `result.status == 404`.
- `test_returns_410_when_run_id_does_not_match_active_runner` — install a runner with `run_id() == "fakerun123"`, call with `?run_id=otherid`. Assert `result.status == 410`.
- `test_emits_event_stream_content_type` — happy path with `events()` yielding just a `done`. Extract `.args` from each `call()` in `send_header.call_args_list` before checking membership: `headers = [c.args for c in result.handler.send_header.call_args_list]; assert ("Content-Type", "text/event-stream; charset=utf-8") in headers`. (`call_args_list` items are `_Call` objects, not bare tuples — comparing the tuple directly to `_Call` will mis-match.)
- `test_sends_retry_zero_header_frame` — happy path. Assert `result.body.startswith(b"retry: 0\n\n")`.
- `test_frames_turn_event_correctly` — `events()` yields `[{"event":"turn","data":{"turn":1,"stage":"action_pending"}}, {"event":"done","data":{...}}]`. Assert `result.body` contains `b"event: turn\ndata: " + json.dumps({"turn":1,"stage":"action_pending"}).encode() + b"\n\n"`.
- `test_frames_finding_event_correctly` — `events()` yields `[{"event":"finding","data":{"turn":1,"kind":"candidate","type":"idor"}}, {"event":"done","data":{...}}]`. Assert `result.body` contains the matching `event: finding\ndata: {...}\n\n` frame.
- `test_closes_response_after_done` — `events()` yields `[{"event":"done","data":{...}}, {"event":"turn","data":{...}}]`. Assert `result.body` contains the `done` frame but NOT the subsequent `turn` frame (the route returned after `done`).
- `test_closes_response_after_probe_error` — same shape with `probe_error` instead of `done`. Assert no later frames in `result.body`.
- `test_keepalive_yields_comment_frame` — `events()` yields `[{"event":"_keepalive","data":{}}, {"event":"done","data":{...}}]`. Assert `b":\n\n"` is in `result.body`.
- `test_client_disconnect_mid_stream_does_not_kill_runner` — build a `BytesIO` subclass whose `write` raises `BrokenPipeError` on the SECOND call (the first write is the `retry: 0` frame, the second is the event); pass via `_invoke_get(..., wfile=fake_wfile)`. Use a `_FakeRunner` whose `events()` yields two frames. Assert `server._PROBE_SLOT` is still the same runner instance after the handler returns.
- `test_client_disconnect_on_first_write_does_not_kill_runner` — same shape, but configure `write` to raise on the FIRST call (the `retry: 0` frame, before any event is read from `events()`). This pins the requirement that the route's `try` block must cover the initial write, not just the per-event writes. Assert `server._PROBE_SLOT` is still the same runner instance after the handler returns.

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
