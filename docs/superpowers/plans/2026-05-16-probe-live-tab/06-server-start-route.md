# Task 6 — `POST /api/probe/start` route

**Spec section:** `docs/superpowers/specs/2026-05-16-probe-live-tab/06-server-routes.md` §"POST /api/probe/start"

**Files:**
- Modify: `src/earn_money/dashboard/server.py`
- Modify: `tests/dashboard/test_probe_routes.py` (created during this task if absent)

This task adds the start route, all its validations, and the matching tests. The dispatcher wiring (so `POST` routes actually arrive at this handler) lands in Task 8.

- [ ] **Step 1: Create the test file scaffold with the happiest-path test**

Create `tests/dashboard/test_probe_routes.py`:

```python
"""Tests for POST /api/probe/start and GET /api/probe/stream."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from earn_money import config


class _FakeRunner:
    """Test double for ProbeRunner — same surface, no thread, no provider."""
    def __init__(self, *_args, on_finished=None, **_kwargs):
        self._id = "fakerun123"
        self._running = True
        self._on_finished = on_finished
    def start(self) -> str:
        return self._id
    def run_id(self) -> str:
        return self._id
    def is_running(self) -> bool:
        return self._running
    def events(self):
        yield {"event": "done", "data": {"turns": 0, "stop_reason": "done",
                                          "candidates_count": 0,
                                          "verified_count": 0,
                                          "denials_count": 0}}


@pytest.fixture()
def tmp_root(tmp_path: Path) -> Path:
    (tmp_path / "RECON_ENABLED").touch()
    return tmp_path


@pytest.fixture(autouse=True)
def _reset_probe_slot():
    """Ensure no probe slot leaks between tests. The handler installs
    a _FakeRunner under server._PROBE_SLOT on a successful start; without
    this fixture a subsequent test would see a stale 409 from a slot the
    previous test left in place."""
    from earn_money.dashboard import server
    server._PROBE_SLOT = None
    yield
    server._PROBE_SLOT = None


@pytest.fixture()
def handler_factory(tmp_root: Path):
    from earn_money.dashboard import server
    paths = config.Paths.from_root(tmp_root)
    # Patch ProbeRunner in the server module to our fake.
    with patch.object(server, "ProbeRunner", _FakeRunner, create=True):
        index_html = b"<!doctype html><title>t</title>"
        static = {}
        yield server._make_handler(paths, index_html, static), paths


def _invoke_post_raw(handler_cls, path: str, raw: bytes) -> tuple[int, dict]:
    """Drive _serve_probe_start with arbitrary request bytes. Use this
    for the malformed-JSON test where the body intentionally isn't a
    serialisable dict."""
    import io
    from unittest.mock import MagicMock
    wfile = io.BytesIO()
    h = handler_cls.__new__(handler_cls)
    h.rfile = io.BytesIO(raw)
    h.wfile = wfile
    h.command = "POST"
    h.path = path
    h.request_version = "HTTP/1.1"
    h.headers = MagicMock()
    h.headers.get = lambda k, default=None: {
        "Content-Length": str(len(raw)),
        "Content-Type": "application/json",
    }.get(k, default)
    h.send_response = MagicMock()
    h.send_header = MagicMock()
    h.end_headers = MagicMock()
    h._serve_probe_start()
    status = h.send_response.call_args.args[0] if h.send_response.call_args else 0
    body_bytes = wfile.getvalue()
    body_json = json.loads(body_bytes.split(b"\r\n\r\n", 1)[-1] or b"{}")
    return status, body_json


def _invoke_post(handler_cls, path: str, body: dict) -> tuple[int, dict]:
    """Drive the BaseHTTPRequestHandler without sockets using a synthetic
    wfile/rfile, then parse the response status and JSON body."""
    import io
    raw = json.dumps(body).encode("utf-8")
    rfile = io.BytesIO(
        f"POST {path} HTTP/1.1\r\nContent-Length: {len(raw)}\r\nContent-Type: application/json\r\n\r\n".encode()
        + raw
    )
    wfile = io.BytesIO()

    class _Req:
        rfile = rfile
        wfile = wfile
        server = MagicMock()
        client_address = ("127.0.0.1", 0)
    h = handler_cls.__new__(handler_cls)
    h.rfile = rfile
    h.wfile = wfile
    h.command = "POST"
    h.path = path
    h.request_version = "HTTP/1.1"
    h.headers = MagicMock()
    h.headers.get = lambda k, default=None: {
        "Content-Length": str(len(raw)),
        "Content-Type": "application/json",
    }.get(k, default)
    # We bypass send_response's logging by stubbing it out.
    h.send_response = MagicMock()
    h.send_header = MagicMock()
    h.end_headers = MagicMock()
    h._serve_probe_start()
    status = h.send_response.call_args.args[0] if h.send_response.call_args else 0
    body_bytes = wfile.getvalue()
    body_json = json.loads(body_bytes.split(b"\r\n\r\n", 1)[-1] or b"{}")
    return status, body_json


class TestStartRoute:
    def test_returns_200_with_run_id_on_success(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post(handler_cls, "/api/probe/start", {
            "base_url": "https://target.example.com",
        })
        assert status == 200
        assert body == {"run_id": "fakerun123"}
```

