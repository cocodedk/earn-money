# Phase 4 — Observation Schemas & Builder

### Task 8: PageObservation dataclass

**Files:**
- Create: `backend/apps/agent/observations/__init__.py`
- Create: `backend/apps/agent/observations/page.py`
- Create: `backend/apps/agent/tests/test_page_observation.py`

- [ ] **Step 1: Write tests for PageObservation**

```python
# backend/apps/agent/tests/test_page_observation.py
import pytest
from apps.agent.observations.page import (
    PageObservation, PageIdentity, LinkElement, ButtonElement,
    FormElement, FormField, InputElement, VisibleTextBlock,
    DiscoveredRoute, DiscoveredAsset, HtmlExcerpt,
    NetworkEntry, CookieInfo, StorageKey, ConsoleMessage,
    ScreenshotRef, ObservationMeta, Elements, DiscoveredItems,
)


def test_page_observation_to_dict():
    obs = PageObservation(
        id="obs_1", turn=0, phase="recon", action_ref="act_0",
        page=PageIdentity(
            url_ref="url_1", path="/", title="Juice Shop",
            origin_label="target", load_state="networkidle", page_hash="abc",
        ),
        elements=Elements(links=[], buttons=[], forms=[], inputs=[]),
        visible_text=[],
        discovered=DiscoveredItems(routes=[], assets=[]),
        selected_html_excerpts=[],
        network=[],
        cookies=[], storage_keys=[],
        console=[],
        screenshot=ScreenshotRef(artifact_ref=None, reason=None),
        meta=ObservationMeta(
            observed_at="2026-05-23T12:00:00Z",
            response_bytes=5000, truncated=False, redactions=[],
        ),
    )
    d = obs.to_dict()
    assert d["page"]["path"] == "/"
    assert d["id"] == "obs_1"


def test_page_observation_elements():
    link = LinkElement(
        id="link_1", text="About", accessible_name="About",
        href_ref="url_2", visible=True,
    )
    btn = ButtonElement(
        id="btn_1", text="Login", aria_role="button",
        accessible_name="Login", enabled=True,
    )
    form = FormElement(
        id="form_1", method="POST", action_ref="url_3",
        fields=[FormField(id="f_1", label="Email", type="email", required=True)],
    )
    inp = InputElement(
        id="inp_1", label="Search", type="text",
        required=False, value_state="empty",
    )
    elems = Elements(links=[link], buttons=[btn], forms=[form], inputs=[inp])
    d = elems.to_dict()
    assert len(d["links"]) == 1
    assert d["forms"][0]["fields"][0]["label"] == "Email"


def test_trust_annotations():
    obs = PageObservation(
        id="obs_2", turn=1, phase="recon", action_ref="act_1",
        page=PageIdentity(
            url_ref="url_1", path="/", title="Test",
            origin_label="target", load_state="networkidle", page_hash="x",
        ),
        elements=Elements(links=[], buttons=[], forms=[], inputs=[]),
        visible_text=[VisibleTextBlock(id="txt_1", text="Hello", role_context="heading")],
        discovered=DiscoveredItems(routes=[], assets=[
            DiscoveredAsset(
                id="asset_1", path="/main.js", type="script",
                interesting_refs=["/admin"],
            ),
        ]),
        selected_html_excerpts=[], network=[], cookies=[], storage_keys=[],
        console=[ConsoleMessage(level="error", text="fail", source_ref="r1")],
        screenshot=ScreenshotRef(artifact_ref=None, reason=None),
        meta=ObservationMeta(
            observed_at="2026-05-23T12:00:00Z",
            response_bytes=0, truncated=False, redactions=[],
        ),
    )
    d = obs.to_dict()
    assert d["visible_text"]["trust"] == "untrusted_target_content"
    assert d["discovered"]["assets"][0]["trust"] == "untrusted_target_content"
    assert d["console"]["trust"] == "untrusted_target_content"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest apps/agent/tests/test_page_observation.py -v`
Expected: FAIL

- [ ] **Step 3: Implement PageObservation**

```python
# backend/apps/agent/observations/__init__.py
# (empty)
```

