from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

_UNTRUSTED = "untrusted_target_content"


@dataclass
class PageIdentity:
    url: str
    title: str
    status_code: int


@dataclass
class LinkElement:
    element_id: str
    href: str
    text: str


@dataclass
class ButtonElement:
    element_id: str
    text: str
    type: str = "button"


@dataclass
class FormField:
    name: str
    type: str
    required: bool = False


@dataclass
class FormElement:
    element_id: str
    action: str
    method: str
    fields: list[FormField] = field(default_factory=list)


@dataclass
class InputElement:
    element_id: str
    name: str
    type: str
    placeholder: str = ""


@dataclass
class Elements:
    links: list[LinkElement] = field(default_factory=list)
    buttons: list[ButtonElement] = field(default_factory=list)
    forms: list[FormElement] = field(default_factory=list)
    inputs: list[InputElement] = field(default_factory=list)


@dataclass
class VisibleTextBlock:
    text: str
    selector: str = ""
    trust: str = _UNTRUSTED


@dataclass
class DiscoveredRoute:
    path: str
    method: str = "GET"


@dataclass
class DiscoveredAsset:
    asset_ref: str
    url: str
    asset_type: str


@dataclass
class DiscoveredItems:
    routes: list[DiscoveredRoute] = field(default_factory=list)
    assets: list[DiscoveredAsset] = field(default_factory=list)
    trust: str = _UNTRUSTED


@dataclass
class HtmlExcerpt:
    selector: str
    html: str
    trust: str = _UNTRUSTED


@dataclass
class NetworkEntry:
    url: str
    method: str
    status: int
    content_type: str = ""


@dataclass
class CookieInfo:
    name: str
    domain: str
    secure: bool = False
    http_only: bool = False


@dataclass
class StorageKey:
    key: str
    storage_type: str


@dataclass
class ConsoleMessage:
    level: str
    text: str
    trust: str = _UNTRUSTED


@dataclass
class ScreenshotRef:
    ref: str
    width: int
    height: int


@dataclass
class ObservationMeta:
    turn_index: int
    phase: str
    elapsed_ms: int


@dataclass
class PageObservation:
    identity: PageIdentity
    meta: ObservationMeta
    elements: Elements = field(default_factory=Elements)
    visible_text: list[VisibleTextBlock] = field(default_factory=list)
    discovered: DiscoveredItems = field(default_factory=DiscoveredItems)
    html_excerpts: list[HtmlExcerpt] = field(default_factory=list)
    network: list[NetworkEntry] = field(default_factory=list)
    cookies: list[CookieInfo] = field(default_factory=list)
    storage_keys: list[StorageKey] = field(default_factory=list)
    console: list[ConsoleMessage] = field(default_factory=list)
    screenshot: ScreenshotRef | None = None
    trust: str = _UNTRUSTED

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)
