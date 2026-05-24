from __future__ import annotations

import time
from urllib.parse import urlparse

from .page import (
    ButtonElement,
    CookieInfo,
    DiscoveredAsset,
    DiscoveredItems,
    DiscoveredRoute,
    Elements,
    InputElement,
    LinkElement,
    NetworkEntry,
    ObservationMeta,
    PageIdentity,
    PageObservation,
    VisibleTextBlock,
)

_ASSET_TYPES = {
    ".js": "script",
    ".css": "stylesheet",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".gif": "image",
    ".svg": "image",
    ".woff": "font",
    ".woff2": "font",
    ".ttf": "font",
}


class ObservationBuilder:
    """Bridges Playwright page state into a PageObservation dataclass."""

    def __init__(self, target_origin: str) -> None:
        self._origin = target_origin.rstrip("/")
        self._counters: dict[str, int] = {}
        self._url_map: dict[str, str] = {}

    # ------------------------------------------------------------------
    # ID + URL helpers
    # ------------------------------------------------------------------

    def _next_id(self, prefix: str) -> str:
        idx = self._counters.get(prefix, 0)
        self._counters[prefix] = idx + 1
        return f"{prefix}_{idx}"

    def _url_ref(self, path: str) -> str:
        if path not in self._url_map:
            ref = f"url_{len(self._url_map)}"
            self._url_map[path] = ref
        return self._url_map[path]

    def resolve_url_ref(self, ref: str) -> str | None:
        for path, r in self._url_map.items():
            if r == ref:
                return path
        return None

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def build_page_observation(
        self,
        page,
        turn: int,
        phase: str,
        action_ref: str,  # noqa: ARG002 — reserved for future artifact linking
        network_entries: list[dict],
    ) -> PageObservation:
        start = time.monotonic()

        url: str = page.url
        title: str = await page.title()
        snapshot = await page.accessibility.snapshot() or {}
        raw_cookies: list[dict] = await page.context.cookies()

        children = snapshot.get("children", [])
        elements, visible_text = self._parse_a11y(children)
        routes = self._extract_routes(elements.links)
        assets = self._extract_assets(network_entries)
        cookies = self._redact_cookies(raw_cookies)
        network = self._build_network(network_entries)

        elapsed = int((time.monotonic() - start) * 1000)

        return PageObservation(
            identity=PageIdentity(url=url, title=title, status_code=0),
            meta=ObservationMeta(turn_index=turn, phase=phase, elapsed_ms=elapsed),
            elements=elements,
            visible_text=visible_text,
            discovered=DiscoveredItems(routes=routes, assets=assets),
            network=network,
            cookies=cookies,
        )

    # ------------------------------------------------------------------
    # A11y snapshot parsing
    # ------------------------------------------------------------------

    def _parse_a11y(
        self, children: list[dict]
    ) -> tuple[Elements, list[VisibleTextBlock]]:
        links: list[LinkElement] = []
        buttons: list[ButtonElement] = []
        inputs: list[InputElement] = []
        visible: list[VisibleTextBlock] = []

        for node in children:
            role = node.get("role", "")
            name = node.get("name", "")
            if role == "link":
                href = node.get("url", "") or node.get("value", "")
                links.append(LinkElement(
                    element_id=self._next_id("link"),
                    href=href,
                    text=name,
                ))
            elif role == "button":
                buttons.append(ButtonElement(
                    element_id=self._next_id("btn"),
                    text=name,
                    type=node.get("type", "button"),
                ))
            elif role in ("textbox", "searchbox", "combobox"):
                inputs.append(InputElement(
                    element_id=self._next_id("input"),
                    name=name,
                    type=role,
                    placeholder=node.get("placeholder", ""),
                ))
            if name:
                visible.append(VisibleTextBlock(text=name))

        return Elements(links=links, buttons=buttons, inputs=inputs), visible

    # ------------------------------------------------------------------
    # Route + asset extraction
    # ------------------------------------------------------------------

    def _extract_routes(self, links: list[LinkElement]) -> list[DiscoveredRoute]:
        seen: set[str] = set()
        routes: list[DiscoveredRoute] = []
        for link in links:
            href = link.href
            if not href:
                continue
            if href.startswith(self._origin):
                path = href[len(self._origin):]
            elif href.startswith("/"):
                path = href
            else:
                continue
            if path not in seen:
                seen.add(path)
                self._url_ref(path)
                routes.append(DiscoveredRoute(path=path))
        return routes

    def _extract_assets(self, entries: list[dict]) -> list[DiscoveredAsset]:
        assets: list[DiscoveredAsset] = []
        for entry in entries:
            url = entry.get("url", "")
            parsed = urlparse(url)
            ext = "." + parsed.path.rsplit(".", 1)[-1] if "." in parsed.path else ""
            asset_type = _ASSET_TYPES.get(ext.lower(), "")
            if not asset_type:
                continue
            path = parsed.path
            ref = self._next_id("asset")
            assets.append(DiscoveredAsset(asset_ref=ref, url=url, asset_type=asset_type))
        return assets

    # ------------------------------------------------------------------
    # Cookie + network helpers
    # ------------------------------------------------------------------

    def _redact_cookies(self, raw: list[dict]) -> list[CookieInfo]:
        return [
            CookieInfo(
                name=c.get("name", ""),
                domain=c.get("domain", ""),
                secure=bool(c.get("secure", False)),
                http_only=bool(c.get("httpOnly", False)),
            )
            for c in raw
        ]

    def _build_network(self, entries: list[dict]) -> list[NetworkEntry]:
        return [
            NetworkEntry(
                url=e.get("url", ""),
                method=e.get("method", "GET"),
                status=e.get("status", 0),
                content_type=e.get("content_type", ""),
            )
            for e in entries
        ]