```python
# backend/apps/agent/observations/page.py
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass(frozen=True)
class PageIdentity:
    url_ref: str
    path: str
    title: str
    origin_label: str
    load_state: str
    page_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LinkElement:
    id: str
    text: str
    accessible_name: str
    href_ref: str
    visible: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ButtonElement:
    id: str
    text: str
    aria_role: str
    accessible_name: str
    enabled: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FormField:
    id: str
    label: str
    type: str
    required: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FormElement:
    id: str
    method: str
    action_ref: str
    fields: list[FormField]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "method": self.method,
            "action_ref": self.action_ref,
            "fields": [f.to_dict() for f in self.fields],
        }


@dataclass(frozen=True)
class InputElement:
    id: str
    label: str
    type: str
    required: bool
    value_state: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Elements:
    links: list[LinkElement]
    buttons: list[ButtonElement]
    forms: list[FormElement]
    inputs: list[InputElement]

    def to_dict(self) -> dict[str, Any]:
        return {
            "links": [e.to_dict() for e in self.links],
            "buttons": [e.to_dict() for e in self.buttons],
            "forms": [e.to_dict() for e in self.forms],
            "inputs": [e.to_dict() for e in self.inputs],
        }


@dataclass(frozen=True)
class VisibleTextBlock:
    id: str
    text: str
    role_context: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DiscoveredRoute:
    id: str
    path: str
    source: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DiscoveredAsset:
    id: str
    path: str
    type: str
    interesting_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["trust"] = "untrusted_target_content"
        return d


@dataclass
class DiscoveredItems:
    routes: list[DiscoveredRoute]
    assets: list[DiscoveredAsset]

    def to_dict(self) -> dict[str, Any]:
        return {
            "routes": [r.to_dict() for r in self.routes],
            "assets": [a.to_dict() for a in self.assets],
        }


@dataclass(frozen=True)
class HtmlExcerpt:
    id: str
    reason: str
    excerpt: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["trust"] = "untrusted_target_content"
        return d


@dataclass(frozen=True)
class NetworkEntry:
    id: str
    method: str
    path: str
    status: int
    resource_type: str
    content_type: str
    redirect_chain: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CookieInfo:
    name: str
    domain: str
    path: str
    secure: bool
    httponly: bool
    samesite: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StorageKey:
    type: str
    key: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConsoleMessage:
    level: str
    text: str
    source_ref: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScreenshotRef:
    artifact_ref: str | None
    reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {"artifact_ref": self.artifact_ref, "reason": self.reason}


@dataclass
class ObservationMeta:
    observed_at: str
    response_bytes: int
    truncated: bool
    redactions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PageObservation:
    id: str
    turn: int
    phase: str
    action_ref: str
    page: PageIdentity
    elements: Elements
    visible_text: list[VisibleTextBlock]
    discovered: DiscoveredItems
    selected_html_excerpts: list[HtmlExcerpt]
    network: list[NetworkEntry]
    cookies: list[CookieInfo]
    storage_keys: list[StorageKey]
    console: list[ConsoleMessage]
    screenshot: ScreenshotRef
    meta: ObservationMeta

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "turn": self.turn,
            "phase": self.phase, "action_ref": self.action_ref,
            "page": self.page.to_dict(),
            "elements": self.elements.to_dict(),
            "visible_text": {
                "trust": "untrusted_target_content",
                "blocks": [b.to_dict() for b in self.visible_text],
            },
            "discovered": self.discovered.to_dict(),
            "selected_html_excerpts": [e.to_dict() for e in self.selected_html_excerpts],
            "network": {"entries": [e.to_dict() for e in self.network]},
            "browser_state": {
                "cookies": [c.to_dict() for c in self.cookies],
                "storage_keys": [s.to_dict() for s in self.storage_keys],
            },
            "console": {
                "trust": "untrusted_target_content",
                "messages": [m.to_dict() for m in self.console],
            },
            "screenshot": self.screenshot.to_dict(),
            "meta": self.meta.to_dict(),
        }
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest apps/agent/tests/test_page_observation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/observations/ backend/apps/agent/tests/test_page_observation.py
git commit -m "feat(agent): add PageObservation dataclass with trust annotations"
```

### Task 9: AssetObservation dataclass

**Files:**
- Create: `backend/apps/agent/observations/assets.py`
- Create: `backend/apps/agent/tests/test_asset_observation.py`

- [ ] **Step 1: Write tests**

```python
# backend/apps/agent/tests/test_asset_observation.py
from apps.agent.observations.assets import AssetObservation, AssetExcerpt


def test_asset_observation_to_dict():
    obs = AssetObservation(
        asset_ref="asset_2", path="/main.js", type="script",
        size_bytes=142000, truncated=True,
        excerpts=[
            AssetExcerpt(
                context="route definition", match="/score-board",
                surrounding="path: '/score-board', component: ScoreBoardComponent",
            ),
        ],
        strings_of_interest=["/score-board", "/api/Users"],
    )
    d = obs.to_dict()
    assert d["trust"] == "untrusted_target_content"
    assert d["excerpts"][0]["match"] == "/score-board"
    assert "/score-board" in d["strings_of_interest"]


def test_asset_observation_empty_excerpts():
    obs = AssetObservation(
        asset_ref="asset_1", path="/vendor.js", type="script",
        size_bytes=500000, truncated=True,
        excerpts=[], strings_of_interest=[],
    )
    d = obs.to_dict()
    assert d["excerpts"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest apps/agent/tests/test_asset_observation.py -v`
