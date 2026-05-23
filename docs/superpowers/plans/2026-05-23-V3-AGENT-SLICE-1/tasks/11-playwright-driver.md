---
tier: CAPABLE
depends_on: [03-migrations]
files:
  creates:
    - backend/apps/agent/browser/__init__.py
    - backend/apps/agent/browser/driver.py
    - backend/apps/agent/tests/test_driver.py
  modifies: []
allow_extra_files: false
---

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

- [ ] **Step 3: Implement** — see [11-playwright-driver-impl.md](11-playwright-driver-impl.md)

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest apps/agent/tests/test_driver.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/browser/ backend/apps/agent/tests/test_driver.py
git commit -m "feat(agent): add thin Playwright driver adapter"
```
