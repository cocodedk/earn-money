# Task 2 — HTTP server

**Files:** Create `src/earn_money/dashboard/server.py` +
`tests/dashboard/test_server.py`.

stdlib **`http.server.ThreadingHTTPServer`** + custom
`BaseHTTPRequestHandler`. Two routes:
- `GET /` → serve `templates/index.html` (200 + `text/html`)
- `GET /api/status` → `aggregator.build_status(paths)` as JSON
- anything else → 404

Bind hardcoded to `127.0.0.1`. No `--host` flag — non-loopback is
unreachable by construction.

## TDD

- [ ] **1. Failing test — `/api/status` returns JSON with the wiring**

```python
def test_status_endpoint_returns_json(tmp_repo: Path) -> None:
    paths = engine_paths(tmp_repo)
    httpd = server.build(paths, port=0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_address[1]
    try:
        with httpx.Client() as c:
            r = c.get(f"http://127.0.0.1:{port}/api/status", timeout=2)
    finally:
        httpd.shutdown()
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert "programs" in r.json() and "across" in r.json()
```

- [ ] **2. Failing test — `/` returns HTML 200** with the literal
  `<title>earn-money dashboard</title>` in the body.

- [ ] **3. Failing test — unknown path returns 404.**

- [ ] **4. Failing test — concurrent GETs both complete**
  (ThreadingHTTPServer): fire two `/api/status` requests in
  parallel via `concurrent.futures.ThreadPoolExecutor`; assert
  both return 200. Guards against accidental regression to
  single-threaded HTTPServer.

- [ ] **5. Failing test — bind host is exactly `127.0.0.1`**:
  assert `httpd.server_address[0] == "127.0.0.1"` after `build()`.

- [ ] **6. Implement `server.py`** (~100 lines):
  - `build(paths, port) -> ThreadingHTTPServer` factory
  - `DashboardHandler(BaseHTTPRequestHandler)` reads `paths` via
    closure (factory-built subclass; standard pattern for injecting
    state into BaseHTTPRequestHandler subclasses).
  - `main(argv)` CLI: `--root`, `--port` (default 8080). No `--host`.

- [ ] **7. `make smoke`** green.

- [ ] **8. Commit + /simplify pass.**
