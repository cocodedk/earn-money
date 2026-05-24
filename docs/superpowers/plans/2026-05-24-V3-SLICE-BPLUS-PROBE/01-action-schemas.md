# Task 1: Action Schemas — ClickAction + HttpRequestAction

**Files:**
- Modify: `backend/apps/agent/actions/schemas.py`
- Modify: `backend/apps/agent/tests/test_actions.py`

---

- [ ] **Step 1: Write tests for ClickAction parsing**

Add to `backend/apps/agent/tests/test_actions.py`:

```python
class TestClickAction:
    def test_parse_valid_click(self):
        raw = {
            "action": "click", "goal": "g", "reason": "r",
            "hypothesis": "h", "element_id": "link_3",
        }
        env = parse_action(raw)
        assert env.action == "click"
        assert env.parsed.element_id == "link_3"

    def test_reject_missing_element_id(self):
        raw = {
            "action": "click", "goal": "g", "reason": "r",
            "hypothesis": "h",
        }
        with pytest.raises(InvalidActionError, match="element_id"):
            parse_action(raw)
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_actions.py::TestClickAction -v`
Expected: FAIL — `Unknown action 'click'`

- [ ] **Step 3: Add ClickAction dataclass + register**

In `backend/apps/agent/actions/schemas.py`, add after `StopAction`:

```python
@dataclass
class ClickAction:
    element_id: str

    def __post_init__(self) -> None:
        if not self.element_id:
            raise InvalidActionError("click requires a non-empty element_id")
```

Add to `_ACTION_MAP`: `"click": ClickAction,`

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_actions.py::TestClickAction -v`

- [ ] **Step 5: Write tests for HttpRequestAction**

```python
_ALLOWED_METHODS = frozenset({"GET", "HEAD"})


class TestHttpRequestAction:
    def test_parse_valid_get(self):
        raw = {
            "action": "http_request", "goal": "g", "reason": "r",
            "hypothesis": "h", "method": "GET", "path": "/api/test",
        }
        env = parse_action(raw)
        assert env.parsed.method == "GET"
        assert env.parsed.path == "/api/test"

    def test_parse_valid_head(self):
        raw = {
            "action": "http_request", "goal": "g", "reason": "r",
            "hypothesis": "h", "method": "HEAD", "path": "/",
        }
        env = parse_action(raw)
        assert env.parsed.method == "HEAD"

    def test_reject_post(self):
        raw = {
            "action": "http_request", "goal": "g", "reason": "r",
            "hypothesis": "h", "method": "POST", "path": "/api/test",
        }
        with pytest.raises(InvalidActionError, match="GET.*HEAD"):
            parse_action(raw)

    def test_reject_absolute_url(self):
        raw = {
            "action": "http_request", "goal": "g", "reason": "r",
            "hypothesis": "h", "method": "GET",
            "path": "https://evil.com/steal",
        }
        with pytest.raises(InvalidActionError, match="must not contain"):
            parse_action(raw)
```

- [ ] **Step 6: Add HttpRequestAction dataclass + register**

```python
_SAFE_HTTP_METHODS = frozenset({"GET", "HEAD"})


@dataclass
class HttpRequestAction:
    method: str
    path: str

    def __post_init__(self) -> None:
        if self.method not in _SAFE_HTTP_METHODS:
            raise InvalidActionError(
                f"http_request method must be GET or HEAD, got {self.method!r}"
            )
        _validate_url(self.path, "path")
```

Add to `_ACTION_MAP`: `"http_request": HttpRequestAction,`

- [ ] **Step 7: Run all action tests**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_actions.py -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add backend/apps/agent/actions/schemas.py backend/apps/agent/tests/test_actions.py
git commit -m "feat(agent): add ClickAction + HttpRequestAction schemas"
```