Expected: FAIL

- [ ] **Step 3: Implement AssetObservation**

```python
# backend/apps/agent/observations/assets.py
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass(frozen=True)
class AssetExcerpt:
    context: str
    match: str
    surrounding: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AssetObservation:
    asset_ref: str
    path: str
    type: str
    size_bytes: int
    truncated: bool
    excerpts: list[AssetExcerpt]
    strings_of_interest: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_ref": self.asset_ref,
            "path": self.path,
            "type": self.type,
            "trust": "untrusted_target_content",
            "size_bytes": self.size_bytes,
            "truncated": self.truncated,
            "excerpts": [e.to_dict() for e in self.excerpts],
            "strings_of_interest": list(self.strings_of_interest),
        }
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest apps/agent/tests/test_asset_observation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/observations/assets.py backend/apps/agent/tests/test_asset_observation.py
git commit -m "feat(agent): add AssetObservation dataclass"
```

### Task 10: Observation builder (Playwright → PageObservation)

**Files:**
- Create: `backend/apps/agent/observations/builder.py`
- Create: `backend/apps/agent/tests/test_builder.py`

This task builds the bridge from raw Playwright page state to the normalized
PageObservation. In tests we mock the Playwright page object — real Playwright
tests come in Task 11 (browser driver) and Task 19 (integration).

- [ ] **Step 1: Write tests with mocked Playwright page**

```python
# backend/apps/agent/tests/test_builder.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from apps.agent.observations.builder import ObservationBuilder


@pytest.fixture
def mock_page():
    page = AsyncMock()
    page.url = "https://juiceshop.cocode.dk/"
    page.title = AsyncMock(return_value="OWASP Juice Shop")

    snapshot = {
        "role": "WebArea",
        "name": "OWASP Juice Shop",
        "children": [
            {"role": "link", "name": "About Us", "url": "/about"},
            {"role": "button", "name": "Login", "disabled": False},
        ],
    }
    page.accessibility.snapshot = AsyncMock(return_value=snapshot)
    page.context.cookies = AsyncMock(return_value=[
        {"name": "session", "domain": "juiceshop.cocode.dk", "path": "/",
         "secure": True, "httpOnly": True, "sameSite": "Lax", "value": "secret123"},
    ])
    page.evaluate = AsyncMock(return_value=[])
    return page


@pytest.mark.asyncio
async def test_builder_produces_page_observation(mock_page):
    builder = ObservationBuilder(target_origin="juiceshop.cocode.dk")
    obs = await builder.build_page_observation(
        page=mock_page, turn=0, phase="recon", action_ref="act_0",
        network_entries=[],
    )
    assert obs.page.path == "/"
    assert obs.page.title == "OWASP Juice Shop"


@pytest.mark.asyncio
async def test_builder_strips_cookie_values(mock_page):
    builder = ObservationBuilder(target_origin="juiceshop.cocode.dk")
    obs = await builder.build_page_observation(
        page=mock_page, turn=0, phase="recon", action_ref="act_0",
        network_entries=[],
    )
    d = obs.to_dict()
    for cookie in d["browser_state"]["cookies"]:
        assert "value" not in cookie


@pytest.mark.asyncio
async def test_builder_assigns_controller_ids(mock_page):
    builder = ObservationBuilder(target_origin="juiceshop.cocode.dk")
    obs = await builder.build_page_observation(
        page=mock_page, turn=0, phase="recon", action_ref="act_0",
        network_entries=[],
    )
    d = obs.to_dict()
    for link in d["elements"]["links"]:
        assert link["id"].startswith("link_")
    for btn in d["elements"]["buttons"]:
        assert btn["id"].startswith("btn_")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest apps/agent/tests/test_builder.py -v`
Expected: FAIL

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
                path = self._resolve_url_ref(link.href_ref)
                if path:
                    routes.append(DiscoveredRoute(
                        id=self._next_id("route"), path=path, source="link",
                    ))
        return routes

    def _resolve_url_ref(self, ref: str) -> str | None:
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

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest apps/agent/tests/test_builder.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/observations/builder.py backend/apps/agent/tests/test_builder.py
git commit -m "feat(agent): add ObservationBuilder (Playwright → PageObservation)"
```