(Note: the `_invoke_post` shim is testing-only and not production code. It bypasses the dispatcher because Task 8 hasn't landed yet; it calls `_serve_probe_start` directly. After Task 8, additional tests can drive the full `do_POST` path.)

- [ ] **Step 2: Run the test — expect FAIL (`_serve_probe_start` doesn't exist)**

```bash
uv run pytest tests/dashboard/test_probe_routes.py::TestStartRoute::test_returns_200_with_run_id_on_success -v
```

- [ ] **Step 3: Implement `_serve_probe_start`**

Inside `DashboardHandler` in `_make_handler`, add the import of `ProbeRunner` and `flags`. At the top of `server.py`:

```python
from earn_money import config, flags
from earn_money.dashboard.aggregator import ...  # (existing)
from earn_money.dashboard.probe_runner import ProbeRunner
```

Add helper methods inside `DashboardHandler`:

```python
        def _read_body(self) -> bytes:
            length = int(self.headers.get("Content-Length") or "0")
            return self.rfile.read(length) if length > 0 else b""

        def _send_json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

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
                return self._send_json(400, {"error":
                    f"base_url scheme must be http or https, got {parsed.scheme!r}"})
            if parsed.username or parsed.password:
                return self._send_json(400, {"error":
                    "base_url must not contain userinfo (user:pass@)"})
            if not parsed.hostname:
                return self._send_json(400, {"error": "base_url missing host"})

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
                    return self._send_json(400, {"error":
                        "max_turns must be an int between 1 and 50"})

            if roe_path is not None and not roe_path.exists():
                return self._send_json(400, {"error":
                    f"RoE profile not found: {roe_path}"})

            try:
                flags.require_recon_enabled(self._paths)
                if program:
                    flags.require_program_not_frozen(self._paths, platform, program)
            except flags.ReconDisabled as e:
                return self._send_json(403, {"error": str(e)})
            except flags.ProgramFrozen as e:
                return self._send_json(403, {"error": str(e)})

            global _PROBE_SLOT
            with _PROBE_SLOT_LOCK:
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

                _PROBE_SLOT = runner
                try:
                    run_id = runner.start()
                except Exception:
                    _PROBE_SLOT = None
                    raise

            self._send_json(200, {"run_id": run_id})
```

Add `Path` to the top imports too:

```python
from pathlib import Path
```

(verify it's not already there; if it is, this is a no-op).

- [ ] **Step 4: Run the happiest-path test — expect PASS**

```bash
uv run pytest tests/dashboard/test_probe_routes.py::TestStartRoute::test_returns_200_with_run_id_on_success -v
```

- [ ] **Step 5: Add the validation-edge tests (one at a time, TDD)**

Implement each test below as a method on `TestStartRoute`. Each one must contain real assertions — **never commit a test body that is only `pass` or `...`**, since both silently pass. The autouse `_reset_probe_slot` fixture clears `_PROBE_SLOT` between tests, so the 409 case must explicitly install a runner. The malformed-JSON case uses `_invoke_post_raw(handler_cls, "/api/probe/start", b"{not-json")`. Names taken verbatim from spec 12-tests.md; behaviour spec next to each name:

- `test_returns_400_when_base_url_missing` — POST `{}`. Assert `status == 400` and `"base_url required" in body["error"]`.
- `test_returns_400_when_body_is_invalid_json` — call `_invoke_post_raw(handler_cls, "/api/probe/start", b"{not-json")`. Assert `status == 400` and `"invalid JSON body" in body["error"]`.
- `test_returns_400_when_roe_profile_path_does_not_exist` — POST `{base_url, roe_profile: "/nope.yaml"}`. Assert `status == 400` and `"RoE profile not found" in body["error"]`.
- `test_returns_400_when_base_url_scheme_not_http` — POST `{base_url: "ftp://x.com"}`. Assert `status == 400` and `"scheme" in body["error"]`.
- `test_returns_400_when_base_url_has_userinfo` — POST `{base_url: "https://u:p@x.com"}`. Assert `status == 400` and `"userinfo" in body["error"]`.
- `test_returns_400_when_base_url_missing_host` — POST `{base_url: "https://"}`. Assert `status == 400` and `"missing host" in body["error"]`.
- `test_returns_400_when_max_turns_out_of_range` — POST `{base_url, max_turns: 0}`. Assert `status == 400` and `"max_turns" in body["error"]`. Repeat with `max_turns: 51`.
- `test_empty_string_roe_profile_treated_as_null` — POST `{base_url, roe_profile: ""}`. Assert `status == 200` (treated as null; safe-default profile is used).
- `test_relative_roe_path_resolved_against_root` — create `tmp_root/roe/test.yaml`, POST `{base_url, roe_profile: "roe/test.yaml"}`. Assert `status == 200`. (Confirms the path was resolved against `--root`, not cwd.)
- `test_empty_platform_defaults_to_local` — POST `{base_url, platform: ""}`. Assert `status == 200`.
- `test_null_platform_defaults_to_local` — POST `{base_url, platform: None}`. Assert `status == 200`.
- `test_empty_program_treated_as_none` — POST `{base_url, program: ""}`. Assert `status == 200` (no frozen-gate call).
- `test_returns_400_when_platform_is_false` — POST `{base_url, platform: False}`. Assert `status == 400` and `"platform must be a string" in body["error"]`.
- `test_returns_400_when_platform_is_zero` — POST `{base_url, platform: 0}`. Assert `status == 400` and `"platform must be a string" in body["error"]`.
- `test_returns_400_when_platform_is_list` — POST `{base_url, platform: []}`. Assert `status == 400` and `"platform must be a string" in body["error"]`.
- `test_returns_400_when_program_is_list` — POST `{base_url, program: []}`. Assert `status == 400` and `"program must be a string" in body["error"]`.
- `test_returns_400_when_program_is_false` — POST `{base_url, program: False}`. Assert `status == 400` and `"program must be a string" in body["error"]`.
- `test_returns_403_when_recon_enabled_absent` — use `tmp_path` (no `RECON_ENABLED` touched). Build a fresh handler via `_make_handler` and POST. Assert `status == 403` and `"RECON_ENABLED" in body["error"]`.
- `test_returns_403_when_program_frozen` — `flags.freeze_program(_paths, "local", "frozen-prog", reason="test")`, then POST `{base_url, program: "frozen-prog"}`. Assert `status == 403` and `"frozen" in body["error"]`.
- `test_skips_frozen_check_when_no_program_supplied` — freeze a program, but POST without `program`. Assert `status == 200`.
- `test_returns_409_when_another_probe_is_running` — POST once (succeeds with 200), POST again. Assert second call `status == 409` and `body["error"] == "another probe is running"`.
- `test_409_payload_includes_existing_run_id` — same flow as above. Assert `body["run_id"] == "fakerun123"` (the first runner's id).
- `test_returns_500_when_runner_construction_raises` — patch `server.ProbeRunner` to raise on `__init__`. POST. Assert `status == 500` and `"runner init failed" in body["error"]`.
- `test_slot_clears_after_runner_finishes_via_callback` — POST (succeeds). Then call `server._clear_probe_slot(server._PROBE_SLOT.run_id())`. Assert `server._PROBE_SLOT is None`.

- [ ] **Step 6: Run the whole `TestStartRoute` class — expect all PASS**

```bash
uv run pytest tests/dashboard/test_probe_routes.py::TestStartRoute -v
```

- [ ] **Step 7: Run the full test suite to confirm no regression**

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
git commit -m "feat(dashboard): POST /api/probe/start route with full validation"
```
