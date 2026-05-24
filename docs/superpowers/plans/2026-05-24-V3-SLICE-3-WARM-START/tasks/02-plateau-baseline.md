---
tier: FAST
depends_on: []
files:
  creates: []
  modifies:
    - backend/apps/agent/plateau.py
    - backend/apps/agent/tests/test_plateau.py
  deletes: []
exports: []
imports: []
allow_extra_files: false
---

### Task 2: PlateauDetector baseline routes

**Files:**
- Modify: `backend/apps/agent/plateau.py`
- Modify: `backend/apps/agent/tests/test_plateau.py`

- [ ] **Step 1: Write failing tests for baseline filtering**

Add to `test_plateau.py`:

```python
class TestBaselineRoutes:
    def test_known_route_does_not_reset_counter(self):
        pd = PlateauDetector(
            max_turns_without_new_route=2,
            known_routes={"/login", "/admin"},
        )
        pd.record_turn(new_routes=1, new_elements=0, route_paths=["/login"])
        pd.record_turn(new_routes=0, new_elements=0, route_paths=[])
        assert pd.is_plateaued() is True

    def test_novel_route_resets_counter(self):
        pd = PlateauDetector(
            max_turns_without_new_route=2,
            known_routes={"/login"},
        )
        pd.record_turn(new_routes=1, new_elements=0, route_paths=["/new-page"])
        pd.record_turn(new_routes=0, new_elements=0, route_paths=[])
        assert pd.is_plateaued() is False

    def test_no_baseline_means_all_routes_novel(self):
        pd = PlateauDetector(max_turns_without_new_route=2)
        pd.record_turn(new_routes=1, new_elements=0, route_paths=["/login"])
        pd.record_turn(new_routes=0, new_elements=0, route_paths=[])
        assert pd.is_plateaued() is False

    def test_mixed_known_and_novel(self):
        pd = PlateauDetector(
            max_turns_without_new_route=2,
            known_routes={"/login"},
        )
        pd.record_turn(
            new_routes=2, new_elements=0,
            route_paths=["/login", "/new-page"],
        )
        pd.record_turn(new_routes=0, new_elements=0, route_paths=[])
        assert pd.is_plateaued() is False

    def test_missing_route_paths_falls_back_to_new_route_count(self):
        pd = PlateauDetector(
            max_turns_without_new_route=2,
            known_routes={"/login"},
        )
        pd.record_turn(new_routes=1, new_elements=0, route_paths=[])
        pd.record_turn(new_routes=0, new_elements=0, route_paths=[])
        assert pd.is_plateaued() is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_plateau.py::TestBaselineRoutes -v`
Expected: FAIL — `TypeError: unexpected keyword argument 'known_routes'`

- [ ] **Step 3: Implement baseline in PlateauDetector**

Modify `plateau.py` `__init__` to accept `known_routes` and `record_turn` to accept `route_paths`. Preserve any existing constructor thresholds and reset behavior; only add the baseline route logic.

```python
def __init__(
    self,
    max_turns_without_new_route: int = 3,
    max_turns_without_new_interactive_element: int = 3,
    max_repeated_denials: int = 3,
    max_invalid_actions: int = 2,
    known_routes: set[str] | None = None,
) -> None:
    self._max_no_route = max_turns_without_new_route
    self._max_no_element = max_turns_without_new_interactive_element
    self._max_denials = max_repeated_denials
    self._max_invalid = max_invalid_actions
    self._known_routes: set[str] = set(known_routes) if known_routes else set()

    self._turns_no_route: int = 0
    self._turns_no_element: int = 0
    self._denial_streak: int = 0
    self._invalid_streak: int = 0

def record_turn(
    self,
    new_routes: int,
    new_elements: int,
    route_paths: list[str] | None = None,
) -> None:
    novel_routes = new_routes
    provided_routes = {p for p in (route_paths or []) if p}
    if provided_routes and self._known_routes:
        novel_routes = sum(1 for p in provided_routes if p not in self._known_routes)

    if novel_routes > 0:
        self._turns_no_route = 0
    else:
        self._turns_no_route += 1

    if new_elements > 0:
        self._turns_no_element = 0
    else:
        self._turns_no_element += 1

    if novel_routes > 0 or new_elements > 0:
        self._denial_streak = 0
        self._invalid_streak = 0

    if provided_routes:
        self._known_routes.update(provided_routes)
```

- [ ] **Step 4: Run ALL plateau tests**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_plateau.py -v`
Expected: ALL PASS. Existing callers that do not pass route paths, or pass an empty list with a positive `new_routes`, must still use `new_routes` as the source of truth.

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/plateau.py backend/apps/agent/tests/test_plateau.py
git commit -m "feat(agent): add known_routes baseline to PlateauDetector"
```
