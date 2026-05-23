# 10-observation-builder — Implementation Code

Part of [Task 10](10-observation-builder.md). This file contains Step 3.

- [ ] **Step 3: Implement ObservationBuilder**

```python
# backend/apps/agent/observations/builder.py
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from .page import (
    PageObservation, PageIdentity, LinkElement, ButtonElement,
    FormElement, FormField, InputElement, VisibleTextBlock,
    DiscoveredRoute, DiscoveredAsset, HtmlExcerpt,
    NetworkEntry, CookieInfo, StorageKey, ConsoleMessage,
    ScreenshotRef, ObservationMeta, Elements, DiscoveredItems,
)


class ObservationBuilder:
    def __init__(self, target_origin: str) -> None:
        self._origin = target_origin
        self._id_counters: dict[str, int] = {}
        self._url_map: dict[str, str] = {}

    def _next_id(self, prefix: str) -> str:
        n = self._id_counters.get(prefix, 0)
        self._id_counters[prefix] = n + 1
        return f"{prefix}_{n}"

    def _url_ref(self, path: str) -> str:
        if path not in self._url_map:
            self._url_map[path] = self._next_id("url")
        return self._url_map[path]

    async def build_page_observation(
        self,
        page: Any,
        turn: int,
        phase: str,
        action_ref: str,
        network_entries: list[dict[str, Any]],
    ) -> PageObservation:
        url = page.url
        parsed = urlparse(url)
        title = await page.title()
        snapshot = await page.accessibility.snapshot() or {}
        raw_cookies = await page.context.cookies() or []

        links, buttons, forms, inputs, texts = self._parse_a11y(snapshot)
        routes = self._extract_routes(links)
        assets = self._extract_assets(network_entries)
        cookies = self._redact_cookies(raw_cookies)
        network = self._build_network(network_entries)
        page_hash = hashlib.sha256(f"{url}{title}".encode()).hexdigest()[:16]

        obs_id = self._next_id("obs")
        return PageObservation(
            id=obs_id, turn=turn, phase=phase, action_ref=action_ref,
            page=PageIdentity(
                url_ref=self._url_ref(parsed.path or "/"),
                path=parsed.path or "/", title=title,
                origin_label="target", load_state="networkidle",
                page_hash=page_hash,
            ),
            elements=Elements(
                links=links, buttons=buttons, forms=forms, inputs=inputs,
            ),
            visible_text=texts,
            discovered=DiscoveredItems(routes=routes, assets=assets),
            selected_html_excerpts=[],
            network=network,
            cookies=cookies,
            storage_keys=[],
            console=[],
            screenshot=ScreenshotRef(artifact_ref=None, reason=None),
            meta=ObservationMeta(
                observed_at=datetime.now(timezone.utc).isoformat(),
                response_bytes=0, truncated=False,
                redactions=["cookie_values"],
            ),
        )

    def _parse_a11y(self, snapshot: dict) -> tuple:
        links, buttons, forms, inputs, texts = [], [], [], [], []
        for child in snapshot.get("children", []):
            role = child.get("role", "")
            name = child.get("name", "")
            if role == "link":
                url = child.get("url", "")
                links.append(LinkElement(
                    id=self._next_id("link"), text=name,
                    accessible_name=name,
                    href_ref=self._url_ref(url) if url else "",
                    visible=True,
                ))
            elif role == "button":
                buttons.append(ButtonElement(
                    id=self._next_id("btn"), text=name,
                    aria_role="button", accessible_name=name,
                    enabled=not child.get("disabled", False),
                ))
            elif name:
                texts.append(VisibleTextBlock(
                    id=self._next_id("txt"), text=name, role_context=role,
                ))
        return links, buttons, forms, inputs, texts

    def _extract_routes(self, links: list[LinkElement]) -> list[DiscoveredRoute]:
        routes = []
        for link in links:
            if link.href_ref:
                path = self.resolve_url_ref(link.href_ref)
                if path:
                    routes.append(DiscoveredRoute(
                        id=self._next_id("route"), path=path, source="link",
                    ))
        return routes

    def resolve_url_ref(self, ref: str) -> str | None:
        for path, url_ref in self._url_map.items():
            if url_ref == ref:
                return path
        return None

    def _extract_assets(self, network_entries: list[dict]) -> list[DiscoveredAsset]:
        assets = []
        for entry in network_entries:
            rtype = entry.get("resource_type", "")
            if rtype in ("script", "stylesheet"):
                path = urlparse(entry.get("url", "")).path
                assets.append(DiscoveredAsset(
                    id=self._next_id("asset"), path=path, type=rtype,
                ))
        return assets

    def _redact_cookies(self, raw: list[dict]) -> list[CookieInfo]:
        return [
            CookieInfo(
                name=c["name"], domain=c.get("domain", ""),
                path=c.get("path", "/"),
                secure=c.get("secure", False),
                httponly=c.get("httpOnly", False),
                samesite=c.get("sameSite", "None"),
            )
            for c in raw
        ]

    def _build_network(self, entries: list[dict]) -> list[NetworkEntry]:
        return [
            NetworkEntry(
                id=self._next_id("req"),
                method=e.get("method", "GET"),
                path=urlparse(e.get("url", "")).path,
                status=e.get("status", 0),
                resource_type=e.get("resource_type", "other"),
                content_type=e.get("content_type", ""),
            )
            for e in entries
        ]
```

