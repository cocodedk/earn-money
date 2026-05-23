---
companion_of: 08-page-observation
---

# Task 08 — Composite Dataclasses

Part of [Task 08](08-page-observation.md). Network, browser state, and
`PageObservation` assembly for `backend/apps/agent/observations/page.py`
(second half).

Continues from [08-page-observation-elements.md](08-page-observation-elements.md).

```python
# backend/apps/agent/observations/page.py (composite types — same file)

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
            "selected_html_excerpts": [
                e.to_dict() for e in self.selected_html_excerpts
            ],
            "network": {
                "entries": [e.to_dict() for e in self.network],
            },
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
