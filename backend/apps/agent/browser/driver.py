from __future__ import annotations

from urllib.parse import urlparse

MAX_ASSET_SIZE = 100_000

_BLOCKED_SCHEMES = frozenset({"javascript", "data", "file", "ftp"})


class ScopeViolationError(ValueError):
    """Raised when navigation or fetch targets a URL outside the allowed scope."""


class PlaywrightDriver:
    """Thin adapter over a Playwright browser page."""

    def __init__(self) -> None:
        self._base_url: str | None = None
        self._base_host: str | None = None
        self._pw = None  # playwright instance
        self._browser = None
        self._context = None
        self._page = None
        self._network_log: list[dict] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self, base_url: str) -> None:
        """Launch a headless browser and navigate to base_url."""
        from playwright.async_api import async_playwright  # lazy import

        parsed = urlparse(base_url)
        self._base_url = base_url
        self._base_host = parsed.netloc

        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=True)
        self._context = await self._browser.new_context()
        self._page = await self._context.new_page()
        self._page.on("response", self._on_response)
        await self._page.goto(base_url)

    async def stop(self) -> None:
        """Close the browser and clean up resources."""
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
        self._page = None
        self._browser = None
        self._pw = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def page(self):
        """Return the current Playwright page object."""
        return self._page

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    async def navigate(self, path: str) -> None:
        """Navigate to path relative to base_url. Validates scope."""
        url = self._resolve(path)
        if not self.is_in_scope(url):
            raise ScopeViolationError(f"URL out of scope: {url!r}")
        await self._page.goto(url)

    # ------------------------------------------------------------------
    # Asset fetching
    # ------------------------------------------------------------------

    async def fetch_asset(self, path: str) -> dict:
        """Fetch asset at path. Returns content, size, and truncated flag."""
        url = self._resolve(path)
        if not self.is_in_scope(url):
            raise ScopeViolationError(f"Asset URL out of scope: {url!r}")
        response = await self._page.request.get(url)
        raw = await response.body()
        truncated = len(raw) > MAX_ASSET_SIZE
        content = raw[:MAX_ASSET_SIZE]
        try:
            text = content.decode("utf-8", errors="replace")
        except Exception:
            text = ""
        return {
            "content": text,
            "size_bytes": len(raw),
            "truncated": truncated,
        }

    # ------------------------------------------------------------------
    # Scope check
    # ------------------------------------------------------------------

    def is_in_scope(self, url: str) -> bool:
        """Return True if url is within the allowed scope."""
        if url.startswith("//"):
            return False
        parsed = urlparse(url)
        if parsed.scheme in _BLOCKED_SCHEMES:
            return False
        if parsed.scheme not in ("http", "https"):
            return False
        if parsed.netloc != self._base_host:
            return False
        return True

    # ------------------------------------------------------------------
    # Network log
    # ------------------------------------------------------------------

    def drain_network_log(self) -> list[dict]:
        """Return and clear accumulated network log entries."""
        log = list(self._network_log)
        self._network_log.clear()
        return log

    def _on_response(self, response) -> None:
        """Playwright response handler — appends entry to network log."""
        self._network_log.append({
            "url": response.url,
            "status": response.status,
            "method": response.request.method,
        })

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve(self, path: str) -> str:
        """Resolve a path against base_url."""
        if path.startswith("http://") or path.startswith("https://"):
            return path
        base = (self._base_url or "").rstrip("/")
        return f"{base}/{path.lstrip('/')}"
