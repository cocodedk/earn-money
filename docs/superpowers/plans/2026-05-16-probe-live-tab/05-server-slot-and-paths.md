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

- [ ] **Step 2: Add module-level state above `build()`**

Insert after the existing `_STATIC_ROUTES` block:

```python
import threading  # if not already imported at top — verify and move up if so
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from earn_money.dashboard.probe_runner import ProbeRunner

# One-at-a-time probe runner — module-level slot under a lock so two
# near-simultaneous POST /api/probe/start handler threads race safely.
_PROBE_SLOT: "ProbeRunner | None" = None
_PROBE_SLOT_LOCK = threading.Lock()


def _clear_probe_slot(run_id: str) -> None:
    """Callback handed to ProbeRunner; clears the module slot in the
    runner's `finally`. Lives in server.py because that's where the slot
    is — the runner never imports from server.py."""
    global _PROBE_SLOT
    with _PROBE_SLOT_LOCK:
        if _PROBE_SLOT is not None and _PROBE_SLOT.run_id() == run_id:
            _PROBE_SLOT = None
```

`TYPE_CHECKING` keeps the `ProbeRunner` import out of the runtime import graph (no cycle) while still letting `mypy --strict` see the real type. The forward-ref string `"ProbeRunner | None"` is the type the slot holds.

- [ ] **Step 3: Add `_paths` class attribute on the handler**

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

- [ ] **Step 4: Confirm imports**

At the top of `server.py`, ensure both of these are present (add if missing):

```python
import threading
from urllib.parse import parse_qs, urlparse
```

(The `urlparse`/`parse_qs` imports will be used by the next task; including them here keeps the diff for Task 6 minimal.)

- [ ] **Step 5: Run the existing dashboard tests to confirm no regression**

```bash
uv run pytest tests/dashboard/ -v
```

Expected: all existing dashboard tests still pass. No new test fails because the new state isn't reached by any route yet.

- [ ] **Step 6: Lint**

```bash
uv run ruff check src/earn_money/dashboard/server.py
```

- [ ] **Step 7: Commit**

```bash
git add src/earn_money/dashboard/server.py
git commit -m "feat(dashboard): probe slot + lock + _paths handler attr (no routes yet)"
```
