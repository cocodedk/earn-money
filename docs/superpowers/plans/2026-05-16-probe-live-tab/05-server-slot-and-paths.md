# Task 5 — Server module state: `_PROBE_SLOT`, lock, `_clear_probe_slot`, `_paths` class attr

**Spec section:** `docs/superpowers/specs/2026-05-16-probe-live-tab/06-server-routes.md` §"New module state", §"Slot assignment", §"Handler state: `paths`"

**Files:**
- Modify: `src/earn_money/dashboard/server.py`

This task wires the foundations the next two tasks (start route, stream route) depend on. No new route handlers yet — just the module-level slot, the lock, the callback, and the `_paths` class attribute on the handler.

- [ ] **Step 1: Read the current `server.py` and locate the insertion points**

Skim `src/earn_money/dashboard/server.py`. Identify:
- Import block (lines ~17–26)
- `_STATIC_ROUTES` map (lines ~36–43)
- `_make_handler` factory (lines ~70–126)
- `DashboardHandler` class body (lines ~82–125)

- [ ] **Step 2: Extend the top-level import block**

Add these to the existing import block at the top of `src/earn_money/dashboard/server.py` (alongside `import json`, `import argparse`, etc.). Ruff `E402` will flag any module-level import below the first top-level statement, so these must live with the other imports — **not** further down beside `_STATIC_ROUTES`:

```python
import threading
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

if TYPE_CHECKING:
    from earn_money.dashboard.probe_runner import ProbeRunner
```

`TYPE_CHECKING` keeps the `ProbeRunner` import out of the runtime import graph (no cycle) while still letting `mypy --strict` see the real type. The `urlparse`/`parse_qs` imports are used by Tasks 6 and 7; staging them here keeps the diff for those tasks minimal.

- [ ] **Step 3: Add module-level slot + lock + clear-callback above `build()`**

Insert after the existing `_STATIC_ROUTES` block (this is module state, not imports, so it lives in the body of the module):

```python
# One-at-a-time probe runner — module-level slot under a lock so two
# near-simultaneous POST /api/probe/start handler threads race safely.
# IMPORTANT: the slot is NOT auto-cleared when a runner finishes. The
# slot acts as "the most recent runner" (running or done) so a late-
# arriving EventSource can still drain the terminal `done` /
# `probe_error` event. The slot is replaced when the next start
# overwrites it (see Task 6). See 04-probe-runner-class.md §"_run_safe"
# for the rationale.
_PROBE_SLOT: "ProbeRunner | None" = None
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
```

The forward-ref string `"ProbeRunner | None"` is the type the slot holds; mypy reads it through the `TYPE_CHECKING` guard added in Step 2.

- [ ] **Step 4: Add `_paths` class attribute on the handler**

Inside `_make_handler`, immediately before the existing `timeout = 5.0` line, add:

```python
        # Bake `paths` onto the class so new route methods can read
        # self._paths.root for relative-path resolution. The existing
        # _serve_status keeps reading the closure variable.
        _paths = paths
```

The factory's class body now begins:

```python
    class DashboardHandler(BaseHTTPRequestHandler):
        _paths = paths
        timeout = 5.0
        # … rest unchanged
```

- [ ] **Step 5: Run the existing dashboard tests to confirm no regression**

```bash
uv run pytest tests/dashboard/ -v
```

Expected: all existing dashboard tests still pass. No new test fails because the new state isn't reached by any route yet.

- [ ] **Step 6: Lint**

```bash
uv run ruff check src/earn_money/dashboard/server.py
```

Expected: clean. If ruff flags `E402: module level import not at top of file`, an import slipped below `_STATIC_ROUTES`; move it back to the import block at the top per Step 2.

- [ ] **Step 7: Commit**

```bash
git add src/earn_money/dashboard/server.py
git commit -m "feat(dashboard): probe slot + lock + _paths handler attr (no routes yet)"
```
