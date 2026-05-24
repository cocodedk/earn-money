---
tier: FAST
depends_on: []
files:
  creates: []
  modifies:
    - backend/apps/agent/browser/driver.py
    - backend/apps/agent/tests/test_driver.py
  deletes: []
exports:
  - PlaywrightDriver.fill
imports: []
allow_extra_files: false
---

### Task 2: Driver fill() method

**Files:**
- Modify: `backend/apps/agent/browser/driver.py`
- Modify: `backend/apps/agent/tests/test_driver.py`

- [ ] **Step 1: Write failing tests for driver.fill()**

Add to `test_driver.py`:

```python
class TestDriverFill:
    def test_fill_known_element(self):
        driver = PlaywrightDriver()
        driver._element_registry = {"input_1": "input[name='email']"}
        page = MagicMock()
        locator = MagicMock()
        page.locator.return_value = locator
        locator.fill = AsyncMock()
        driver._page = page

        run(driver.fill("input_1", "admin@example.com"))
        page.locator.assert_called_once_with("input[name='email']")
        locator.fill.assert_awaited_once_with("admin@example.com")

    def test_fill_unknown_element_raises(self):
        driver = PlaywrightDriver()
        driver._element_registry = {}
        with pytest.raises(ValueError, match="Unknown element_id"):
            run(driver.fill("input_999", "test"))

    def test_fill_empty_value_clears(self):
        driver = PlaywrightDriver()
        driver._element_registry = {"input_0": "input[name='q']"}
        page = MagicMock()
        locator = MagicMock()
        page.locator.return_value = locator
        locator.fill = AsyncMock()
        driver._page = page

        run(driver.fill("input_0", ""))
        locator.fill.assert_awaited_once_with("")

    def test_fill_without_page_raises_clear_error(self):
        driver = PlaywrightDriver()
        driver._element_registry = {"input_0": "input[name='q']"}
        driver._page = None
        with pytest.raises(RuntimeError, match="active page"):
            run(driver.fill("input_0", "test"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_driver.py::TestDriverFill -v`
Expected: FAIL — `PlaywrightDriver has no attribute 'fill'`

- [ ] **Step 3: Implement fill() method**

Add to `driver.py` after the `click` method:

```python
async def fill(self, element_id: str, value: str) -> None:
    """Fill the input identified by element_id with value."""
    if element_id not in self._element_registry:
        raise ValueError(f"Unknown element_id: {element_id!r}")
    if self._page is None:
        raise RuntimeError("Cannot fill without an active page")
    selector = self._element_registry[element_id]
    locator = self._page.locator(selector)
    await locator.fill(value)
```

If the existing `click()` method already uses a different active-page guard or exception message, reuse that exact local pattern and update the test's `match=` string accordingly.

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_driver.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/browser/driver.py backend/apps/agent/tests/test_driver.py
git commit -m "feat(agent): add fill() method to PlaywrightDriver"
```
