---
companion_of: 11-playwright-driver
---

# Task 11 — PlaywrightDriver Implementation

Part of [Task 11](11-playwright-driver.md). Step 3 implementation code.

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
