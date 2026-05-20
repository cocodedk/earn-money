# Task 5 — Integration test

**Files:** Add `tests/dashboard/test_e2e.py`.

End-to-end: spin up the real server on an ephemeral port against a
seeded `tmp_repo`, fetch both endpoints with `httpx`, parse the JSON
+ the HTML, and assert that key strings/keys from the aggregator flow
all the way through to the response.

## TDD

- [ ] **1. Failing test — full request cycle**

```python
import threading, httpx
from earn_money.dashboard import server
from tests.triage.conftest import engine_paths

def test_e2e_wiring(tmp_repo):
    """Wiring-only: aggregator+server+html template path all connect.
    Per-layer behavior is covered by aggregator and server unit tests;
    don't duplicate the data assertions here."""
    paths = engine_paths(tmp_repo)
    httpd = server.build(paths, port=0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_address[1]
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}") as c:
            api = c.get("/api/status", timeout=2)
            html = c.get("/", timeout=2)
    finally:
        httpd.shutdown()
    assert api.status_code == 200
    assert api.headers["content-type"].startswith("application/json")
    assert "programs" in api.json() and "across" in api.json()
    assert html.status_code == 200
    assert html.headers["content-type"].startswith("text/html")
    assert "<title>earn-money dashboard</title>" in html.text
```

- [ ] **2. Run, expect FAIL** until Tasks 1-3 land.

- [ ] **3. After Tasks 1-3 are merged: re-run, expect PASS.**

- [ ] **4. `make smoke`** green.

- [ ] **5. Commit** as `test(dashboard): e2e — real http server + aggregator + html`.

- [ ] **6. `/simplify`** pass.

## Why one test, not a matrix

The aggregator already has its own unit tests covering shape and
edge cases (FROZEN, success criterion). The server has its own
route tests. This e2e exists to catch wiring bugs (e.g., the html
template path being wrong, or `--root` not propagating). One green
test that exercises both endpoints is enough; more would just
duplicate the layer-specific tests.
