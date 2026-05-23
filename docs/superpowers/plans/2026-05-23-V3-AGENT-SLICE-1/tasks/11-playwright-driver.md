# Phase 5 — Playwright Driver
### Task 11: Thin Playwright adapter

**Files:**
- Create: `backend/apps/agent/browser/__init__.py`
- Create: `backend/apps/agent/browser/driver.py`
- Create: `backend/apps/agent/tests/test_driver.py`

The driver is a thin adapter — it owns the browser lifecycle and exposes typed
methods (navigate, get_page, fetch_asset). The controller calls these methods;
the LLM never touches Playwright directly.

- [ ] **Step 1: Write tests with mocked Playwright**

```python
# backend/apps/agent/tests/test_driver.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from apps.agent.browser.driver import PlaywrightDriver

@pytest.fixture
def mock_playwright():
    pw = AsyncMock()
    browser = AsyncMock()
    context = AsyncMock()
    page = AsyncMock()

    pw.chromium.launch = AsyncMock(return_value=browser)
    browser.new_context = AsyncMock(return_value=context)
    context.new_page = AsyncMock(return_value=page)

    page.url = "https://juiceshop.cocode.dk/"
    page.title = AsyncMock(return_value="Juice Shop")
    page.goto = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.close = AsyncMock()
    context.close = AsyncMock()
    browser.close = AsyncMock()

    return pw, browser, context, page

@pytest.mark.asyncio
async def test_driver_navigate(mock_playwright):
    pw, browser, context, page = mock_playwright
    with patch("apps.agent.browser.driver.async_playwright") as mock_apw:
        mock_apw.return_value.start = AsyncMock(return_value=pw)

        driver = PlaywrightDriver()
        await driver.start("https://juiceshop.cocode.dk")
        page.goto.assert_called_once()
        page.goto.reset_mock()
        driver._page = page

        await driver.navigate("/about")
        page.goto.assert_called_once()
        call_url = page.goto.call_args[0][0]
        assert "/about" in call_url


@pytest.mark.asyncio
async def test_driver_fetch_asset_returns_truncated():
    driver = PlaywrightDriver()
    driver._base_url = "https://juiceshop.cocode.dk"
    driver._page = AsyncMock()

    response = AsyncMock()
    response.status = 200
    response.text = AsyncMock(return_value="x" * 200_000)
    response.headers = {"content-type": "application/javascript"}
    driver._page.context.request.get = AsyncMock(return_value=response)

    content, size, truncated = await driver.fetch_asset("/main.js")
    assert truncated is True
    assert size == 200_000
    assert len(content) < 200_000

@pytest.mark.asyncio
async def test_driver_scope_validation():
    driver = PlaywrightDriver()
    driver._base_url = "https://juiceshop.cocode.dk"

    assert driver.is_in_scope("https://juiceshop.cocode.dk/api/users")
    assert not driver.is_in_scope("https://evil.com/steal")
    assert not driver.is_in_scope("//evil.com/steal")
    assert not driver.is_in_scope("javascript:alert(1)")
    assert driver.is_in_scope("/relative/path")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest apps/agent/tests/test_driver.py -v`
Expected: FAIL

- [ ] **Step 3: Implement PlaywrightDriver**

```python
# backend/apps/agent/browser/__init__.py
# (empty)
```

```python
# backend/apps/agent/browser/driver.py
from __future__ import annotations

from urllib.parse import urlparse, urljoin
from typing import Any

from playwright.async_api import async_playwright, Page, Browser, BrowserContext

MAX_ASSET_SIZE = 100_000

class PlaywrightDriver:
    def __init__(self) -> None:
        self._pw: Any = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._base_url: str = ""
        self._network_log: list[dict[str, Any]] = []

    async def start(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=True)
        self._context = await self._browser.new_context()
        self._page = await self._context.new_page()
        self._page.on("response", self._on_response)
        await self._page.goto(self._base_url, wait_until="networkidle")

    async def stop(self) -> None:
        if self._page:
            await self._page.close()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()

    @property
    def page(self) -> Page:
        assert self._page is not None
        return self._page

    async def navigate(self, path: str) -> str:
        url = urljoin(self._base_url + "/", path)
        if not self.is_in_scope(url):
            raise ValueError(f"Out-of-scope navigation blocked: {url}")
        await self._page.goto(url, wait_until="networkidle")
        return self._page.url

    async def fetch_asset(self, path: str) -> tuple[str, int, bool]:
        url = urljoin(self._base_url + "/", path)
        if not self.is_in_scope(url):
            raise ValueError(f"Out-of-scope asset fetch blocked: {url}")
        response = await self._page.context.request.get(url)
        full_text = await response.text()
        size = len(full_text)
        truncated = size > MAX_ASSET_SIZE
        content = full_text[:MAX_ASSET_SIZE] if truncated else full_text
        return content, size, truncated

    def is_in_scope(self, url: str) -> bool:
        if url.startswith("//"):
            return False
        parsed = urlparse(url)
        if parsed.scheme and parsed.scheme not in {"http", "https"}:
            return False
        if url.startswith("/"):
            return True
        base_parsed = urlparse(self._base_url)
        return parsed.netloc == base_parsed.netloc

    def drain_network_log(self) -> list[dict[str, Any]]:
        log = list(self._network_log)
        self._network_log.clear()
        return log

    def _on_response(self, response: Any) -> None:
        self._network_log.append({
            "url": response.url,
            "method": response.request.method,
            "status": response.status,
            "resource_type": response.request.resource_type,
            "content_type": response.headers.get("content-type", ""),
        })
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest apps/agent/tests/test_driver.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/browser/ backend/apps/agent/tests/test_driver.py
git commit -m "feat(agent): add thin Playwright driver adapter"
```
