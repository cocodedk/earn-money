---
tier: FAST
depends_on:
  - 02-plateau-baseline
files:
  creates:
    - backend/apps/agent/tests/test_controller_dispatch.py
  modifies:
    - backend/apps/agent/controller_dispatch.py
  deletes: []
exports: []
imports: []
allow_extra_files: false
---

### Task 6: Pass route_paths through dispatch to plateau

**Files:**
- Modify: `backend/apps/agent/controller_dispatch.py`
- Create/Modify: `backend/apps/agent/tests/test_controller_dispatch.py`

- [ ] **Step 1: Add failing dispatch regression test**

Add or update the existing `_execute_browser_action` test in `test_controller_dispatch.py` so the fake browser observation includes two discovered routes and the fake plateau object is a mock. The assertion must verify the route paths are forwarded, not only the count:

```python
expected_element_count = 4  # one fake link, button, input, and form
ctrl.plateau.record_turn.assert_called_once_with(
    new_routes=2,
    new_elements=expected_element_count,
    route_paths=["/login", "/#!/score-board"],
)
```

If the existing dispatch tests use positional assertions, update them to keyword assertions so a future argument-order change does not hide a missing `route_paths` value.

- [ ] **Step 2: Update _execute_browser_action to pass route_paths**

In `controller_dispatch.py`, modify `_execute_browser_action` to pass discovered route paths to `record_turn`:

```python
routes = list(obs.discovered.routes)
new_routes = len(routes)
route_paths = [r.path for r in routes if getattr(r, "path", None)]
new_elements = (
    len(obs.elements.links) + len(obs.elements.buttons)
    + len(obs.elements.inputs) + len(obs.elements.forms)
)
ctrl.plateau.record_turn(
    new_routes=new_routes,
    new_elements=new_elements,
    route_paths=route_paths,
)
```

Use only the current observation's `obs.discovered.routes`. Do not pass all session-known routes; plateau baseline filtering depends on seeing routes discovered by this browser action.

- [ ] **Step 3: Run dispatch and full test suites**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_controller_dispatch.py -v`
Expected: ALL PASS

Run: `docker compose exec backend python -m pytest apps/agent/tests/ -v --tb=short`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add backend/apps/agent/controller_dispatch.py backend/apps/agent/tests/test_controller_dispatch.py
git commit -m "feat(agent): pass route_paths to plateau detector for baseline filtering"
```
