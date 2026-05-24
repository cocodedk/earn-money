---
companion_of: 08-page-observation
---

# Task 08 — Element Dataclasses

Part of [Task 08](08-page-observation.md). Element and container types for
`backend/apps/agent/observations/page.py` (first half).

```python
# backend/apps/agent/observations/page.py (element types)
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
```

Continues in [08-page-observation-composite.md](08-page-observation-composite.md).
