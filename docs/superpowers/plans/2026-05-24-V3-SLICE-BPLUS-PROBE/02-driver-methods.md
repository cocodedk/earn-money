# Task 2: Driver — click + http_request Methods

**Files:**
- Modify: `backend/apps/agent/browser/driver.py`
- Modify: `backend/apps/agent/tests/test_driver.py`

---

- [ ] **Step 1: Write tests for driver.click()**

Add to `backend/apps/agent/tests/test_driver.py`:

```python
class TestDriverClick:
    def test_click_known_element(self):
        driver = PlaywrightDriver()
        driver._element_registry = {"link_3": "a >> nth=2"}
        page = AsyncMock()
        locator = MagicMock()
        page.locator.return_value = locator
        locator.click = AsyncMock()
        driver._page = page

        run(driver.click("link_3"))
        page.locator.assert_called_once_with("a >> nth=2")
        locator.click.assert_awaited_once()

    def test_click_unknown_element_raises(self):
        driver = PlaywrightDriver()
        driver._element_registry = {}
        with pytest.raises(ValueError, match="Unknown element_id"):
            run(driver.click("link_999"))
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_driver.py::TestDriverClick -v`

- [ ] **Step 3: Implement driver.click()**

In `backend/apps/agent/browser/driver.py`, add to `PlaywrightDriver`:

```python
    def __init__(self) -> None:
        # ... existing fields ...
        self._element_registry: dict[str, str] = {}

    def register_elements(self, registry: dict[str, str]) -> None:
        self._element_registry = dict(registry)

    async def click(self, element_id: str) -> None:
        if element_id not in self._element_registry:
            raise ValueError(f"Unknown element_id: {element_id!r}")
        selector = self._element_registry[element_id]
        locator = self._page.locator(selector)
        await locator.click()
```

- [ ] **Step 4: Run click tests — expect PASS**

- [ ] **Step 5: Write tests for driver.http_request()**

```python
class TestDriverHttpRequest:
    def test_get_same_origin(self):
        driver = PlaywrightDriver()
        driver._base_url = "https://juiceshop.cocode.dk"
        driver._base_host = "juiceshop.cocode.dk"
        page = MagicMock()
        resp = AsyncMock()
        resp.status = 200
        resp.headers = {"content-type": "text/html"}
        resp.url = "https://juiceshop.cocode.dk/api/test"
        resp.body = AsyncMock(return_value=b"<html>ok</html>")
        page.request.get = AsyncMock(return_value=resp)
        driver._page = page

        result = run(driver.http_request("GET", "/api/test"))
        assert result["status"] == 200
        assert result["method"] == "GET"
        assert result["trust"] == "untrusted_target_content"

    def test_rejects_out_of_scope(self):
        driver = PlaywrightDriver()
        driver._base_url = "https://juiceshop.cocode.dk"
        driver._base_host = "juiceshop.cocode.dk"
        with pytest.raises(ScopeViolationError):
            run(driver.http_request("GET", "https://evil.com/steal"))

    def test_truncates_large_body(self):
        driver = PlaywrightDriver()
        driver._base_url = "https://example.com"
        driver._base_host = "example.com"
        page = MagicMock()
        resp = AsyncMock()
        resp.status = 200
        resp.headers = {"content-type": "text/plain"}
        resp.url = "https://example.com/big"
        resp.body = AsyncMock(return_value=b"x" * 200_000)
        page.request.get = AsyncMock(return_value=resp)
        driver._page = page

        result = run(driver.http_request("GET", "/big"))
        assert result["body_truncated"] is True
        assert len(result["body_excerpt"]) <= MAX_BODY_EXCERPT + 100
```

- [ ] **Step 6: Implement driver.http_request()**

```python
MAX_BODY_EXCERPT = 10_000


async def http_request(self, method: str, path: str) -> dict:
    url = self._resolve(path)
    if not self.is_in_scope(url):
        raise ScopeViolationError(f"HTTP request out of scope: {url!r}")
    if method == "GET":
        resp = await self._page.request.get(url)
    else:
        resp = await self._page.request.head(url)
    raw_body = await resp.body()
    truncated = len(raw_body) > MAX_BODY_EXCERPT
    excerpt = raw_body[:MAX_BODY_EXCERPT].decode("utf-8", errors="replace")
    return {
        "url": resp.url,
        "method": method,
        "status": resp.status,
        "content_type": resp.headers.get("content-type", ""),
        "redirected": resp.url != url,
        "final_url": resp.url,
        "body_excerpt": excerpt,
        "body_truncated": truncated,
        "trust": "untrusted_target_content",
    }
```

- [ ] **Step 7: Run all driver tests**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_driver.py -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add backend/apps/agent/browser/driver.py backend/apps/agent/tests/test_driver.py
git commit -m "feat(agent): add click + http_request to PlaywrightDriver"
```
