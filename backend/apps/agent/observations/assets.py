from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

_UNTRUSTED = "untrusted_target_content"


@dataclass
class AssetExcerpt:
    context: str
    match: str
    surrounding: str


@dataclass
class AssetObservation:
    asset_ref: str
    path: str
    type: str
    size_bytes: int
    truncated: bool
    excerpts: list[AssetExcerpt] = field(default_factory=list)
    strings_of_interest: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = dataclasses.asdict(self)
        d["trust"] = _UNTRUSTED
        return d
